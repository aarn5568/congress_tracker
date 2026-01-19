#!/bin/bash
# Docker Helper Script - Common operations for Congress Tracker

set -e

COMPOSE_FILE="docker-compose.yml"

show_help() {
    cat << EOF
Congress Tracker - Docker Helper

Usage: ./docker/docker-helper.sh <command>

Commands:
    start           Start the scheduler in background
    stop            Stop the scheduler
    restart         Restart the scheduler
    logs            Show logs (follow mode)
    logs-once       Show logs (one-time)
    status          Show running containers

    fetch           Run one-time data fetch
    post            Run one-time post batch
    stats           Show database statistics
    init            Initialize database

    shell           Open bash shell in container
    rebuild         Rebuild Docker image
    clean           Remove containers and images

Examples:
    ./docker/docker-helper.sh start
    ./docker/docker-helper.sh logs
    ./docker/docker-helper.sh fetch
    ./docker/docker-helper.sh post --dry-run --max-items 5

EOF
}

case "$1" in
    start)
        echo "Starting Congress Tracker scheduler..."
        docker-compose up -d scheduler
        echo "Scheduler started. View logs with: $0 logs"
        ;;

    stop)
        echo "Stopping Congress Tracker..."
        docker-compose down
        ;;

    restart)
        echo "Restarting Congress Tracker..."
        docker-compose restart scheduler
        ;;

    logs)
        echo "Following logs (Ctrl+C to exit)..."
        docker-compose logs -f scheduler
        ;;

    logs-once)
        docker-compose logs scheduler
        ;;

    status)
        docker-compose ps
        ;;

    fetch)
        echo "Running data fetch..."
        docker-compose run --rm cli run-etl "${@:2}"
        ;;

    post)
        echo "Running post batch..."
        docker-compose run --rm cli publish-items "${@:2}"
        ;;

    stats)
        docker-compose run --rm cli show-stats
        ;;

    init)
        echo "Initializing database..."
        docker-compose run --rm cli init-db
        ;;

    shell)
        echo "Opening shell..."
        docker-compose run --rm cli bash
        ;;

    rebuild)
        echo "Rebuilding Docker image..."
        docker-compose build --no-cache
        ;;

    clean)
        echo "Cleaning up Docker resources..."
        docker-compose down -v
        docker rmi congress_tracker_scheduler congress_tracker_cli 2>/dev/null || true
        echo "Cleanup complete."
        ;;

    help|--help|-h)
        show_help
        ;;

    *)
        echo "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
