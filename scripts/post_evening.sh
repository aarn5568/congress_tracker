#!/bin/bash
# post_evening.sh - Evening post batch (runs at 5:00 PM ET)
# Posts speeches and remaining items

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

echo "$(date): Posting evening batch (speeches)..."

# Post up to 10 more items (likely speeches)
python -m congress_tracker.cli publish-items --max-items 10

echo "$(date): Evening batch complete."
