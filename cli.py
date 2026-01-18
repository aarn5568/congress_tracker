"""CLI for Congress Tracker."""

from datetime import date, datetime, timedelta

import click
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


@click.group()
def cli():
    """Congress Tracker - Monitor Congressional activity."""
    pass


@cli.command()
def init_db():
    """Initialize the database."""
    from congress_tracker.models.database import init_db as _init_db
    _init_db()
    click.echo("Database initialized.")


@cli.command()
@click.option("--date", "-d", "target_date", type=click.DateTime(formats=["%Y-%m-%d"]),
              help="Date to fetch votes for (YYYY-MM-DD). Defaults to yesterday.")
def fetch_votes(target_date):
    """Fetch Congressional votes for a specific date."""
    from congress_tracker.etl.votes import fetch_votes_for_date

    if target_date is None:
        target = date.today() - timedelta(days=1)
    else:
        target = target_date.date()

    click.echo(f"Fetching votes for {target}...")
    count = fetch_votes_for_date(target)
    click.echo(f"Saved {count} new votes.")


@cli.command()
@click.option("--date", "-d", "target_date", type=click.DateTime(formats=["%Y-%m-%d"]),
              help="Date to fetch bills for (YYYY-MM-DD). Defaults to yesterday.")
@click.option("--details", is_flag=True, help="Fetch full bill details (slower).")
def fetch_bills(target_date, details):
    """Fetch Congressional bills updated on a specific date."""
    from congress_tracker.etl.bills import fetch_bills_for_date

    if target_date is None:
        target = date.today() - timedelta(days=1)
    else:
        target = target_date.date()

    click.echo(f"Fetching bills for {target}...")
    count = fetch_bills_for_date(target, fetch_details=details)
    click.echo(f"Saved {count} new bills.")


@cli.command()
@click.option("--date", "-d", "target_date", type=click.DateTime(formats=["%Y-%m-%d"]),
              help="Date to fetch Congressional Record for (YYYY-MM-DD). Defaults to yesterday.")
def fetch_speeches(target_date):
    """Fetch Congressional Record for a specific date."""
    from congress_tracker.etl.speeches import fetch_speeches_for_date

    if target_date is None:
        target = date.today() - timedelta(days=1)
    else:
        target = target_date.date()

    click.echo(f"Fetching Congressional Record for {target}...")
    count = fetch_speeches_for_date(target)
    if count:
        click.echo("Congressional Record found.")
    else:
        click.echo("No Congressional Record for this date.")


@cli.command()
@click.option("--date", "-d", "target_date", type=click.DateTime(formats=["%Y-%m-%d"]),
              help="Date to run full ETL for (YYYY-MM-DD). Defaults to yesterday.")
def run_etl(target_date):
    """Run full ETL pipeline: fetch votes and bills."""
    from congress_tracker.etl.votes import fetch_votes_for_date
    from congress_tracker.etl.bills import fetch_bills_for_date

    if target_date is None:
        target = date.today() - timedelta(days=1)
    else:
        target = target_date.date()

    click.echo(f"Running ETL for {target}...")

    # Votes
    click.echo("Fetching votes...")
    vote_count = fetch_votes_for_date(target)
    click.echo(f"  Saved {vote_count} votes.")

    # Bills
    click.echo("Fetching bills...")
    bill_count = fetch_bills_for_date(target)
    click.echo(f"  Saved {bill_count} bills.")

    click.echo("ETL complete.")


@cli.command()
@click.option("--date", "-d", "target_date", type=click.DateTime(formats=["%Y-%m-%d"]),
              help="Date to generate digest for (YYYY-MM-DD). Defaults to yesterday.")
def generate_digest(target_date):
    """Generate daily digest for Bluesky."""
    from congress_tracker.formatters.bluesky import generate_daily_digest

    if target_date is None:
        target = date.today() - timedelta(days=1)
    else:
        target = target_date.date()

    click.echo(f"Generating digest for {target}...")
    thread = generate_daily_digest(target)
    if thread:
        click.echo(f"Generated {len(thread)} posts.")
        for i, post in enumerate(thread, 1):
            click.echo(f"\n--- Post {i} ({len(post)} chars) ---")
            click.echo(post)
    else:
        click.echo("No content for digest.")


@cli.command()
@click.option("--date", "-d", "target_date", type=click.DateTime(formats=["%Y-%m-%d"]),
              help="Date to publish digest for (YYYY-MM-DD). Defaults to yesterday.")
@click.option("--dry-run", is_flag=True, help="Print thread without publishing.")
def publish_digest(target_date, dry_run):
    """Publish daily digest to Bluesky."""
    from congress_tracker.formatters.bluesky import generate_daily_digest, publish_thread

    if target_date is None:
        target = date.today() - timedelta(days=1)
    else:
        target = target_date.date()

    click.echo(f"{'[DRY RUN] ' if dry_run else ''}Publishing digest for {target}...")

    thread = generate_daily_digest(target)
    if not thread:
        click.echo("No content for digest.")
        return

    if dry_run:
        for i, post in enumerate(thread, 1):
            click.echo(f"\n--- Post {i} ({len(post)} chars) ---")
            click.echo(post)
    else:
        uri = publish_thread(thread, target)
        if uri:
            click.echo(f"Published! Thread URI: {uri}")
        else:
            click.echo("Failed to publish.")


@cli.command()
def show_stats():
    """Show database statistics."""
    from congress_tracker.models.database import get_session, Vote, Bill, FloorSpeech, DailyDigest

    session = get_session()
    try:
        vote_count = session.query(Vote).count()
        bill_count = session.query(Bill).count()
        speech_count = session.query(FloorSpeech).count()
        digest_count = session.query(DailyDigest).count()

        click.echo("Database Statistics:")
        click.echo(f"  Votes:    {vote_count}")
        click.echo(f"  Bills:    {bill_count}")
        click.echo(f"  Speeches: {speech_count}")
        click.echo(f"  Digests:  {digest_count}")
    finally:
        session.close()


if __name__ == "__main__":
    cli()
