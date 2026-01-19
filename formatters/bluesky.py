"""Bluesky thread formatter for Congressional digests."""

import json
import re
from datetime import date, datetime
from typing import Optional

import structlog
from atproto import Client

from config import get_config
from models.database import (
    get_session, Vote, Bill, FloorSpeech, BillThread, DailyDigest, VoteResult
)

log = structlog.get_logger()

# Bluesky character limit
CHAR_LIMIT = 300


def truncate(text: str, limit: int = CHAR_LIMIT) -> str:
    """Truncate text to fit character limit."""
    if len(text) <= limit:
        return text
    return text[:limit - 3] + "..."


def format_vote(vote: Vote, bill_title: str = None) -> str:
    """Format a single vote for Bluesky.

    Args:
        vote: Vote object to format
        bill_title: Optional bill title to include (looked up separately)
    """
    result_text = {
        VoteResult.PASSED: "PASSED",
        VoteResult.FAILED: "FAILED",
        VoteResult.AGREED_TO: "AGREED",
        VoteResult.REJECTED: "REJECTED",
    }.get(vote.result, "VOTED")

    # Build description based on what info we have
    if vote.amendment_author:
        # Amendment vote
        desc = f"Amendment by {vote.amendment_author}"
        if vote.bill_id:
            desc += f" to {vote.bill_id}"
    elif vote.bill_id:
        # Bill vote - use bill title if available
        if bill_title:
            desc = f"{vote.bill_id}: {bill_title}"
        else:
            desc = f"Vote on {vote.bill_id}"
    elif vote.description:
        desc = vote.description
    elif vote.question:
        desc = vote.question
    else:
        # No meaningful context - return None to signal skip
        return None

    text = f"[{result_text}] {desc}"
    return truncate(text, CHAR_LIMIT - 30)  # Leave room for vote counts and date


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
        URI of the post, or None on failure, or "skipped" if vote has no context
    """
    config = get_config()

    if not config.bluesky_handle or not config.bluesky_password:
        log.error("Bluesky credentials not configured")
        return None

    try:
        # Look up bill title if this vote is related to a bill
        bill_title = None
        if vote.bill_id:
            session = get_session()
            try:
                # Parse bill_id like "HR2988" into type and number
                import re
                match = re.match(r'([A-Z]+)(\d+)', vote.bill_id)
                if match:
                    bill_type = match.group(1).lower()
                    bill_num = int(match.group(2))
                    bill = session.query(Bill).filter(
                        Bill.bill_type == bill_type,
                        Bill.bill_number == bill_num
                    ).first()
                    if bill:
                        bill_title = bill.title
            finally:
                session.close()

        # Format the vote text
        vote_text = format_vote(vote, bill_title)

        # Skip votes with no meaningful context
        if vote_text is None:
            log.info("Skipping vote with no context", vote_id=vote.id)
            # Mark as posted so it's not retried
            session = get_session()
            try:
                db_vote = session.query(Vote).get(vote.id)
                db_vote.posted = True
                db_vote.posted_at = datetime.utcnow()
                session.commit()
            finally:
                session.close()
            return "skipped"

        if vote.yea_count and vote.nay_count:
            vote_text += f"\nYea: {vote.yea_count} / Nay: {vote.nay_count}"

        # Add date
        date_str = vote.vote_date.strftime("%B %d, %Y")
        vote_text = f"🗳️ House Vote - {date_str}\n\n{vote_text}"

        # Publish to Bluesky
        client = Client()
        client.login(config.bluesky_handle, config.bluesky_password)
        response = client.send_post(text=truncate(vote_text))

        # Update vote record in a new session
        session = get_session()
        try:
            db_vote = session.query(Vote).get(vote.id)
            db_vote.bluesky_post_uri = response.uri
            db_vote.posted = True
            db_vote.posted_at = datetime.utcnow()
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

        # Update bill record in a new session
        session = get_session()
        try:
            db_bill = session.query(Bill).get(bill.id)
            db_bill.bluesky_post_uri = response.uri
            db_bill.posted = True
            db_bill.posted_at = datetime.utcnow()
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

        # Update speech record in a new session
        session = get_session()
        try:
            db_speech = session.query(FloorSpeech).get(speech.id)
            db_speech.bluesky_post_uri = response.uri
            db_speech.posted = True
            db_speech.posted_at = datetime.utcnow()
            session.commit()
        finally:
            session.close()

        log.info("Published speech", uri=response.uri, speech_id=speech.id)
        return response.uri

    except Exception as e:
        log.error("Failed to publish speech", error=str(e), speech_id=speech.id)
        return None


def format_bill_header(bill: Bill) -> str:
    """Format bill header post for thread."""
    bill_id = f"{bill.bill_type.upper()}{bill.bill_number}"

    text = f"📜 {bill_id}: {bill.short_title or bill.title}\n\n"

    # Add AI summary if available, otherwise use title
    if bill.ai_summary:
        text += f"{bill.ai_summary}\n\n"
    elif bill.title and bill.title != bill.short_title:
        text += f"{bill.title}\n\n"

    # Add sponsor info
    if bill.sponsor_name:
        sponsor = bill.sponsor_name
        if bill.sponsor_party and bill.sponsor_state:
            sponsor += f" ({bill.sponsor_party}-{bill.sponsor_state})"
        text += f"Sponsor: {sponsor}"

    return truncate(text)


def format_vote_reply(vote: Vote) -> str:
    """Format a vote as a reply in a bill thread."""
    result_text = {
        VoteResult.PASSED: "✅ PASSED",
        VoteResult.FAILED: "❌ FAILED",
        VoteResult.AGREED_TO: "✅ AGREED",
        VoteResult.REJECTED: "❌ REJECTED",
    }.get(vote.result, "🗳️ VOTED")

    # Determine vote type
    if vote.amendment_author:
        vote_type = f"Amendment by {vote.amendment_author}"
    elif "Passage" in (vote.question or ""):
        vote_type = "Final Passage"
    elif "Recommit" in (vote.question or ""):
        vote_type = "Motion to Recommit"
    elif "Previous Question" in (vote.question or ""):
        vote_type = "Previous Question"
    else:
        vote_type = vote.question or "Roll Call Vote"

    text = f"🗳️ {vote_type}\n\n"
    text += f"{result_text}\n"
    text += f"Yea: {vote.yea_count or 0} | Nay: {vote.nay_count or 0}"

    return truncate(text)


def format_speech_reply(speech: FloorSpeech) -> str:
    """Format a speech as a reply in a bill thread."""
    speaker = speech.speaker_name or "Unknown"
    if speech.speaker_party and speech.speaker_state:
        speaker += f" ({speech.speaker_party}-{speech.speaker_state})"

    text = f"🎤 {speaker}\n\n"

    if speech.ai_summary:
        text += speech.ai_summary
    elif speech.title:
        text += f"Speaking on: {speech.title}"
    else:
        # First 200 chars of content
        content = (speech.content or "")[:200]
        if len(speech.content or "") > 200:
            content += "..."
        text += content

    return truncate(text)


def publish_bill_thread(bill: Bill, dry_run: bool = False) -> Optional[dict]:
    """Publish a bill as a threaded post with votes and speeches.

    Creates:
    1. Header post - bill summary
    2. Vote replies - all votes on this bill
    3. Speech replies - floor speeches about this bill

    Args:
        bill: Bill object to publish as thread
        dry_run: If True, return thread content without publishing

    Returns:
        Dict with thread info (uris, counts) or None on failure
    """
    config = get_config()
    session = get_session()

    bill_id = f"{bill.bill_type.upper()}{bill.bill_number}"

    try:
        # Get all votes related to this bill
        votes = session.query(Vote).filter(
            Vote.bill_id == bill_id
        ).order_by(Vote.vote_date.desc()).all()

        # Get all speeches related to this bill
        speeches = session.query(FloorSpeech).filter(
            FloorSpeech.related_bill_id == bill_id
        ).order_by(FloorSpeech.speech_date.desc()).all()

        # Build thread content
        thread_posts = []

        # 1. Header post
        header = format_bill_header(bill)
        thread_posts.append(("header", header, None))

        # 2. Vote posts (final passage first, then amendments)
        passage_votes = [v for v in votes if "Passage" in (v.question or "")]
        other_votes = [v for v in votes if "Passage" not in (v.question or "")]

        for vote in passage_votes + other_votes:
            vote_text = format_vote_reply(vote)
            thread_posts.append(("vote", vote_text, vote))

        # 3. Speech posts
        for speech in speeches[:5]:  # Limit speeches to avoid very long threads
            speech_text = format_speech_reply(speech)
            thread_posts.append(("speech", speech_text, speech))

        if dry_run:
            return {
                "bill_id": bill_id,
                "posts": [(t, text) for t, text, _ in thread_posts],
                "votes_count": len(votes),
                "speeches_count": len(speeches),
            }

        # Publish to Bluesky
        if not config.bluesky_handle or not config.bluesky_password:
            log.error("Bluesky credentials not configured")
            return None

        client = Client()
        client.login(config.bluesky_handle, config.bluesky_password)

        root_post = None
        parent_post = None
        header_uri = None
        header_cid = None

        for post_type, text, item in thread_posts:
            if post_type == "header":
                # First post - the header
                response = client.send_post(text=text)
                root_post = {"uri": response.uri, "cid": response.cid}
                parent_post = root_post
                header_uri = response.uri
                header_cid = response.cid
            else:
                # Reply to thread
                response = client.send_post(
                    text=text,
                    reply_to={"root": root_post, "parent": parent_post}
                )
                parent_post = {"uri": response.uri, "cid": response.cid}

                # Update individual item record
                if post_type == "vote" and item:
                    db_item = session.query(Vote).get(item.id)
                    if db_item:
                        db_item.bluesky_post_uri = response.uri
                        db_item.posted = True
                        db_item.posted_at = datetime.utcnow()
                elif post_type == "speech" and item:
                    db_item = session.query(FloorSpeech).get(item.id)
                    if db_item:
                        db_item.bluesky_post_uri = response.uri
                        db_item.posted = True
                        db_item.posted_at = datetime.utcnow()

        # Save BillThread record
        bill_thread = BillThread(
            bill_id=bill.id,
            bill_str_id=bill_id,
            header_post_uri=header_uri,
            header_post_cid=header_cid,
            votes_count=len(votes),
            speeches_count=min(len(speeches), 5),
            published=True,
            published_at=datetime.utcnow(),
        )
        session.add(bill_thread)

        # Mark bill as posted
        db_bill = session.query(Bill).get(bill.id)
        db_bill.bluesky_post_uri = header_uri
        db_bill.posted = True
        db_bill.posted_at = datetime.utcnow()

        session.commit()

        log.info("Published bill thread",
                 bill_id=bill_id,
                 uri=header_uri,
                 votes=len(votes),
                 speeches=min(len(speeches), 5))

        return {
            "bill_id": bill_id,
            "header_uri": header_uri,
            "votes_count": len(votes),
            "speeches_count": min(len(speeches), 5),
            "total_posts": len(thread_posts),
        }

    except Exception as e:
        log.error("Failed to publish bill thread", error=str(e), bill_id=bill_id)
        session.rollback()
        return None
    finally:
        session.close()


def publish_bill_threads(target_date: date, max_bills: Optional[int] = None,
                         dry_run: bool = False) -> dict:
    """Publish all unposted bills from a date as threads.

    Args:
        target_date: Date to publish bills for
        max_bills: Optional limit on bills to post
        dry_run: If True, preview without publishing

    Returns:
        Dictionary with counts and results
    """
    session = get_session()
    stats = {
        "bills": 0,
        "total_votes": 0,
        "total_speeches": 0,
        "errors": 0,
        "threads": [],
    }

    try:
        # Get unposted bills with activity on this date
        bills = session.query(Bill).filter(
            Bill.latest_action_date == target_date,
            Bill.posted.is_(False)
        ).all()

        if not bills:
            log.info("No unposted bills for date", date=str(target_date))
            return stats

        if max_bills:
            bills = bills[:max_bills]

        log.info("Publishing bill threads", date=str(target_date), count=len(bills))

        for bill in bills:
            result = publish_bill_thread(bill, dry_run=dry_run)
            if result:
                stats["bills"] += 1
                stats["total_votes"] += result.get("votes_count", 0)
                stats["total_speeches"] += result.get("speeches_count", 0)
                stats["threads"].append(result)
            else:
                stats["errors"] += 1

        log.info("Bill threads published", **{k: v for k, v in stats.items() if k != "threads"})
        return stats

    finally:
        session.close()


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
        "skipped": 0,
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
                    result = publish_vote(item)
                    if result == "skipped":
                        stats["skipped"] += 1
                    elif result:
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
