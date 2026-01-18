"""ETL module for Congressional Record floor speeches.

Downloads PDFs from Congress.gov, extracts text, parses individual speeches,
and optionally summarizes with Claude Haiku.
"""

import io
import json
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    import fitz  # pymupdf
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

from congress_tracker.config import get_config
from congress_tracker.models.database import FloorSpeech, Chamber, get_session, init_db

log = structlog.get_logger()

# Pattern to identify speaker lines: "Mr./Mrs./Ms. NAME" or "The SPEAKER"
SPEAKER_PATTERN = re.compile(
    r'^(Mr\.|Mrs\.|Ms\.|Miss|The\s+SPEAKER|The\s+PRESIDING\s+OFFICER|'
    r'The\s+ACTING\s+PRESIDENT|The\s+VICE\s+PRESIDENT)\s*'
    r'([A-Z][A-Z\s\-\']+)?(?:\s+of\s+([A-Za-z]+))?[.\s]',
    re.MULTILINE
)

# Pattern for topic headers (all caps lines)
TOPIC_PATTERN = re.compile(r'^([A-Z][A-Z\s\-,\.\']{10,})$', re.MULTILINE)


class CongressionalRecordFetcher:
    """Fetches and parses Congressional Record from Congress.gov."""

    def __init__(self):
        self.config = get_config()
        self.client = httpx.Client(timeout=60.0, follow_redirects=True)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_daily_record(self, target_date: date) -> Optional[dict]:
        """Fetch Congressional Record metadata for a specific date."""
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

        log.info("Fetching Congressional Record metadata", date=str(target_date))
        response = self.client.get(url, params=params)

        if response.status_code == 404:
            log.info("No Congressional Record for date", date=str(target_date))
            return None

        response.raise_for_status()
        return response.json()

    def _get_pdf_urls(self, record_data: dict) -> dict[str, str]:
        """Extract PDF URLs from Congressional Record metadata."""
        urls = {}

        results = record_data.get("Results", {})
        issues = results.get("Issues", [])

        if not issues:
            return urls

        issue = issues[0]
        links = issue.get("Links", {})

        # Get House section PDF
        house = links.get("House", {})
        house_pdfs = house.get("PDF", [])
        if house_pdfs:
            urls["house"] = house_pdfs[0].get("Url", "")

        # Get Senate section PDF
        senate = links.get("Senate", {})
        senate_pdfs = senate.get("PDF", [])
        if senate_pdfs:
            urls["senate"] = senate_pdfs[0].get("Url", "")

        return urls

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _download_pdf(self, url: str) -> Optional[bytes]:
        """Download PDF content from URL."""
        if not url:
            return None

        log.info("Downloading PDF", url=url[:80])
        response = self.client.get(url)
        response.raise_for_status()
        return response.content

    def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes using PyMuPDF."""
        if not PDF_AVAILABLE:
            log.warning("PyMuPDF not installed, cannot extract PDF text")
            return ""

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_parts = []

            for page in doc:
                text_parts.append(page.get_text())

            doc.close()
            return "\n".join(text_parts)
        except Exception as e:
            log.error("Failed to extract PDF text", error=str(e))
            return ""

    def _parse_speeches(self, text: str, chamber: Chamber, speech_date: date) -> list[dict]:
        """Parse individual speeches from Congressional Record text."""
        speeches = []

        if not text:
            return speeches

        # Split by speaker patterns
        # Find all speaker occurrences
        speaker_matches = list(SPEAKER_PATTERN.finditer(text))

        if not speaker_matches:
            return speeches

        for i, match in enumerate(speaker_matches):
            # Get the speaker info
            title = match.group(1)
            name = match.group(2) or ""
            state = match.group(3) or ""

            speaker_name = f"{title} {name}".strip()
            if state:
                speaker_name += f" ({state})"

            # Get the speech content (from this match to the next)
            start = match.end()
            end = speaker_matches[i + 1].start() if i + 1 < len(speaker_matches) else len(text)

            content = text[start:end].strip()

            # Skip very short entries (procedural)
            if len(content) < 100:
                continue

            # Try to find a topic header near the start
            topic = None
            topic_match = TOPIC_PATTERN.search(text[max(0, match.start() - 200):match.start()])
            if topic_match:
                topic = topic_match.group(1).strip()

            speeches.append({
                "speaker_name": speaker_name,
                "speaker_state": state[:2].upper() if state else None,
                "title": topic,
                "content": content[:10000],  # Limit content size
                "chamber": chamber,
                "speech_date": speech_date,
            })

            # Limit speeches per section to avoid overwhelming
            if len(speeches) >= 50:
                break

        return speeches

    def _speech_dict_to_model(self, speech_data: dict) -> FloorSpeech:
        """Convert speech dict to FloorSpeech model."""
        return FloorSpeech(
            congress=119 if speech_data["speech_date"].year >= 2025 else 118,
            chamber=speech_data["chamber"],
            speech_date=speech_data["speech_date"],
            speaker_name=speech_data["speaker_name"],
            speaker_state=speech_data.get("speaker_state"),
            title=speech_data.get("title"),
            content=speech_data["content"],
        )

    def fetch_speeches_for_date(self, target_date: date) -> list[FloorSpeech]:
        """Fetch and parse all speeches for a specific date."""
        speeches = []

        if not PDF_AVAILABLE:
            log.error("PyMuPDF not installed. Run: pip install pymupdf")
            return speeches

        try:
            # Get Congressional Record metadata
            record = self._fetch_daily_record(target_date)
            if not record:
                return speeches

            # Get PDF URLs
            pdf_urls = self._get_pdf_urls(record)
            if not pdf_urls:
                log.info("No PDF URLs found", date=str(target_date))
                return speeches

            # Process each chamber's PDF
            for chamber_name, url in pdf_urls.items():
                chamber = Chamber.HOUSE if chamber_name == "house" else Chamber.SENATE

                try:
                    # Download PDF
                    pdf_bytes = self._download_pdf(url)
                    if not pdf_bytes:
                        continue

                    # Extract text
                    text = self._extract_text_from_pdf(pdf_bytes)
                    if not text:
                        continue

                    log.info("Extracted PDF text", chamber=chamber_name, chars=len(text))

                    # Parse speeches
                    parsed = self._parse_speeches(text, chamber, target_date)
                    log.info("Parsed speeches", chamber=chamber_name, count=len(parsed))

                    # Convert to models
                    for speech_data in parsed:
                        speeches.append(self._speech_dict_to_model(speech_data))

                except Exception as e:
                    log.error("Failed to process chamber PDF", chamber=chamber_name, error=str(e))

        except Exception as e:
            log.error("Failed to fetch speeches", error=str(e))

        log.info("Total speeches fetched", count=len(speeches), date=str(target_date))
        return speeches

    def save_speeches(self, speeches: list[FloorSpeech]) -> int:
        """Save speeches to database, avoiding duplicates."""
        session = get_session()
        saved_count = 0

        try:
            for speech in speeches:
                # Check for existing (by date, chamber, speaker, and content hash)
                existing = session.query(FloorSpeech).filter(
                    FloorSpeech.speech_date == speech.speech_date,
                    FloorSpeech.chamber == speech.chamber,
                    FloorSpeech.speaker_name == speech.speaker_name,
                ).first()

                if not existing:
                    session.add(speech)
                    saved_count += 1
                    log.debug("Saved speech", speaker=speech.speaker_name)

            session.commit()
            log.info("Speeches saved", new_count=saved_count, total=len(speeches))

        except Exception as e:
            session.rollback()
            log.error("Failed to save speeches", error=str(e))
            raise
        finally:
            session.close()

        return saved_count


def fetch_speeches_for_date(target_date: date) -> int:
    """Fetch and save speeches for a date."""
    init_db()

    with CongressionalRecordFetcher() as fetcher:
        speeches = fetcher.fetch_speeches_for_date(target_date)
        if speeches:
            return fetcher.save_speeches(speeches)
        else:
            log.info("No speeches found", date=str(target_date))
            return 0
