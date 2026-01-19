# Quick Start Guide

Get Congress Tracker running in under 5 minutes!

## Using Docker (Recommended) 🐳

### 1. Install Prerequisites

**Install Docker:**
- Mac/Windows: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Linux: [Docker Engine](https://docs.docker.com/engine/install/)

### 2. Configure

```bash
# Clone the repo
git clone https://github.com/yourusername/congress_tracker.git
cd congress_tracker

# Create config file
cp .env.example .env

# Edit .env with your API keys (required)
nano .env
```

Add these keys:
```env
CONGRESS_API_KEY=your_key_here          # Get from: https://api.congress.gov/
BLUESKY_HANDLE=yourhandle.bsky.social   # Your Bluesky handle
BLUESKY_PASSWORD=your_app_password      # Generate at: Settings -> App Passwords
ANTHROPIC_API_KEY=your_key              # Optional, for summarization
```

### 3. Start

```bash
# Start scheduler
docker-compose up -d scheduler

# Check it's running
docker-compose logs -f scheduler
```

**That's it!** The bot will now:
- Fetch congressional data at 10:30 AM ET daily
- Post updates in 5 batches from 11 AM - 7 PM ET
- Automatically restart if your server reboots

### 4. Verify

```bash
# Check status
docker-compose ps

# View statistics
docker-compose run --rm cli show-stats

# Test posting (dry run)
docker-compose run --rm cli publish-items --dry-run
```

## Common Tasks

```bash
# View logs
docker-compose logs -f scheduler

# Stop scheduler
docker-compose down

# Restart scheduler
docker-compose restart scheduler

# Manual data fetch
docker-compose run --rm cli run-etl

# Update code
git pull
docker-compose build scheduler
docker-compose up -d scheduler
```

## Using Native Python

### 1. Install

```bash
git clone https://github.com/yourusername/congress_tracker.git
cd congress_tracker

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env  # Add API keys
```

### 2. Run

```bash
# Initialize database
python -m congress_tracker.cli init-db

# Fetch data
python -m congress_tracker.cli run-etl

# Post (dry run)
python -m congress_tracker.cli publish-items --dry-run
```

### 3. Schedule

Set up cron jobs (see main [README.md](README.md) for details):

```bash
cp scripts/crontab.example scripts/crontab.local
nano scripts/crontab.local  # Edit paths
crontab scripts/crontab.local
```

## Troubleshooting

**"API key not configured"**
- Check your `.env` file exists
- Verify `CONGRESS_API_KEY` is set
- For Docker: restart after editing .env

**"Permission denied"**
- Docker: `sudo chmod 777 ./data ./logs`
- Native: Check file permissions

**"No items to post"**
- Run fetch first: `docker-compose run --rm cli run-etl`
- Congress.gov data might not be available yet (updates at 10 AM ET)

**"Container won't start"**
```bash
docker-compose logs scheduler
docker-compose config  # Check for syntax errors
```

## Next Steps

- Read [DOCKER.md](DOCKER.md) for complete Docker guide
- Read [README.md](README.md) for full documentation
- Check [scripts/README.md](scripts/README.md) for scheduling details

## Getting Help

1. Check logs for error messages
2. Verify API credentials are correct
3. Test connectivity: `curl https://api.congress.gov/v3/bill/119?api_key=YOUR_KEY`
4. Open a GitHub issue with logs and error details

## Tips

- **Timezone**: Default is Eastern Time. Change in `docker-compose.yml` if needed.
- **Backups**: Database is in `./data/congress_tracker.db` - back it up regularly
- **Costs**: Congress.gov and Bluesky are free. Anthropic API costs ~$0.60-1.50/month.
- **Resources**: Uses <100 MB RAM and minimal CPU. Very lightweight!

Happy tracking! 🏛️
