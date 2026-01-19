#!/bin/bash
set -e

# Initialize database on first run
if [ ! -f /data/congress_tracker.db ]; then
    echo "Initializing database..."
    python -m congress_tracker.cli init-db
fi

# Load environment variables from .env if it exists
if [ -f /app/.env ]; then
    export $(cat /app/.env | grep -v '^#' | xargs)
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
        python -m congress_tracker.cli run-etl "${@:2}"
        ;;

    post)
        echo "Running one-time post..."
        python -m congress_tracker.cli publish-items "${@:2}"
        ;;

    cli)
        echo "Running CLI command..."
        python -m congress_tracker.cli "${@:2}"
        ;;

    bash)
        exec /bin/bash
        ;;

    *)
        exec "$@"
        ;;
esac
