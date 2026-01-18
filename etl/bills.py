"""ETL module for fetching Congressional bills from Congress.gov API."""

import json
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from congress_tracker.config import get_config
from congress_tracker.models.database import Bill, get_session, init_db

log = structlog.get_logger()


class BillFetcher:
    """Fetches bills from Congress.gov API."""

    def __init__(self):
        self.config = get_config()
        self.client = httpx.Client(timeout=30.0)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_bills_updated_on(self, target_date: date, congress: int) -> list[dict]:
        """Fetch bills updated on a specific date."""
        if not self.config.congress_api_key:
            raise ValueError("Congress.gov API key not configured")

        bills = []
        offset = 0
        limit = 250

        # Format date range for API
        from_dt = f"{target_date}T00:00:00Z"
        to_dt = f"{target_date}T23:59:59Z"

        while True:
            url = f"{self.config.congress_api_base}/bill/{congress}"
            params = {
                "api_key": self.config.congress_api_key,
                "format": "json",
                "fromDateTime": from_dt,
                "toDateTime": to_dt,
                "offset": offset,
                "limit": limit,
            }

            log.info("Fetching bills", congress=congress, date=str(target_date), offset=offset)
            response = self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            bill_list = data.get("bills", [])

            if not bill_list:
                break

            bills.extend(bill_list)
            offset += limit

            if len(bill_list) < limit:
                break

        return bills

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_bill_details(self, congress: int, bill_type: str, bill_number: int) -> Optional[dict]:
        """Fetch detailed bill information including summary."""
        url = f"{self.config.congress_api_base}/bill/{congress}/{bill_type.lower()}/{bill_number}"
        params = {
            "api_key": self.config.congress_api_key,
            "format": "json",
        }

        response = self.client.get(url, params=params)
        if response.status_code == 404:
            return None
        response.raise_for_status()

        return response.json().get("bill")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_bill_summaries(self, congress: int, bill_type: str, bill_number: int) -> list[dict]:
        """Fetch bill summaries."""
        url = f"{self.config.congress_api_base}/bill/{congress}/{bill_type.lower()}/{bill_number}/summaries"
        params = {
            "api_key": self.config.congress_api_key,
            "format": "json",
        }

        response = self.client.get(url, params=params)
        if response.status_code == 404:
            return []
        response.raise_for_status()

        return response.json().get("summaries", [])

    def _bill_to_model(self, bill_data: dict, details: Optional[dict] = None) -> Optional[Bill]:
        """Convert Congress.gov bill data to Bill model."""
        try:
            # Parse latest action date
            latest_action = bill_data.get("latestAction", {})
            latest_action_date = None
            if latest_action.get("actionDate"):
                latest_action_date = datetime.strptime(
                    latest_action["actionDate"], "%Y-%m-%d"
                ).date()

            bill = Bill(
                congress=bill_data.get("congress"),
                bill_type=bill_data.get("type", "").lower(),
                bill_number=int(bill_data.get("number", 0)),
                title=bill_data.get("title"),
                latest_action_date=latest_action_date,
                latest_action_text=latest_action.get("text"),
                source_url=bill_data.get("url"),
                raw_data=json.dumps(bill_data),
            )

            # Add details if available
            if details:
                introduced = details.get("introducedDate")
                if introduced:
                    bill.introduced_date = datetime.strptime(introduced, "%Y-%m-%d").date()

                # Sponsor info
                sponsors = details.get("sponsors", [])
                if sponsors:
                    sponsor = sponsors[0]
                    bill.sponsor_name = sponsor.get("fullName")
                    bill.sponsor_party = sponsor.get("party")
                    bill.sponsor_state = sponsor.get("state")

                # Policy area
                policy = details.get("policyArea")
                if policy:
                    bill.policy_area = policy.get("name")

            return bill
        except Exception as e:
            log.error("Failed to parse bill", error=str(e), data=bill_data)
            return None

    def fetch_bills_for_date(self, target_date: date, fetch_details: bool = False) -> list[Bill]:
        """Fetch all bills updated on a specific date."""
        year = target_date.year
        if year >= 2025:
            congress = 119
        elif year >= 2023:
            congress = 118
        else:
            congress = 117

        bills = []

        try:
            bill_list = self._fetch_bills_updated_on(target_date, congress)
            log.info("Fetched bill list", count=len(bill_list))

            for bill_data in bill_list:
                details = None
                if fetch_details:
                    try:
                        details = self._fetch_bill_details(
                            congress,
                            bill_data.get("type", "hr"),
                            int(bill_data.get("number", 0))
                        )
                    except Exception as e:
                        log.warning("Failed to fetch bill details", error=str(e))

                bill = self._bill_to_model(bill_data, details)
                if bill:
                    bills.append(bill)

        except Exception as e:
            log.error("Failed to fetch bills", error=str(e))

        log.info("Bills processed", count=len(bills), date=str(target_date))
        return bills

    def save_bills(self, bills: list[Bill]) -> int:
        """Save bills to database, updating existing records."""
        session = get_session()
        saved_count = 0

        try:
            for bill in bills:
                existing = session.query(Bill).filter(
                    Bill.congress == bill.congress,
                    Bill.bill_type == bill.bill_type,
                    Bill.bill_number == bill.bill_number,
                ).first()

                if existing:
                    # Update existing record
                    existing.title = bill.title
                    existing.latest_action_date = bill.latest_action_date
                    existing.latest_action_text = bill.latest_action_text
                    existing.raw_data = bill.raw_data
                    log.debug("Updated bill", bill_type=bill.bill_type, number=bill.bill_number)
                else:
                    session.add(bill)
                    saved_count += 1
                    log.debug("Added bill", bill_type=bill.bill_type, number=bill.bill_number)

            session.commit()
            log.info("Bills saved", new_count=saved_count, total=len(bills))

        except Exception as e:
            session.rollback()
            log.error("Failed to save bills", error=str(e))
            raise
        finally:
            session.close()

        return saved_count


def fetch_bills_for_date(target_date: date, fetch_details: bool = False) -> int:
    """Fetch and save bills updated on a specific date."""
    init_db()

    with BillFetcher() as fetcher:
        bills = fetcher.fetch_bills_for_date(target_date, fetch_details)
        if bills:
            return fetcher.save_bills(bills)
        else:
            log.info("No bills found", date=str(target_date))
            return 0
