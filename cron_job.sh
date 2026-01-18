#!/bin/bash
# Congress Tracker Daily Cron Job
# Add to crontab: 0 6 * * * /path/to/congress_tracker/cron_job.sh >> /var/log/congress_tracker.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting Congress Tracker ETL"

# Run full ETL pipeline
python -m congress_tracker.cli run-etl

# Generate and publish digest
python -m congress_tracker.cli generate-digest
python -m congress_tracker.cli publish-digest

echo "$(date '+%Y-%m-%d %H:%M:%S') - Congress Tracker ETL complete"
