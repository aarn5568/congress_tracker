#!/bin/bash
# fetch_daily.sh - Morning data fetch (runs at 10:30 AM ET)
# Fetches votes, bills, and speeches from yesterday after Congress.gov updates

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "$(date): Starting daily fetch..."

# Run full ETL pipeline for yesterday
python -m congress_tracker.cli run-etl

# Optional: Summarize bills without CRS summaries (uses Claude API tokens)
# Uncomment if you want automatic summarization
# python -m congress_tracker.cli summarize --bills --limit 20

echo "$(date): Fetch complete."
