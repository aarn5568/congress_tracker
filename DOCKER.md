# Docker Setup Guide

This guide explains how to run Congress Tracker using Docker and Docker Compose, which significantly simplifies installation and updates.

## Benefits of Docker Setup

✅ **No dependency management** - No need for Python venv or pip installs
✅ **Consistent environment** - Works the same on any system
✅ **Easy updates** - Just rebuild the image
✅ **Isolated** - Doesn't affect your host system
✅ **Portable** - Move between servers easily
✅ **Built-in scheduling** - Cron included and configured

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+

**Install Docker:**
- Linux: https://docs.docker.com/engine/install/
- Mac: https://docs.docker.com/desktop/mac/install/
- Windows: https://docs.docker.com/desktop/windows/install/

## Quick Start

### 1. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with your API keys
nano .env
```

Required variables:
```env
CONGRESS_API_KEY=your_congress_api_key
BLUESKY_HANDLE=yourhandle.bsky.social
BLUESKY_PASSWORD=your_app_password
ANTHROPIC_API_KEY=your_anthropic_key  # Optional
```

### 2. Start the Scheduler

```bash
# Build and start in background
docker-compose up -d scheduler

# View logs
docker-compose logs -f scheduler
```

That's it! The scheduler will:
- Initialize the database on first run
- Fetch data at 10:30 AM ET daily
- Post in 5 batches throughout the day (11 AM - 7 PM ET)

### 3. Check Status

```bash
# View running containers
docker-compose ps

# Check logs
docker-compose logs scheduler
```

## Using the Helper Script

For convenience, use the helper script for common operations:

```bash
# Start scheduler
./docker/docker-helper.sh start

# View logs
./docker/docker-helper.sh logs

# Check status
./docker/docker-helper.sh status

# Stop scheduler
./docker/docker-helper.sh stop
```

## Manual Commands

### One-Time Data Fetch

```bash
# Fetch yesterday's data
docker-compose run --rm cli run-etl

# Fetch specific date
docker-compose run --rm cli run-etl --date 2025-09-08
```

### One-Time Posting

```bash
# Post with dry run (preview)
docker-compose run --rm cli publish-items --dry-run

# Post specific date
docker-compose run --rm cli publish-items --date 2025-09-08

# Post with item limit
docker-compose run --rm cli publish-items --max-items 10
```

### Database Operations

```bash
# Show statistics
docker-compose run --rm cli show-stats

# Initialize database (usually automatic)
docker-compose run --rm cli init-db

# Summarize bills
docker-compose run --rm cli summarize --bills --limit 20
```

### Interactive Shell

```bash
# Open bash shell in container
docker-compose run --rm cli bash

# Once inside, you can run any command
python -m congress_tracker.cli --help
```

## Timezone Configuration

The default timezone is `America/New_York` (Eastern Time). To change it:

**Option 1: Edit docker-compose.yml**
```yaml
environment:
  - TZ=America/Los_Angeles  # Pacific Time
  - TZ=America/Chicago       # Central Time
  - TZ=Europe/London         # UK
```

**Option 2: Override in .env**
```env
TZ=America/Los_Angeles
```

Find your timezone: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

## Data Persistence

### Volumes

Docker uses volumes to persist data:

- `./data/` - SQLite database
- `./logs/` - Log files

These directories are created automatically on the host machine.

### Backup Database

```bash
# Copy database from container
cp ./data/congress_tracker.db ./backup/congress_tracker_$(date +%Y%m%d).db

# Restore from backup
cp ./backup/congress_tracker_20250119.db ./data/congress_tracker.db
docker-compose restart scheduler
```

## Customizing the Schedule

### Edit Cron Times

Modify `docker/crontab` to change posting times:

```cron
# Example: Change morning post to 9:00 AM
0 9 * * * cd /app && python -m congress_tracker.cli publish-items --max-items 10
```

After editing, rebuild the image:

```bash
docker-compose build scheduler
docker-compose up -d scheduler
```

### Change Batch Sizes

Edit the `--max-items` parameter in `docker/crontab`:

```cron
# Post 20 items instead of 10
0 11 * * * cd /app && python -m congress_tracker.cli publish-items --max-items 20
```

## Updates and Maintenance

### Update Application

```bash
# Pull latest code
git pull

