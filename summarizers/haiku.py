"""Claude Haiku summarization for bills and speeches."""

from typing import Optional

import anthropic
import structlog

from config import get_config

log = structlog.get_logger()


class HaikuSummarizer:
    """Summarizes Congressional content using Claude Haiku."""

    def __init__(self):
        self.config = get_config()
        if not self.config.anthropic_api_key:
            raise ValueError("Anthropic API key not configured")
        self.client = anthropic.Anthropic(api_key=self.config.anthropic_api_key)

    def summarize_bill(self, title: str, full_text: Optional[str] = None,
                       latest_action: Optional[str] = None) -> str:
        """Generate a concise summary of a bill.

        Args:
            title: Bill title
            full_text: Full bill text (if available)
            latest_action: Latest action text

        Returns:
            Summary string suitable for social media (under 280 chars)
        """
        content = f"Bill Title: {title}\n"
        if latest_action:
            content += f"Latest Action: {latest_action}\n"
        if full_text:
            # Truncate to avoid token limits
            content += f"Bill Text (excerpt): {full_text[:3000]}\n"

        prompt = f"""Summarize this Congressional bill in 1-2 sentences (max 200 characters).
Focus on: what it does, who it affects, and its current status.
Be factual and neutral. No hashtags.

{content}

Summary:"""

        try:
            response = self.client.messages.create(
                model=self.config.haiku_model,
                max_tokens=self.config.max_summary_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            summary = response.content[0].text.strip()
            log.debug("Generated bill summary", title=title[:50], summary_len=len(summary))
            return summary
        except Exception as e:
            log.error("Failed to summarize bill", error=str(e), title=title[:50])
            return ""

    def summarize_speech(self, speaker: str, title: Optional[str],
                         content: str) -> str:
        """Generate a concise summary of a floor speech.

        Args:
            speaker: Speaker name and party
            title: Speech title/topic
            content: Speech text

        Returns:
            Summary string suitable for social media
        """
        text = f"Speaker: {speaker}\n"
        if title:
            text += f"Topic: {title}\n"
        text += f"Speech (excerpt): {content[:3000]}\n"

        prompt = f"""Summarize this Congressional floor speech in 1-2 sentences (max 200 characters).
Focus on: the main argument or announcement, and any specific bills/policies mentioned.
Be factual and neutral. No hashtags.

{text}

Summary:"""

        try:
            response = self.client.messages.create(
                model=self.config.haiku_model,
                max_tokens=self.config.max_summary_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            summary = response.content[0].text.strip()
            log.debug("Generated speech summary", speaker=speaker, summary_len=len(summary))
            return summary
        except Exception as e:
            log.error("Failed to summarize speech", error=str(e), speaker=speaker)
            return ""

    def summarize_vote(self, question: str, result: str,
                       bill_title: Optional[str] = None) -> str:
        """Generate a concise summary of a vote.

        Args:
            question: The question voted on
            result: Vote result (passed/failed)
            bill_title: Associated bill title if any

        Returns:
            Summary string suitable for social media
        """
        content = f"Vote Question: {question}\n"
        content += f"Result: {result}\n"
        if bill_title:
            content += f"Related Bill: {bill_title}\n"

        prompt = f"""Summarize this Congressional vote in 1 sentence (max 150 characters).
Include the result and what was voted on. Be factual.

{content}

Summary:"""

        try:
            response = self.client.messages.create(
                model=self.config.haiku_model,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )
            summary = response.content[0].text.strip()
            return summary
        except Exception as e:
            log.error("Failed to summarize vote", error=str(e))
            return ""


def get_summarizer() -> Optional[HaikuSummarizer]:
    """Get summarizer instance if API key is configured."""
    config = get_config()
    if not config.anthropic_api_key:
        log.warning("Anthropic API key not configured, summarization disabled")
        return None
    return HaikuSummarizer()
