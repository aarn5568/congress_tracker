#!/bin/bash
# post_midafternoon.sh - Mid-afternoon post batch (runs at 3:00 PM ET)
# Posts more bills

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

echo "$(date): Posting mid-afternoon batch (bills)..."

# Post up to 15 more items
python -m congress_tracker.cli publish-items --max-items 15

echo "$(date): Mid-afternoon batch complete."
