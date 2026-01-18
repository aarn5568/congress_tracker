"""ETL module for Congressional Record floor speeches.

Note: The Congress.gov API provides Congressional Record metadata and PDF links,
but not structured text content for individual speeches. Full speech extraction
would require PDF parsing or using the GPO's GovInfo API for granule-level data.

This module provides basic Congressional Record issue tracking.
"""

import json
from datetime import date, datetime
from typing import Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from congress_tracker.config import get_config
from congress_tracker.models.database import FloorSpeech, Chamber, get_session, init_db

log = structlog.get_logger()


class CongressionalRecordFetcher:
    """Fetches Congressional Record data from Congress.gov API."""

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
    def _fetch_daily_record(self, target_date: date) -> Optional[dict]:
        """Fetch Congressional Record for a specific date."""
        if not self.config.congress_api_key:
            raise ValueError("Congress.gov API key not configured")

        year = target_date.year
        month = target_date.month
        day = target_date.day

        url = f"{self.config.congress_api_base}/congressional-record/{year}/{month}/{day}"
        params = {
            "api_key": self.config.congress_api_key,
            "format": "json",
        }

        log.info("Fetching Congressional Record", date=str(target_date))
        response = self.client.get(url, params=params)

        if response.status_code == 404:
            log.info("No Congressional Record for date", date=str(target_date))
            return None

        response.raise_for_status()
        return response.json()

    def fetch_record_for_date(self, target_date: date) -> dict:
        """Fetch Congressional Record metadata for a specific date.

        Returns dict with record info and PDF links for House/Senate sections.
        Actual speech text extraction requires PDF parsing (not implemented).
        """
        try:
            record = self._fetch_daily_record(target_date)
            if record:
                log.info("Found Congressional Record", date=str(target_date))
                return record
        except Exception as e:
            log.error("Failed to fetch Congressional Record", error=str(e))

        return {}


def fetch_speeches_for_date(target_date: date) -> int:
    """Fetch Congressional Record for a date.

    Note: Returns count of records found, not individual speeches.
    Speech extraction from PDFs is not yet implemented.
    """
    init_db()

    with CongressionalRecordFetcher() as fetcher:
        record = fetcher.fetch_record_for_date(target_date)
        if record:
            log.info("Congressional Record available", date=str(target_date),
                     has_record=bool(record))
            return 1
        return 0
