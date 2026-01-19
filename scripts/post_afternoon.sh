#!/bin/bash
# post_afternoon.sh - Afternoon post batch (runs at 1:00 PM ET)
# Posts remaining votes and bills

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

echo "$(date): Posting afternoon batch (votes + bills)..."

# Post up to 15 more items
python -m congress_tracker.cli publish-items --max-items 15

echo "$(date): Afternoon batch complete."
