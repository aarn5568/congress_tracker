"""ETL module for fetching Congressional votes from Congress.gov API."""

import json
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_config
from models.database import Vote, VoteResult, Chamber, get_session, init_db

log = structlog.get_logger()


class VoteFetcher:
    """Fetches votes from Congress.gov API."""

    def __init__(self):
        self.config = get_config()
        self.client = httpx.Client(timeout=30.0)

    def close(self):
        """Close HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _parse_vote_result(self, result_str: str) -> VoteResult:
        """Parse vote result string to enum."""
        result_str = result_str.lower() if result_str else ""
        if "passed" in result_str:
            return VoteResult.PASSED
        elif "failed" in result_str:
            return VoteResult.FAILED
        elif "agreed" in result_str:
            return VoteResult.AGREED_TO
        elif "rejected" in result_str:
            return VoteResult.REJECTED
        return VoteResult.UNKNOWN

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_chamber_votes(self, congress: int, chamber: str) -> list[dict]:
        """Fetch votes for a specific congress/chamber."""
        if not self.config.congress_api_key:
            raise ValueError("Congress.gov API key not configured")

        votes = []
        offset = 0
        limit = 250

        # Endpoint is /house-vote or /senate-vote
        endpoint = f"{chamber}-vote"

        while True:
            url = f"{self.config.congress_api_base}/{endpoint}/{congress}"
            params = {
                "api_key": self.config.congress_api_key,
                "format": "json",
                "offset": offset,
                "limit": limit,
            }

            log.info("Fetching votes", congress=congress, chamber=chamber, offset=offset)
            response = self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            # Response key is "houseRollCallVotes" or "senateRollCallVotes"
            vote_key = f"{chamber}RollCallVotes"
            vote_list = data.get(vote_key, [])

            if not vote_list:
                break

            votes.extend(vote_list)
            offset += limit

            if len(vote_list) < limit:
                break

        return votes

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_vote_details(self, congress: int, chamber: str, roll_call: int) -> Optional[dict]:
        """Fetch detailed vote information."""
        url = f"{self.config.congress_api_base}/vote/{congress}/{chamber}/{roll_call}"
        params = {
            "api_key": self.config.congress_api_key,
            "format": "json",
        }

        response = self.client.get(url, params=params)
        if response.status_code == 404:
            return None
        response.raise_for_status()

        data = response.json()
        return data.get("vote")

    def _vote_to_model(self, vote_data: dict, chamber: Chamber) -> Optional[Vote]:
        """Convert Congress.gov vote data to Vote model."""
        try:
            # Parse date - API uses "startDate" field
            date_str = vote_data.get("startDate") or vote_data.get("updateDate")
            if not date_str:
                return None

            # Handle ISO format with timezone (e.g., "2025-09-08T18:56:00-04:00")
            vote_date = datetime.fromisoformat(date_str).date()

            # Build bill reference from legislationType + legislationNumber
            bill_id = None
            if vote_data.get("legislationType") and vote_data.get("legislationNumber"):
                bill_id = f"{vote_data['legislationType']}{vote_data['legislationNumber']}"

            # Extract amendment info
            amendment_number = vote_data.get("amendmentNumber")
            amendment_type = vote_data.get("amendmentType")
            amendment_author = vote_data.get("amendmentAuthor")

            vote = Vote(
                congress=vote_data.get("congress"),
                session=vote_data.get("sessionNumber", 1),
                chamber=chamber,
                roll_call=vote_data.get("rollCallNumber"),
                vote_date=vote_date,
                question=vote_data.get("question"),
                description=vote_data.get("description") or vote_data.get("title"),
                vote_type=vote_data.get("voteType"),
                result=self._parse_vote_result(vote_data.get("result", "")),
                bill_id=bill_id,
                bill_number=vote_data.get("legislationNumber"),
                amendment_number=amendment_number,
                amendment_type=amendment_type,
                amendment_author=amendment_author,
                source_url=vote_data.get("url"),
                raw_data=json.dumps(vote_data),
            )
            return vote
        except Exception as e:
            log.error("Failed to parse vote", error=str(e), data=vote_data)
            return None

    def fetch_votes_for_date(self, target_date: date) -> list[Vote]:
        """Fetch all votes for a specific date.

        Note: Congress.gov API currently only provides House votes.
        Senate vote data is not available through this API.
        """
        # Determine congress number (119th Congress started Jan 2025)
        year = target_date.year
        if year >= 2025:
            congress = 119
        elif year >= 2023:
            congress = 118
        else:
            congress = 117

        votes = []

        # Note: Only House votes available via Congress.gov API
        # Senate endpoint (/senate-vote) does not exist
        try:
            chamber_votes = self._fetch_chamber_votes(congress, "house")
            log.info("Fetched chamber votes", chamber="house", total=len(chamber_votes))

            for vote_data in chamber_votes:
                # Filter by date using startDate field
                date_str = vote_data.get("startDate", "")
                if date_str:
                    vote_dt = datetime.fromisoformat(date_str).date()
                    if vote_dt == target_date:
                        vote = self._vote_to_model(vote_data, Chamber.HOUSE)
                        if vote:
                            votes.append(vote)

        except Exception as e:
            log.error("Failed to fetch House votes", error=str(e))

        log.info("Votes matched for date", count=len(votes), date=str(target_date))
        return votes

    def save_votes(self, votes: list[Vote]) -> int:
        """Save votes to database, avoiding duplicates."""
        session = get_session()
        saved_count = 0

        try:
            for vote in votes:
                # Check for existing vote
                existing = session.query(Vote).filter(
                    Vote.congress == vote.congress,
                    Vote.chamber == vote.chamber,
                    Vote.roll_call == vote.roll_call,
                    Vote.vote_date == vote.vote_date,
                ).first()

                if not existing:
                    session.add(vote)
                    saved_count += 1
                    log.debug(
                        "Saved vote",
                        chamber=vote.chamber.value,
                        roll_call=vote.roll_call,
                        date=str(vote.vote_date),
                    )
                else:
                    log.debug(
                        "Vote already exists",
                        chamber=vote.chamber.value,
                        roll_call=vote.roll_call,
                    )

            session.commit()
            log.info("Votes saved to database", new_count=saved_count, total=len(votes))

        except Exception as e:
            session.rollback()
            log.error("Failed to save votes", error=str(e))
            raise
        finally:
            session.close()

        return saved_count


def fetch_yesterday_votes() -> int:
    """Fetch and save yesterday's votes."""
    yesterday = date.today() - timedelta(days=1)
    return fetch_votes_for_date(yesterday)


def fetch_votes_for_date(target_date: date) -> int:
    """Fetch and save votes for a specific date."""
    init_db()

    with VoteFetcher() as fetcher:
        votes = fetcher.fetch_votes_for_date(target_date)
        if votes:
            return fetcher.save_votes(votes)
        else:
            log.info("No votes found", date=str(target_date))
            return 0


if __name__ == "__main__":
    import sys

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    if len(sys.argv) > 1:
        target = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    else:
        target = date.today() - timedelta(days=1)

    print(f"Fetching votes for {target}...")
    count = fetch_votes_for_date(target)
    print(f"Saved {count} new votes.")
