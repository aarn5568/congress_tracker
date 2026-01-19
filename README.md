# Congress Tracker

A Python tool that fetches Congressional activity (votes, bills) from Congress.gov and publishes daily digests to Bluesky.

## Features

- **Vote Tracking**: Fetches House roll call votes from Congress.gov API
- **Bill Tracking**: Monitors bill updates and latest actions
- **AI Summarization**: Uses Claude Haiku to summarize bills without CRS summaries
- **Bluesky Integration**: Publish as threaded digests OR individual posts per item
- **Individual Posts**: Each bill, vote, and speech can be posted separately (NEW!)
- **SQLite Storage**: Local database for historical tracking
- **Cron Ready**: Designed to run as a daily scheduled job

## Requirements

- Python 3.10+
- Congress.gov API key (free: https://api.congress.gov/)
- Anthropic API key (for summarization, optional)
- Bluesky account (for publishing, optional)

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/congress_tracker.git
cd congress_tracker

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

## Configuration

Edit `.env` with your credentials:

```env
CONGRESS_API_KEY=your_congress_api_key
ANTHROPIC_API_KEY=your_anthropic_key  # Optional, for summarization
BLUESKY_HANDLE=yourhandle.bsky.social  # Optional, for publishing
BLUESKY_PASSWORD=your_app_password     # Optional, use app password
```

## Usage

```bash
# Initialize database
python -m congress_tracker.cli init-db

# Fetch yesterday's votes
python -m congress_tracker.cli fetch-votes

# Fetch votes for specific date
python -m congress_tracker.cli fetch-votes --date 2025-09-08

# Fetch bills updated on a date
python -m congress_tracker.cli fetch-bills --date 2025-09-08

# Run full ETL (votes + bills)
python -m congress_tracker.cli run-etl --date 2025-09-08

# Generate digest (preview)
python -m congress_tracker.cli generate-digest --date 2025-09-08

# Publish to Bluesky
python -m congress_tracker.cli publish-digest --date 2025-09-08

# Dry run (preview without publishing)
python -m congress_tracker.cli publish-digest --date 2025-09-08 --dry-run

# Publish individual posts (NEW! - separate post for each item)
python -m congress_tracker.cli publish-items --date 2025-09-08

# Publish individual posts with limit
python -m congress_tracker.cli publish-items --date 2025-09-08 --max-items 10

# Preview individual posts
python -m congress_tracker.cli publish-items --date 2025-09-08 --dry-run

# Show database statistics
python -m congress_tracker.cli show-stats
```

## Cron Setup

Add to crontab for daily execution at 6 AM:

```bash
crontab -e
# Add:
0 6 * * * /path/to/congress_tracker/cron_job.sh >> /var/log/congress_tracker.log 2>&1
```

## Project Structure

```
congress_tracker/
├── cli.py              # Command-line interface
├── config.py           # Configuration management
├── cron_job.sh         # Cron wrapper script
├── etl/
│   ├── votes.py        # Vote fetching from Congress.gov
│   ├── bills.py        # Bill fetching
│   └── speeches.py     # Congressional Record (metadata only)
├── models/
│   └── database.py     # SQLAlchemy models
├── formatters/
│   └── bluesky.py      # Bluesky thread formatting
├── summarizers/
│   └── haiku.py        # Claude Haiku summarization
└── utils/
```

## API Limitations

- **House votes only**: Congress.gov API currently only provides House roll call votes. Senate vote data is not available through this API.
- **Congressional Record**: API provides metadata and PDF links, not extracted speech text.
- **Rate limits**: Congress.gov has rate limits; the ETL includes retry logic with exponential backoff.

## Data Sources

- [Congress.gov API](https://api.congress.gov/) - Official Congressional data
- Vote data includes: roll call number, date, result, bill reference
- Bill data includes: title, sponsor, latest action, policy area

## License

MIT License

## Contributing

Contributions welcome! Please open an issue or submit a PR.
