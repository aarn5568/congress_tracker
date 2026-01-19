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

- Docker & Docker Compose (recommended) OR Python 3.10+
- Congress.gov API key (free: https://api.congress.gov/)
- Anthropic API key (for summarization, optional)
- Bluesky account (for publishing, optional)

## Installation

### Option 1: Docker (Recommended) 🐳

**Easiest setup with automatic scheduling included!**

```bash
# Clone the repository
git clone https://github.com/yourusername/congress_tracker.git
cd congress_tracker

# Configure environment
cp .env.example .env
nano .env  # Add your API keys

# Start scheduler
docker-compose up -d scheduler

# View logs
docker-compose logs -f scheduler
```

**Done!** The scheduler is now running and will automatically fetch and post throughout the day.

See [DOCKER.md](DOCKER.md) for complete Docker documentation.

### Option 2: Native Python Installation

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

### Docker Quick Reference

If using Docker, prefix commands with `docker-compose run --rm cli`:

```bash
# Fetch data
docker-compose run --rm cli run-etl

# Post items
docker-compose run --rm cli publish-items --dry-run

# Show stats
docker-compose run --rm cli show-stats

# Or use the helper script
./docker/docker-helper.sh fetch
./docker/docker-helper.sh post --dry-run
./docker/docker-helper.sh stats
```

See [DOCKER.md](DOCKER.md) for complete Docker usage.

## Automated Scheduling

### Docker: Automatic (Easiest)

If using Docker, scheduling is **built-in and automatic**:

```bash
# Start scheduler (runs in background)
docker-compose up -d scheduler

# View logs to verify
docker-compose logs -f scheduler
```

The scheduler automatically:
- Fetches data at 10:30 AM ET
- Posts in 5 batches from 11 AM - 7 PM ET
- Handles timezone conversion
- Restarts on system reboot (with `restart: unless-stopped`)

See [DOCKER.md](DOCKER.md) to customize the schedule.

---

### Native Installation Options

For non-Docker installations, choose one of these scheduling approaches:

### Option 1: Optimal Staggered Schedule (Recommended)

This approach fetches data once daily and spreads posts throughout the day to avoid flooding followers.

**Why this schedule?**
- Congress.gov updates at **10:00 AM ET** daily
- Posts spread over 8 hours (11 AM - 7 PM) for optimal engagement
- Prevents follower fatigue from too many posts at once

**Timeline:**
- **10:30 AM ET**: Fetch all data (after Congress.gov updates)
- **11:00 AM ET**: Post batch 1 (10 items - votes priority)
- **1:00 PM ET**: Post batch 2 (15 items)
- **3:00 PM ET**: Post batch 3 (15 items)
- **5:00 PM ET**: Post batch 4 (10 items - speeches)
- **7:00 PM ET**: Post batch 5 (20 items - catch-all)

**Total: Up to 70 items/day spread over 8 hours**

```bash
# Copy and customize the crontab template
cp scripts/crontab.example scripts/crontab.local

# Edit paths in crontab.local to match your system
nano scripts/crontab.local

# Install the crontab
crontab scripts/crontab.local

# Verify installation
crontab -l
```

### Option 2: Single Daily Job (Simpler)

If you prefer one long-running job that handles everything:

```bash
# Run once per day at 10:30 AM ET
30 10 * * * /path/to/congress_tracker/scripts/daily_workflow.sh >> /var/log/congress_tracker.log 2>&1
```

This script fetches data and automatically posts in batches with delays between them.

### Option 3: Manual Execution

For testing or manual control:

```bash
# Fetch data
./scripts/fetch_daily.sh

# Post in batches throughout the day
./scripts/post_morning.sh
# Wait 2 hours...
./scripts/post_afternoon.sh
# Wait 2 hours...
./scripts/post_midafternoon.sh
# Wait 2 hours...
./scripts/post_evening.sh
# Wait 2 hours...
./scripts/post_catchall.sh
```

### Legacy: Simple Daily Job

Old approach (fetches and posts everything at once):

```bash
0 6 * * * /path/to/congress_tracker/cron_job.sh >> /var/log/congress_tracker.log 2>&1
```

## Project Structure

```
congress_tracker/
├── cli.py                    # Command-line interface
├── config.py                 # Configuration management
├── cron_job.sh               # Legacy cron wrapper script
├── scripts/                  # Scheduling scripts (NEW!)
│   ├── fetch_daily.sh        # Morning data fetch
│   ├── post_morning.sh       # 11 AM batch
│   ├── post_afternoon.sh     # 1 PM batch
│   ├── post_midafternoon.sh  # 3 PM batch
│   ├── post_evening.sh       # 5 PM batch
│   ├── post_catchall.sh      # 7 PM batch
│   ├── daily_workflow.sh     # All-in-one alternative
│   └── crontab.example       # Crontab template
├── etl/
│   ├── votes.py              # Vote fetching from Congress.gov
│   ├── bills.py              # Bill fetching
│   └── speeches.py           # Congressional Record (metadata only)
├── models/
│   └── database.py           # SQLAlchemy models
├── formatters/
│   └── bluesky.py            # Bluesky formatting & publishing
├── summarizers/
│   └── haiku.py              # Claude Haiku summarization
└── utils/
```

## Data Update Timing

**Congress.gov Update Schedule:**
- Congress.gov is updated **once per day at 10:00 AM ET**
- Data reflects activity from the previous day's House/Senate sessions
- Running the ETL more than once per day is unnecessary - the data won't change

**Optimal Fetch Time:** 10:30 AM ET or later

**Why Stagger Posts?**
- Posting 50+ items at once can overwhelm followers
- Spreading posts over 8 hours increases visibility and engagement
- Allows followers in different time zones to see content

## API Limitations

- **House votes only**: Congress.gov API currently only provides House roll call votes. Senate vote data is not available through this API.
- **Congressional Record**: API provides metadata and PDF links, not extracted speech text.
- **Rate limits**: Congress.gov API limit is 5,000 requests/hour (you'll use ~100/day).

## Data Sources

- [Congress.gov API](https://api.congress.gov/) - Official Congressional data
- Vote data includes: roll call number, date, result, bill reference
- Bill data includes: title, sponsor, latest action, policy area

## License

MIT License

## Contributing

Contributions welcome! Please open an issue or submit a PR.
