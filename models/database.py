"""Database models for Congress Tracker."""

from datetime import datetime, date
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import enum

from config import get_config

Base = declarative_base()


class VoteResult(enum.Enum):
    PASSED = "passed"
    FAILED = "failed"
    AGREED_TO = "agreed_to"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class Chamber(enum.Enum):
    HOUSE = "house"
    SENATE = "senate"


class Vote(Base):
    """Congressional vote record."""

    __tablename__ = "votes"

    id = Column(Integer, primary_key=True)
    congress = Column(Integer, nullable=False)
    session = Column(Integer, nullable=False)
    chamber = Column(Enum(Chamber), nullable=False)
    roll_call = Column(Integer, nullable=False)
    vote_date = Column(Date, nullable=False)
    vote_time = Column(String(10))

    question = Column(Text)
    description = Column(Text)
    vote_type = Column(String(50))
    result = Column(Enum(VoteResult))

    # Vote counts
    yea_count = Column(Integer)
    nay_count = Column(Integer)
    present_count = Column(Integer)
    not_voting_count = Column(Integer)

    # Related bill info
    bill_id = Column(String(50))
    bill_number = Column(String(20))
    bill_title = Column(Text)  # Cached bill title for display

    # Amendment info (for amendment votes)
    amendment_number = Column(String(20))
    amendment_type = Column(String(20))
    amendment_author = Column(Text)  # e.g., "Huizenga of Michigan Part A Amendment"

    # API source tracking
    source_url = Column(String(500))
    raw_data = Column(Text)  # JSON storage

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Digest tracking
    included_in_digest = Column(Boolean, default=False)
    digest_date = Column(Date)

    # Individual post tracking
    bluesky_post_uri = Column(String(500))
    posted = Column(Boolean, default=False)
    posted_at = Column(DateTime)


class Bill(Base):
    """Congressional bill record."""

    __tablename__ = "bills"

    id = Column(Integer, primary_key=True)
    congress = Column(Integer, nullable=False)
    bill_type = Column(String(10), nullable=False)  # hr, s, hjres, sjres, etc.
    bill_number = Column(Integer, nullable=False)

    title = Column(Text)
    short_title = Column(Text)

    introduced_date = Column(Date)
    latest_action_date = Column(Date)
    latest_action_text = Column(Text)

    sponsor_name = Column(String(200))
    sponsor_party = Column(String(1))
    sponsor_state = Column(String(2))

    # Summaries
    crs_summary = Column(Text)
    ai_summary = Column(Text)  # Claude-generated summary
    ai_summary_date = Column(DateTime)

    # Policy areas and subjects
    policy_area = Column(String(200))
    subjects = Column(Text)  # JSON array

    source_url = Column(String(500))
    raw_data = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Individual post tracking
    bluesky_post_uri = Column(String(500))
    posted = Column(Boolean, default=False)
    posted_at = Column(DateTime)


class FloorSpeech(Base):
    """Congressional Record floor speech."""

    __tablename__ = "floor_speeches"

    id = Column(Integer, primary_key=True)
    congress = Column(Integer, nullable=False)
    chamber = Column(Enum(Chamber), nullable=False)
    speech_date = Column(Date, nullable=False)

    speaker_name = Column(String(200))
    speaker_party = Column(String(1))
    speaker_state = Column(String(2))

    title = Column(Text)
    content = Column(Text)
    ai_summary = Column(Text)
    ai_summary_date = Column(DateTime)

    # Related bill (detected from speech content)
    related_bill_id = Column(String(50))  # e.g., "HR2988"
    related_bill_db_id = Column(Integer, ForeignKey("bills.id"))

    # Metadata
    granule_id = Column(String(100))
    source_url = Column(String(500))

    created_at = Column(DateTime, default=datetime.utcnow)

    # Individual post tracking
    bluesky_post_uri = Column(String(500))
    posted = Column(Boolean, default=False)
    posted_at = Column(DateTime)


class BillThread(Base):
    """Published Bluesky thread for a bill."""

    __tablename__ = "bill_threads"

    id = Column(Integer, primary_key=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    bill_str_id = Column(String(50), nullable=False)  # e.g., "HR2988"

    # Thread structure - store URIs for threading replies
    header_post_uri = Column(String(500))
    header_post_cid = Column(String(100))

    # Stats
    votes_count = Column(Integer, default=0)
    speeches_count = Column(Integer, default=0)

    # Publishing status
    published = Column(Boolean, default=False)
    published_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)


class DailyDigest(Base):
    """Generated daily digest for Bluesky."""

    __tablename__ = "daily_digests"

    id = Column(Integer, primary_key=True)
    digest_date = Column(Date, nullable=False, unique=True)

    # Thread content (JSON array of posts)
    thread_content = Column(Text)

    # Stats
    votes_count = Column(Integer, default=0)
    bills_count = Column(Integer, default=0)
    speeches_count = Column(Integer, default=0)

    # Publishing status
    published = Column(Boolean, default=False)
    published_at = Column(DateTime)
    bluesky_thread_uri = Column(String(500))

    created_at = Column(DateTime, default=datetime.utcnow)


def get_engine():
    """Create database engine."""
    config = get_config()
    return create_engine(config.database_url, echo=False)


def get_session():
    """Create database session."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def init_db():
    """Initialize database tables."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("Database initialized successfully.")
