#!/bin/bash
set -e

# Load environment variables from .env if it exists (before any Python commands)
if [ -f /app/.env ]; then
    export $(cat /app/.env | grep -v '^#' | xargs)
fi

# Initialize database on first run
if [ ! -f /data/congress_tracker.db ]; then
    echo "Initializing database..."
    python cli.py init-db
fi

# Handle different commands
case "$1" in
    cron)
        echo "Starting cron scheduler..."

        # Export environment variables to cron
        # This writes env vars to a file that cron jobs can source
        printenv | grep -E "^(CONGRESS_API_KEY|ANTHROPIC_API_KEY|BLUESKY_HANDLE|BLUESKY_PASSWORD|DISCORD_WEBHOOK_URL|DATABASE_URL|TZ|PYTHONPATH)=" > /etc/environment

        # Also set TZ system-wide for cron
        if [ -n "$TZ" ]; then
            echo "TZ=$TZ" >> /etc/environment
            ln -snf /usr/share/zoneinfo/$TZ /etc/localtime
            echo "$TZ" > /etc/timezone
        fi

        echo "Timezone: $(date +%Z)"
        echo "Current time: $(date)"

        # Start cron in foreground
        cron -f
        ;;

    fetch)
        echo "Running one-time data fetch..."
        python cli.py run-etl "${@:2}"
        ;;

    post)
        echo "Running one-time post..."
        python cli.py publish-items "${@:2}"
        ;;

    cli)
        echo "Running CLI command..."
        python cli.py "${@:2}"
        ;;

    bash)
        exec /bin/bash
        ;;

    *)
        exec "$@"
        ;;
esac
