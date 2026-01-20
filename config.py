"""Configuration management for Congress Tracker."""

import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env from package directory, not CWD
_package_dir = Path(__file__).parent
load_dotenv(_package_dir / ".env")


class Config(BaseModel):
    """Application configuration."""

    # API Keys
    congress_api_key: str = Field(default_factory=lambda: os.getenv("CONGRESS_API_KEY", ""))
    anthropic_api_key: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))

    # Bluesky credentials
    bluesky_handle: str = Field(default_factory=lambda: os.getenv("BLUESKY_HANDLE", ""))
    bluesky_password: str = Field(default_factory=lambda: os.getenv("BLUESKY_PASSWORD", ""))

    # Discord notifications
    discord_webhook_url: str = Field(default_factory=lambda: os.getenv("DISCORD_WEBHOOK_URL", ""))

    # Database
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            f"sqlite:///{Path(__file__).parent / 'congress.db'}"
        )
    )

    # API base URLs
    congress_api_base: str = "https://api.congress.gov/v3"

    # Summarization settings
    haiku_model: str = "claude-3-haiku-20240307"
    max_summary_tokens: int = 150

    # Bluesky thread settings
    bluesky_char_limit: int = 300
    max_thread_posts: int = 10


def get_config() -> Config:
    """Get application configuration."""
    return Config()
