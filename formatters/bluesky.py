"""Bluesky thread formatter for Congressional digests."""

import json
from datetime import date, datetime
from typing import Optional

import structlog
from atproto import Client

from congress_tracker.config import get_config
from congress_tracker.models.database import (
    get_session, Vote, Bill, FloorSpeech, DailyDigest, VoteResult
)

log = structlog.get_logger()

# Bluesky character limit
CHAR_LIMIT = 300


def truncate(text: str, limit: int = CHAR_LIMIT) -> str:
    """Truncate text to fit character limit."""
    if len(text) <= limit:
        return text
    return text[:limit - 3] + "..."


def format_vote(vote: Vote) -> str:
    """Format a single vote for Bluesky."""
    result_emoji = {
        VoteResult.PASSED: "PASSED",
        VoteResult.FAILED: "FAILED",
        VoteResult.AGREED_TO: "AGREED",
        VoteResult.REJECTED: "REJECTED",
    }.get(vote.result, "VOTED")

    bill_info = f" on {vote.bill_id}" if vote.bill_id else ""
    desc = vote.description or vote.question or "Roll call vote"

    text = f"[{result_emoji}] {desc}{bill_info}"
    return truncate(text, CHAR_LIMIT - 20)  # Leave room for vote counts


def format_bill(bill: Bill) -> str:
    """Format a single bill for Bluesky."""
    bill_id = f"{bill.bill_type.upper()}{bill.bill_number}"
    title = bill.title or "Untitled bill"

    # Prefer AI summary if available
    if bill.ai_summary:
        text = f"{bill_id}: {bill.ai_summary}"
    else:
        action = bill.latest_action_text or ""
        text = f"{bill_id}: {title}"
        if action:
            text += f"\nAction: {action}"

    return truncate(text)


def format_speech(speech: FloorSpeech) -> str:
    """Format a single speech for Bluesky."""
    speaker = speech.speaker_name or "Unknown"

    # Use AI summary if available, otherwise truncate content
    if speech.ai_summary:
        text = f"{speaker}: {speech.ai_summary}"
    elif speech.title:
        text = f"{speaker} on {speech.title}"
    else:
        # Extract first sentence of content
        content = speech.content or ""
        first_sentence = content.split('.')[0][:150] if content else ""
        text = f"{speaker}: {first_sentence}..."

    return truncate(text)


def generate_daily_digest(target_date: date) -> list[str]:
    """Generate a Bluesky thread for daily Congressional activity.

    Returns list of post strings, each under 300 characters.
    """
    session = get_session()
    posts = []

    try:
        # Get votes for the date
        votes = session.query(Vote).filter(Vote.vote_date == target_date).all()

        # Get bills updated on the date
        bills = session.query(Bill).filter(Bill.latest_action_date == target_date).all()

        # Get speeches for the date
        speeches = session.query(FloorSpeech).filter(
            FloorSpeech.speech_date == target_date
        ).all()

        if not votes and not bills and not speeches:
            log.info("No activity for digest", date=str(target_date))
            return []

        # Header post
        date_str = target_date.strftime("%B %d, %Y")
        header = f"Congressional Activity - {date_str}\n\n"
        header += f"Votes: {len(votes)}\n"
        header += f"Bills: {len(bills)}\n"
        header += f"Speeches: {len(speeches)}"
        posts.append(truncate(header))

        # Vote summaries (limit to top 5)
        if votes:
            posts.append(truncate(f"HOUSE VOTES ({len(votes)} total):"))
            for vote in votes[:5]:
                vote_text = format_vote(vote)
                if vote.yea_count and vote.nay_count:
                    vote_text += f"\nYea: {vote.yea_count} / Nay: {vote.nay_count}"
                posts.append(truncate(vote_text))

            if len(votes) > 5:
                posts.append(f"...and {len(votes) - 5} more votes")

        # Bill summaries (limit to top 5)
        if bills:
            posts.append(truncate(f"BILLS WITH ACTION ({len(bills)} total):"))
            for bill in bills[:5]:
                posts.append(format_bill(bill))

            if len(bills) > 5:
                posts.append(f"...and {len(bills) - 5} more bills")

        # Speech summaries (limit to top 3 - they're longer)
        if speeches:
            posts.append(truncate(f"FLOOR SPEECHES ({len(speeches)} total):"))
            for speech in speeches[:3]:
                posts.append(format_speech(speech))

            if len(speeches) > 3:
                posts.append(f"...and {len(speeches) - 3} more speeches")

        # Footer
        posts.append("Data from Congress.gov API")

        log.info("Generated digest", date=str(target_date), posts=len(posts),
                 votes=len(votes), bills=len(bills), speeches=len(speeches))
        return posts

    except Exception as e:
        log.error("Failed to generate digest", error=str(e))
        return []
    finally:
        session.close()


def publish_thread(posts: list[str], target_date: date) -> Optional[str]:
    """Publish a thread to Bluesky.

    Args:
        posts: List of post strings
        target_date: Date for the digest

    Returns:
        URI of the first post, or None on failure
    """
    config = get_config()

    if not config.bluesky_handle or not config.bluesky_password:
        log.error("Bluesky credentials not configured")
        return None

    try:
        client = Client()
        client.login(config.bluesky_handle, config.bluesky_password)

        root_post = None
        parent_post = None
        root_uri = None

        for i, text in enumerate(posts):
            if i == 0:
                # First post in thread
                response = client.send_post(text=text)
                root_post = {
                    "uri": response.uri,
                    "cid": response.cid,
                }
                parent_post = root_post
                root_uri = response.uri
            else:
                # Reply to previous post
                response = client.send_post(
                    text=text,
                    reply_to={
                        "root": root_post,
                        "parent": parent_post,
                    }
                )
                parent_post = {
                    "uri": response.uri,
                    "cid": response.cid,
                }

        # Save digest record
        session = get_session()
        try:
            digest = DailyDigest(
                digest_date=target_date,
                thread_content=json.dumps(posts),
                votes_count=len([p for p in posts if "VOTES" in p]),
                bills_count=len([p for p in posts if "BILLS" in p]),
                speeches_count=len([p for p in posts if "SPEECHES" in p]),
                published=True,
                published_at=datetime.utcnow(),
                bluesky_thread_uri=root_uri,
            )
            session.add(digest)
            session.commit()
        finally:
            session.close()

        log.info("Published thread", uri=root_uri, posts=len(posts))
        return root_uri

    except Exception as e:
        log.error("Failed to publish to Bluesky", error=str(e))
        return None
