# Scheduling Scripts

This directory contains automation scripts for fetching and posting Congressional data throughout the day.

## Overview

Congress.gov updates **once per day at 10:00 AM ET** with the previous day's activity. These scripts implement an optimal schedule that:

1. Fetches data once after the update (10:30 AM ET)
2. Spreads posts over 8 hours (11 AM - 7 PM ET) to avoid flooding followers
3. Posts up to 70 items/day in 5 batches

## Scripts

### Data Fetching

- **`fetch_daily.sh`** - Fetches votes, bills, and speeches from yesterday
  - Run time: 10:30 AM ET
  - Duration: ~2-5 minutes

### Staggered Posting

- **`post_morning.sh`** - Posts first batch (10 items, votes priority)
  - Run time: 11:00 AM ET

- **`post_afternoon.sh`** - Posts second batch (15 items)
  - Run time: 1:00 PM ET

- **`post_midafternoon.sh`** - Posts third batch (15 items)
  - Run time: 3:00 PM ET

- **`post_evening.sh`** - Posts fourth batch (10 items, speeches)
  - Run time: 5:00 PM ET

- **`post_catchall.sh`** - Posts final batch (20 items, any remaining)
  - Run time: 7:00 PM ET

### All-in-One

- **`daily_workflow.sh`** - Single script that handles fetching and all posting batches
  - Run time: 10:30 AM ET
  - Duration: ~8.5 hours (includes sleep delays)
  - Use this if you prefer a single cron job

## Setup

### Option 1: Multiple Cron Jobs (Recommended)

This gives you more control and better logging:

```bash
# 1. Copy the crontab template
cp crontab.example crontab.local

# 2. Edit paths to match your system
nano crontab.local

# 3. Install the crontab
crontab crontab.local

# 4. Verify
crontab -l
```

The crontab will look like this (adjust for your timezone):

```cron
# 10:30 AM ET - Fetch data
30 10 * * * /path/to/congress_tracker/scripts/fetch_daily.sh >> /var/log/congress_tracker/fetch.log 2>&1

# 11:00 AM ET - Post batch 1
0 11 * * * /path/to/congress_tracker/scripts/post_morning.sh >> /var/log/congress_tracker/post_morning.log 2>&1

# 1:00 PM ET - Post batch 2
0 13 * * * /path/to/congress_tracker/scripts/post_afternoon.sh >> /var/log/congress_tracker/post_afternoon.log 2>&1

# 3:00 PM ET - Post batch 3
0 15 * * * /path/to/congress_tracker/scripts/post_midafternoon.sh >> /var/log/congress_tracker/post_midafternoon.log 2>&1

# 5:00 PM ET - Post batch 4
0 17 * * * /path/to/congress_tracker/scripts/post_evening.sh >> /var/log/congress_tracker/post_evening.log 2>&1

# 7:00 PM ET - Post batch 5
0 19 * * * /path/to/congress_tracker/scripts/post_catchall.sh >> /var/log/congress_tracker/post_catchall.log 2>&1
```

### Option 2: Single Cron Job (Simpler)

Use the all-in-one script:

```bash
# Add to crontab
30 10 * * * /path/to/congress_tracker/scripts/daily_workflow.sh >> /var/log/congress_tracker.log 2>&1
```

**Note:** This script will run for ~8.5 hours. Make sure your cron daemon allows long-running jobs.

## Manual Testing

Test individual scripts before automating:

```bash
# Test fetching (safe, no posting)
./fetch_daily.sh

# Test posting with dry run (safe, shows what would be posted)
cd ..
python -m congress_tracker.cli publish-items --dry-run --max-items 10

# Test actual posting (will post to Bluesky!)
./post_morning.sh
```

## Timezone Considerations

**IMPORTANT:** The times above assume **Eastern Time (ET)**.

If your server is in a different timezone:

1. Convert times to your local timezone
2. OR set `CRON_TZ` in your crontab:
   ```cron
   CRON_TZ=America/New_York
   ```

Common timezone conversions from 10:30 AM ET:
- Pacific Time: 7:30 AM PT
- Mountain Time: 8:30 AM MT
- Central Time: 9:30 AM CT
- UTC: 3:30 PM UTC (15:30)

## Logs

Create a log directory:

```bash
sudo mkdir -p /var/log/congress_tracker
sudo chown $USER:$USER /var/log/congress_tracker
```

Monitor logs:

```bash
# Watch fetch log
tail -f /var/log/congress_tracker/fetch.log

# Watch posting logs
tail -f /var/log/congress_tracker/post_*.log

# Check for errors
grep -i error /var/log/congress_tracker/*.log
```

## Customization

### Adjust Batch Sizes

Edit the `--max-items` parameter in each posting script:

```bash
# Example: Increase morning batch to 20 items
python -m congress_tracker.cli publish-items --max-items 20
```

### Change Posting Times

Adjust the cron times or sleep durations in `daily_workflow.sh`:

```bash
# Sleep for 1 hour instead of 2 hours
sleep 3600  # seconds
```

### Skip Certain Batches

Comment out unwanted cron jobs or remove sleep/post blocks from `daily_workflow.sh`.

## Troubleshooting

### "Command not found" errors
- Ensure virtual environment is activated in the scripts
- Check that paths in scripts match your installation

### "Permission denied" errors
- Make scripts executable: `chmod +x scripts/*.sh`
- Check log directory permissions

### Posts not appearing
- Verify Bluesky credentials in `.env`
- Check logs for authentication errors
- Test with `--dry-run` first

### Duplicate posts
- The database tracks posted items to prevent duplicates
- Only unposted items will be published
- Check `posted` column in database: `python -m congress_tracker.cli show-stats`

## Performance

Typical resource usage:
- **Fetch script**: ~2-5 minutes, minimal CPU/memory
- **Post scripts**: ~10-30 seconds each, minimal resources
- **API calls**: ~50-100/day (well under 5,000/hour limit)
- **Storage**: ~10-50 MB/month database growth

## Cost Estimate

With default settings:
- **Congress.gov API**: Free (5,000 requests/hour limit)
- **Bluesky**: Free
- **Anthropic API** (optional summarization): ~$0.02-0.05/day = $0.60-1.50/month

Total: **$0-1.50/month**
