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


def publish_vote(vote: Vote) -> Optional[str]:
    """Publish a single vote as an individual post to Bluesky.

    Args:
        vote: Vote object to publish

    Returns:
        URI of the post, or None on failure
    """
    config = get_config()

    if not config.bluesky_handle or not config.bluesky_password:
        log.error("Bluesky credentials not configured")
        return None

    try:
        # Format the vote text
        vote_text = format_vote(vote)
        if vote.yea_count and vote.nay_count:
            vote_text += f"\nYea: {vote.yea_count} / Nay: {vote.nay_count}"

        # Add date
        date_str = vote.vote_date.strftime("%B %d, %Y")
        vote_text = f"Vote - {date_str}\n\n{vote_text}"

        # Publish to Bluesky
        client = Client()
        client.login(config.bluesky_handle, config.bluesky_password)
        response = client.send_post(text=truncate(vote_text))

        # Update vote record
        session = get_session()
        try:
            vote.bluesky_post_uri = response.uri
            vote.posted = True
            vote.posted_at = datetime.utcnow()
            session.add(vote)
            session.commit()
        finally:
            session.close()

        log.info("Published vote", uri=response.uri, vote_id=vote.id)
        return response.uri

    except Exception as e:
        log.error("Failed to publish vote", error=str(e), vote_id=vote.id)
        return None


def publish_bill(bill: Bill) -> Optional[str]:
    """Publish a single bill as an individual post to Bluesky.

    Args:
        bill: Bill object to publish

    Returns:
        URI of the post, or None on failure
    """
    config = get_config()

    if not config.bluesky_handle or not config.bluesky_password:
        log.error("Bluesky credentials not configured")
        return None

    try:
        # Format the bill text
        bill_text = format_bill(bill)

        # Add date and type header
        date_str = bill.latest_action_date.strftime("%B %d, %Y") if bill.latest_action_date else "Unknown"
        bill_text = f"Bill Update - {date_str}\n\n{bill_text}"

        # Publish to Bluesky
        client = Client()
        client.login(config.bluesky_handle, config.bluesky_password)
        response = client.send_post(text=truncate(bill_text))

        # Update bill record
        session = get_session()
        try:
            bill.bluesky_post_uri = response.uri
            bill.posted = True
            bill.posted_at = datetime.utcnow()
            session.add(bill)
            session.commit()
        finally:
            session.close()

        log.info("Published bill", uri=response.uri, bill_id=bill.id)
        return response.uri

    except Exception as e:
        log.error("Failed to publish bill", error=str(e), bill_id=bill.id)
        return None


def publish_speech(speech: FloorSpeech) -> Optional[str]:
    """Publish a single floor speech as an individual post to Bluesky.

    Args:
        speech: FloorSpeech object to publish

    Returns:
        URI of the post, or None on failure
    """
    config = get_config()

    if not config.bluesky_handle or not config.bluesky_password:
        log.error("Bluesky credentials not configured")
        return None

    try:
        # Format the speech text
        speech_text = format_speech(speech)

        # Add date and type header
        date_str = speech.speech_date.strftime("%B %d, %Y")
        speech_text = f"Floor Speech - {date_str}\n\n{speech_text}"

        # Publish to Bluesky
        client = Client()
        client.login(config.bluesky_handle, config.bluesky_password)
        response = client.send_post(text=truncate(speech_text))

        # Update speech record
        session = get_session()
        try:
            speech.bluesky_post_uri = response.uri
            speech.posted = True
            speech.posted_at = datetime.utcnow()
            session.add(speech)
            session.commit()
        finally:
            session.close()

        log.info("Published speech", uri=response.uri, speech_id=speech.id)
        return response.uri

    except Exception as e:
        log.error("Failed to publish speech", error=str(e), speech_id=speech.id)
        return None


def publish_daily_items(target_date: date, max_items: Optional[int] = None) -> dict:
    """Publish all unposted items from a date as individual posts.

    Args:
        target_date: Date to publish items for
        max_items: Optional limit on total items to post

    Returns:
        Dictionary with counts of published items
    """
    session = get_session()
    stats = {
        "votes": 0,
        "bills": 0,
        "speeches": 0,
        "errors": 0,
    }

    try:
        # Get unposted votes
        votes = session.query(Vote).filter(
            Vote.vote_date == target_date,
            Vote.posted.is_(False)
        ).all()

        # Get unposted bills
        bills = session.query(Bill).filter(
            Bill.latest_action_date == target_date,
            Bill.posted.is_(False)
        ).all()

        # Get unposted speeches
        speeches = session.query(FloorSpeech).filter(
            FloorSpeech.speech_date == target_date,
            FloorSpeech.posted.is_(False)
        ).all()

        total_items = len(votes) + len(bills) + len(speeches)
        if total_items == 0:
            log.info("No unposted items for date", date=str(target_date))
            return stats

        log.info("Publishing individual items", date=str(target_date),
                 votes=len(votes), bills=len(bills), speeches=len(speeches))

        # Apply max_items limit if specified
        items_to_post = []
        items_to_post.extend([("vote", v) for v in votes])
        items_to_post.extend([("bill", b) for b in bills])
        items_to_post.extend([("speech", s) for s in speeches])

        if max_items:
            items_to_post = items_to_post[:max_items]

        # Publish each item
        for item_type, item in items_to_post:
            try:
                if item_type == "vote":
                    if publish_vote(item):
                        stats["votes"] += 1
                    else:
                        stats["errors"] += 1
                elif item_type == "bill":
                    if publish_bill(item):
                        stats["bills"] += 1
                    else:
                        stats["errors"] += 1
                elif item_type == "speech":
                    if publish_speech(item):
                        stats["speeches"] += 1
                    else:
                        stats["errors"] += 1
            except Exception as e:
                log.error("Error publishing item", error=str(e), type=item_type)
                stats["errors"] += 1

        log.info("Publishing complete", **stats)
        return stats

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
