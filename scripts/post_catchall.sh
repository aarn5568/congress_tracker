#!/bin/bash
# post_catchall.sh - Late evening catch-all (runs at 7:00 PM ET)
# Posts any remaining unposted items from the day

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

echo "$(date): Posting catch-all batch (any remaining items)..."

# Post up to 20 remaining items to finish the day
python -m congress_tracker.cli publish-items --max-items 20

echo "$(date): Catch-all batch complete."
