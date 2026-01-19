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
