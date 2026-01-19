"""Discord notification support for Congress Tracker."""

from datetime import datetime
from typing import Optional
import httpx
import structlog

from config import get_config

log = structlog.get_logger()


class DiscordNotifier:
    """Send notifications to Discord via webhook."""

    def __init__(self):
        self.config = get_config()
        self.webhook_url = self.config.discord_webhook_url

    def is_configured(self) -> bool:
        """Check if Discord notifications are configured."""
        return bool(self.webhook_url)

    def send(self, title: str, message: str, color: int = 0x5865F2,
             fields: Optional[list[dict]] = None) -> bool:
        """Send a Discord embed message.

        Args:
            title: Embed title
            message: Main message text
            color: Embed color (default: Discord blurple)
            fields: Optional list of field dicts with 'name' and 'value'

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_configured():
            log.debug("Discord webhook not configured, skipping notification")
            return False

        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Congress Tracker"}
        }

        if fields:
            embed["fields"] = fields

        payload = {"embeds": [embed]}

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(self.webhook_url, json=payload)
                response.raise_for_status()
                log.info("Discord notification sent", title=title)
                return True
        except Exception as e:
            log.error("Failed to send Discord notification", error=str(e))
            return False

    def notify_etl_complete(self, date_str: str, votes: int, bills: int, speeches: int):
        """Notify about ETL completion."""
        if votes == 0 and bills == 0 and speeches == 0:
            self.send(
                title="📊 ETL Complete - No Data",
                message=f"No congressional activity found for **{date_str}**",
                color=0x95A5A6,  # Gray
            )
        else:
            self.send(
                title="📊 ETL Complete",
                message=f"Fetched congressional data for **{date_str}**",
                color=0x2ECC71,  # Green
                fields=[
                    {"name": "🗳️ Votes", "value": str(votes), "inline": True},
                    {"name": "📜 Bills", "value": str(bills), "inline": True},
                    {"name": "🎤 Speeches", "value": str(speeches), "inline": True},
                ]
            )

    def notify_summarize_complete(self, date_str: str, summaries: int):
        """Notify about summarization completion."""
        if summaries == 0:
            self.send(
                title="🤖 Summarization Complete",
                message=f"No new content to summarize for **{date_str}**",
                color=0x95A5A6,  # Gray
            )
        else:
            self.send(
                title="🤖 Summarization Complete",
                message=f"Generated **{summaries}** AI summaries for **{date_str}**",
                color=0x9B59B6,  # Purple
            )

    def notify_publish_complete(self, date_str: str, stats: dict):
        """Notify about publishing completion."""
        bills = stats.get("bills", 0)
        votes = stats.get("total_votes", 0)
        speeches = stats.get("total_speeches", 0)
        errors = stats.get("errors", 0)

        if bills == 0 and errors == 0:
            self.send(
                title="📤 Publishing Complete",
                message=f"No new bill threads to publish for **{date_str}**",
                color=0x95A5A6,  # Gray
            )
        elif errors > 0 and bills == 0:
            self.send(
                title="❌ Publishing Failed",
                message=f"Failed to publish threads for **{date_str}**",
                color=0xE74C3C,  # Red
                fields=[
                    {"name": "Errors", "value": str(errors), "inline": True},
                ]
            )
        else:
            color = 0x3498DB if errors == 0 else 0xF39C12  # Blue or Orange
            title = "📤 Publishing Complete" if errors == 0 else "⚠️ Publishing Complete (with errors)"

            self.send(
                title=title,
                message=f"Published bill threads for **{date_str}**",
                color=color,
                fields=[
                    {"name": "📜 Bill Threads", "value": str(bills), "inline": True},
                    {"name": "🗳️ Votes", "value": str(votes), "inline": True},
                    {"name": "🎤 Speeches", "value": str(speeches), "inline": True},
                    {"name": "❌ Errors", "value": str(errors), "inline": True},
                ]
            )

    def notify_error(self, command: str, error: str):
        """Notify about an error."""
        self.send(
            title=f"❌ Error in {command}",
            message=f"```\n{error[:1000]}\n```",
            color=0xE74C3C,  # Red
        )


def get_notifier() -> DiscordNotifier:
    """Get Discord notifier instance."""
    return DiscordNotifier()
