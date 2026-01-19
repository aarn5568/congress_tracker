#!/usr/bin/env python3
"""Test script to preview bill-centric thread format.

Run with: docker run --rm congress-tracker-test python test_post_format.py
"""

from datetime import date
from dataclasses import dataclass
from typing import Optional
import sys

# Add path for imports
sys.path.insert(0, '/app')

from models.database import VoteResult


# Mock classes that match our database models
@dataclass
class MockVote:
    id: int
    bill_id: str
    vote_date: date
    result: VoteResult
    yea_count: int
    nay_count: int
    question: str
    description: str
    amendment_author: Optional[str] = None


@dataclass
class MockBill:
    id: int
    bill_type: str
    bill_number: int
    title: str
    short_title: Optional[str]
    ai_summary: Optional[str]
    latest_action_text: str
    latest_action_date: date
    sponsor_name: str
    sponsor_party: str
    sponsor_state: str


@dataclass
class MockSpeech:
    id: int
    speaker_name: str
    speaker_party: str
    speaker_state: str
    title: str
    ai_summary: Optional[str]
    content: Optional[str]
    speech_date: date
    related_bill_id: Optional[str] = None


# Sample data
sample_bills = [
    MockBill(
        id=1,
        bill_type="hr",
        bill_number=2988,
        title="To require U.S. Immigration and Customs Enforcement to take into custody certain aliens who have been charged in the United States with theft, and for other purposes.",
        short_title="Laken Riley Act",
        ai_summary="Requires DHS to detain undocumented immigrants charged with theft or violent crimes. Named after nursing student killed in Georgia.",
        latest_action_text="Passed House 263-156",
        latest_action_date=date(2025, 1, 22),
        sponsor_name="Mike Collins",
        sponsor_party="R",
        sponsor_state="GA"
    ),
    MockBill(
        id=2,
        bill_type="hr",
        bill_number=29,
        title="To provide that for purposes of determining compliance with title IX of the Education Amendments of 1972 in athletics, sex shall be recognized based solely on a person's reproductive biology and genetics at birth.",
        short_title="Protection of Women and Girls in Sports Act",
        ai_summary="Prohibits school athletic programs receiving federal funds from allowing transgender women/girls to compete on women's sports teams.",
        latest_action_text="Passed House 218-206",
        latest_action_date=date(2025, 1, 23),
        sponsor_name="Greg Steube",
        sponsor_party="R",
        sponsor_state="FL"
    ),
]

sample_votes = [
    MockVote(
        id=1, bill_id="HR2988", vote_date=date(2025, 1, 22),
        result=VoteResult.PASSED, yea_count=263, nay_count=156,
        question="On Passage", description="Laken Riley Act"
    ),
    MockVote(
        id=2, bill_id="HR2988", vote_date=date(2025, 1, 22),
        result=VoteResult.REJECTED, yea_count=145, nay_count=274,
        question="On Motion to Recommit", description="Motion to Recommit",
        amendment_author="Rep. Garcia (TX)"
    ),
    MockVote(
        id=3, bill_id="HR2988", vote_date=date(2025, 1, 22),
        result=VoteResult.AGREED_TO, yea_count=225, nay_count=198,
        question="On Ordering the Previous Question", description="Previous Question"
    ),
    MockVote(
        id=4, bill_id="HR29", vote_date=date(2025, 1, 23),
        result=VoteResult.PASSED, yea_count=218, nay_count=206,
        question="On Passage", description="Protection of Women and Girls in Sports Act"
    ),
]

sample_speeches = [
    MockSpeech(
        id=1, speaker_name="Rep. Chip Roy", speaker_party="R", speaker_state="TX",
        title="Regarding HR 2988",
        ai_summary="Argued bill is necessary to protect communities from violent criminals who should have been detained. Cited specific cases of crimes committed by released detainees.",
        content=None,
        speech_date=date(2025, 1, 22),
        related_bill_id="HR2988"
    ),
    MockSpeech(
        id=2, speaker_name="Rep. Pramila Jayapal", speaker_party="D", speaker_state="WA",
        title="In Opposition to HR 2988",
        ai_summary="Criticized bill as unconstitutional overreach that would overwhelm detention facilities. Argued it targets immigrants based on accusations, not convictions.",
        content=None,
        speech_date=date(2025, 1, 22),
        related_bill_id="HR2988"
    ),
    MockSpeech(
        id=3, speaker_name="Rep. Mike Collins", speaker_party="R", speaker_state="GA",
        title="Introduction of HR 2988",
        ai_summary="Introduced bill in memory of Laken Riley. Emphasized need for mandatory detention of criminal aliens. Called for bipartisan support for public safety.",
        content=None,
        speech_date=date(2025, 1, 22),
        related_bill_id="HR2988"
    ),
]