# Rebuild image
docker-compose build --no-cache scheduler

# Restart with new image
docker-compose up -d scheduler
```

Or use the helper:
```bash
./docker/docker-helper.sh rebuild
./docker/docker-helper.sh start
```

### View Logs

```bash
# Follow logs live
docker-compose logs -f scheduler

# View last 100 lines
docker-compose logs --tail=100 scheduler

# View specific log file
docker-compose exec scheduler cat /logs/post_morning.log
```

### Restart Services

```bash
# Restart scheduler
docker-compose restart scheduler

# Stop everything
docker-compose down

# Start fresh
docker-compose up -d scheduler
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs for errors
docker-compose logs scheduler

# Check if .env exists
ls -la .env

# Verify environment variables
docker-compose config
```

### Database Issues

```bash
# Re-initialize database
docker-compose run --rm cli init-db

# Check database location
docker-compose exec scheduler ls -la /data
```

### Cron Not Running

```bash
# Check if cron is running
docker-compose exec scheduler ps aux | grep cron

# Check cron logs
docker-compose exec scheduler grep CRON /var/log/syslog

# Verify crontab is installed
docker-compose exec scheduler crontab -l
```

### Permission Issues

```bash
# Fix data directory permissions
sudo chown -R $USER:$USER ./data ./logs
chmod -R 755 ./data ./logs
```

### API Errors

```bash
# Test Congress.gov API
docker-compose run --rm cli bash
curl "https://api.congress.gov/v3/bill/119?api_key=YOUR_KEY"

# Test Bluesky credentials
docker-compose run --rm cli publish-items --dry-run
```

## Development Mode

For development, mount the code as a volume:

```yaml
# Add to docker-compose.yml under scheduler service
volumes:
  - ./:/app  # Mount entire directory
  - ./data:/data
  - ./logs:/logs
```

Changes to Python code will be reflected without rebuilding.

## Comparing Docker vs Native Installation

| Feature | Docker | Native |
|---------|--------|--------|
| Setup time | 5 minutes | 15 minutes |
| Dependencies | Automatic | Manual (venv, pip) |
| Updates | Rebuild image | git pull + pip install |
| Isolation | Complete | Shared Python env |
| Portability | High | Medium |
| Debugging | Requires exec/logs | Direct access |

**Recommendation:** Use Docker for production, native for development.

## Advanced: Multi-Container Setup

For high-volume deployments, you could split into multiple containers:

```yaml
services:
  fetcher:
    # Handles data fetching only

  poster-morning:
    # Handles morning posts only

  poster-afternoon:
    # Handles afternoon posts only
```

This isn't necessary for typical usage but provides better resource isolation.

## Security Notes

- `.env` file contains secrets - keep it secure
- The `.env` is mounted read-only into containers
- Database file is in `./data` - include in backups, exclude from git
- App passwords for Bluesky are safer than main passwords
- Congress.gov API key is free but rate-limited to 5000/hour

## Resource Usage

Typical resource consumption:

- **Image size**: ~200 MB
- **Memory**: 50-100 MB
- **CPU**: <1% (idle), 5-10% (during fetch/post)
- **Disk**: ~10-50 MB/month for database growth
- **Network**: ~5-10 MB/day for API calls

Very lightweight!

## Getting Help

If you encounter issues:

1. Check logs: `docker-compose logs scheduler`
2. Verify configuration: `docker-compose config`
3. Test API connectivity: `docker-compose run --rm cli bash`
4. Review [main README](README.md) for CLI usage
5. Check [scripts README](scripts/README.md) for scheduling details

## Example Workflows

### Daily Monitoring

```bash
# Morning: Check if jobs ran
./docker/docker-helper.sh logs-once | grep "Publishing"

# Afternoon: Check database
./docker/docker-helper.sh stats
```

### Manual Override

```bash
# Congress just voted, fetch immediately
./docker/docker-helper.sh fetch

# Post specific batch manually
./docker/docker-helper.sh post --max-items 5
```

### Weekly Maintenance

```bash
# Check logs
./docker/docker-helper.sh logs-once > weekly_logs.txt

# Backup database
cp ./data/congress_tracker.db ./backups/backup_$(date +%Y%m%d).db

# Clean old logs
find ./logs -name "*.log" -mtime +30 -delete
```
