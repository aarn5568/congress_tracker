#!/bin/bash
# post_morning.sh - Morning post batch (runs at 11:00 AM ET)
# Posts high-priority votes first

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

echo "$(date): Posting morning batch (votes)..."

# Post up to 10 votes from yesterday
python -m congress_tracker.cli publish-items --max-items 10

echo "$(date): Morning batch complete."