# Import the actual formatting functions
from formatters.bluesky import format_bill_header, format_vote_reply, format_speech_reply


def display_thread(bill, votes, speeches):
    """Display a bill thread in a visual format."""
    bill_id = f"{bill.bill_type.upper()}{bill.bill_number}"

    # Filter votes and speeches for this bill
    bill_votes = [v for v in votes if v.bill_id == bill_id]
    bill_speeches = [s for s in speeches if s.related_bill_id == bill_id]

    print(f"\n{'═' * 60}")
    print(f"BILL THREAD: {bill_id}")
    print(f"{'═' * 60}")

    # Header post
    header = format_bill_header(bill)
    print(f"\n┌{'─' * 58}┐")
    print(f"│ {'[HEADER POST]':^56} │")
    print(f"├{'─' * 58}┤")
    for line in header.split('\n'):
        # Wrap long lines
        while len(line) > 56:
            print(f"│ {line[:56]} │")
            line = line[56:]
        print(f"│ {line:<56} │")
    print(f"└{'─' * 58}┘")
    print(f"  ({len(header)} chars)")

    # Vote replies
    passage_votes = [v for v in bill_votes if "Passage" in (v.question or "")]
    other_votes = [v for v in bill_votes if "Passage" not in (v.question or "")]

    for vote in passage_votes + other_votes:
        vote_text = format_vote_reply(vote)
        print(f"\n  └─➤ ┌{'─' * 54}┐")
        print(f"      │ {'[VOTE REPLY]':^52} │")
        print(f"      ├{'─' * 54}┤")
        for line in vote_text.split('\n'):
            while len(line) > 52:
                print(f"      │ {line[:52]} │")
                line = line[52:]
            print(f"      │ {line:<52} │")
        print(f"      └{'─' * 54}┘")
        print(f"        ({len(vote_text)} chars)")

    # Speech replies
    for speech in bill_speeches[:5]:
        speech_text = format_speech_reply(speech)
        print(f"\n  └─➤ ┌{'─' * 54}┐")
        print(f"      │ {'[SPEECH REPLY]':^52} │")
        print(f"      ├{'─' * 54}┤")
        for line in speech_text.split('\n'):
            while len(line) > 52:
                print(f"      │ {line[:52]} │")
                line = line[52:]
            print(f"      │ {line:<52} │")
        print(f"      └{'─' * 54}┘")
        print(f"        ({len(speech_text)} chars)")


def main():
    print("=" * 60)
    print("BILL-CENTRIC THREAD FORMAT PREVIEW")
    print("=" * 60)
    print("""
Each bill becomes its own thread:
  📜 HEADER: Bill ID, title, summary, sponsor
    └─➤ 🗳️ VOTE: Final passage result
    └─➤ 🗳️ VOTE: Amendment/procedural votes
    └─➤ 🎤 SPEECH: Floor debate (supporting)
    └─➤ 🎤 SPEECH: Floor debate (opposing)
""")

    for bill in sample_bills:
        display_thread(bill, sample_votes, sample_speeches)

    print(f"\n{'=' * 60}")
    print("THREAD SUMMARY")
    print(f"{'=' * 60}")

    for bill in sample_bills:
        bill_id = f"{bill.bill_type.upper()}{bill.bill_number}"
        bill_votes = [v for v in sample_votes if v.bill_id == bill_id]
        bill_speeches = [s for s in sample_speeches if s.related_bill_id == bill_id]

        total_posts = 1 + len(bill_votes) + min(len(bill_speeches), 5)
        print(f"\n{bill_id}: {bill.short_title}")
        print(f"  Posts in thread: {total_posts}")
        print(f"  - 1 header")
        print(f"  - {len(bill_votes)} vote(s)")
        print(f"  - {min(len(bill_speeches), 5)} speech(es)")


if __name__ == "__main__":
    main()
