#!/bin/bash
# daily_workflow.sh - All-in-one daily workflow
# Alternative to separate cron jobs - fetches and posts with delays between batches
# Run this once per day at 10:30 AM ET and it handles everything

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

echo "$(date): Starting daily workflow..."

# Step 1: Fetch all data
echo "$(date): Fetching data..."
python -m congress_tracker.cli run-etl
echo "$(date): Fetch complete."

# Optional: Summarize bills (uses Claude API tokens)
# python -m congress_tracker.cli summarize --bills --limit 20

# Step 2: Wait 30 minutes, then post first batch (11:00 AM)
echo "$(date): Waiting 30 minutes before first post batch..."
sleep 1800

echo "$(date): Posting batch 1/5 (10 items)..."
python -m congress_tracker.cli publish-items --max-items 10

# Step 3: Wait 2 hours, post second batch (1:00 PM)
echo "$(date): Waiting 2 hours before second post batch..."
sleep 7200

echo "$(date): Posting batch 2/5 (15 items)..."
python -m congress_tracker.cli publish-items --max-items 15

# Step 4: Wait 2 hours, post third batch (3:00 PM)
echo "$(date): Waiting 2 hours before third post batch..."
sleep 7200

echo "$(date): Posting batch 3/5 (15 items)..."
python -m congress_tracker.cli publish-items --max-items 15

# Step 5: Wait 2 hours, post fourth batch (5:00 PM)
echo "$(date): Waiting 2 hours before fourth post batch..."
sleep 7200

echo "$(date): Posting batch 4/5 (10 items)..."
python -m congress_tracker.cli publish-items --max-items 10

# Step 6: Wait 2 hours, post catch-all batch (7:00 PM)
echo "$(date): Waiting 2 hours before final catch-all batch..."
sleep 7200

echo "$(date): Posting batch 5/5 (20 items, catch-all)..."
python -m congress_tracker.cli publish-items --max-items 20

echo "$(date): Daily workflow complete!"
