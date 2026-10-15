"""What the provider's refusal records are read as, and what they are not.

The reader's whole job is to be WRONG IN ONE DIRECTION: a record it cannot parse
must contribute no refusal rather than a guessed one, because a guessed refusal
rotates the fleet off a healthy account. Each case below is one way a record can
be unreadable, beside the shapes that ARE read.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from caam_decision import UsageRecord
from caam_refusal_hold import RefusalState, trigger_binding
from caam_refusal_store import RememberedRefusal, remembered_refusals
from caam_refusals import (
    WINDOW_FIVE_HOUR,
    WINDOW_SEVEN_DAY,
    Refusal,
    TrackedSession,
    session_refusals,
)

__all__: list[str] = []

RECORDED_AT = 1_800_000_000.0
RESET_AT = 1_800_003_600.0


def stamp(*, at: float) -> str:
    return datetime.fromtimestamp(at, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(*, text: str, at: float = RECORDED_AT, **extra: object) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "timestamp": stamp(at=at),
            "isApiErrorMessage": True,
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
            **extra,
        }
    )


def transcript(*, tmp_path: Path, lines: tuple[str, ...], session_id: str = "s1") -> TrackedSession:
    path = tmp_path / ".claude" / "projects" / "-repo" / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return TrackedSession(session_id=session_id, config_dir=tmp_path / ".claude")


def test_the_subscription_limit_error_is_read_with_the_reset_it_states(*, tmp_path: Path) -> None:
    session = transcript(
        tmp_path=tmp_path,
        lines=(record(text=f"Claude AI usage limit reached|{int(RESET_AT)}"),),
    )

    assert session_refusals(session=session) == (
        Refusal(recorded_at=RECORDED_AT, window=WINDOW_FIVE_HOUR, resets_at=RESET_AT),
    )


def test_a_weekly_limit_error_names_the_weekly_window(*, tmp_path: Path) -> None:
    session = transcript(
        tmp_path=tmp_path,
        lines=(record(text=f"Claude AI weekly limit reached|{int(RESET_AT)}"),),
    )

    assert session_refusals(session=session)[0].window == WINDOW_SEVEN_DAY


def test_the_measured_session_limit_phrasing_is_read_as_reporting_no_reset(
    *, tmp_path: Path
) -> None:
    """The 2026-10-13 text, whose wall-clock reset this reader does not resolve.

    It is still a refusal -- that is the whole point of reading the text rather
    than the envelope -- and reporting no reset is the conservative answer: the
    hold then lasts until the window is observed to replenish.
    """
    session = transcript(
        tmp_path=tmp_path,
        lines=(record(text="You've hit your session limit · resets 3:30am (Europe/Berlin)"),),
    )

    assert session_refusals(session=session) == (
        Refusal(recorded_at=RECORDED_AT, window=WINDOW_FIVE_HOUR, resets_at=None),
    )


def test_a_rate_limit_reset_is_its_retry_after_interval_from_when_it_was_recorded(
    *, tmp_path: Path
) -> None:
    session = transcript(
        tmp_path=tmp_path,
        lines=(
            json.dumps(
                {
                    "type": "error",
                    "timestamp": stamp(at=RECORDED_AT),
                    "error": {"type": "rate_limit_error", "message": "retry-after: 120"},
                }
            ),
        ),
    )

    assert session_refusals(session=session) == (
        Refusal(recorded_at=RECORDED_AT, window=WINDOW_FIVE_HOUR, resets_at=RECORDED_AT + 120.0),
    )


def test_a_record_naming_an_account_identity_carries_it(*, tmp_path: Path) -> None:
    session = transcript(
        tmp_path=tmp_path,
        lines=(
            record(
                text=f"Claude AI usage limit reached|{int(RESET_AT)}",
                accountUuid="uuid-anthropic-3",
            ),
        ),
    )

    assert session_refusals(session=session)[0].account == "uuid-anthropic-3"


def test_a_transcript_that_merely_discusses_a_rate_limit_carries_no_refusal(
    *, tmp_path: Path
) -> None:
    """The conjunction that matters: a phrase alone is not an error.

    The sessions this operation watches discuss rate limits constantly, and an
    assistant turn quoting one must never read as having hit one. The SECOND
    record is the shape that matters most, and it is the one this control used
    to miss: prose naming the provider's own ``rate_limit_error`` error type.
    An error marker must be STRUCTURAL -- the envelope's, not the text's --
    because a marker a sentence can satisfy is no conjunction at all, and the
    sentence a session is most likely to write about this very module carries
    it. Its weekly phrasing is deliberate too: a weekly refusal reporting no
    reset holds its account until the window is observed to replenish, so
    reading this sentence as a refusal would stand an account down for up to a
    week.
    """
    session = transcript(
        tmp_path=tmp_path,
        lines=(
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": stamp(at=RECORDED_AT),
                    "message": {
                        "role": "assistant",
                        "content": "the account hit your session limit last night",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "assistant",
                    "timestamp": stamp(at=RECORDED_AT),
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "The provider surfaces rate_limit_error when a "
                                    "weekly limit reached condition occurs."
                                ),
                            }
                        ],
                    },
                }
            ),
        ),
    )

    assert session_refusals(session=session) == ()


def test_an_api_error_naming_no_usage_limit_carries_no_refusal(*, tmp_path: Path) -> None:
    session = transcript(tmp_path=tmp_path, lines=(record(text="Overloaded: please try again"),))

    assert session_refusals(session=session) == ()


def test_a_record_with_no_time_of_its_own_carries_no_refusal(*, tmp_path: Path) -> None:
    """Attribution turns on WHEN, so an undated record is unusable rather than old."""
    session = transcript(
        tmp_path=tmp_path,
        lines=(
            json.dumps({"isApiErrorMessage": True, "text": f"usage limit reached|{int(RESET_AT)}"}),
        ),
    )

    assert session_refusals(session=session) == ()


def test_a_record_whose_time_cannot_be_parsed_carries_no_refusal(*, tmp_path: Path) -> None:
    session = transcript(
        tmp_path=tmp_path,
        lines=(
            json.dumps(
                {
                    "timestamp": "last Tuesday",
                    "isApiErrorMessage": True,
                    "text": "usage limit reached",
                }
            ),
        ),
    )

    assert session_refusals(session=session) == ()


def test_another_provider_contributes_nothing(*, tmp_path: Path) -> None:
    session = transcript(tmp_path=tmp_path, lines=(record(text="Claude AI usage limit reached"),))
    foreign = TrackedSession(
        session_id=session.session_id, config_dir=session.config_dir, provider="openai"
    )

    assert session_refusals(session=foreign) == ()


def test_a_session_with_no_transcript_at_all_contributes_nothing(*, tmp_path: Path) -> None:
    assert (
        session_refusals(
            session=TrackedSession(session_id="absent", config_dir=tmp_path / ".claude")
        )
        == ()
    )


def test_an_unreadable_transcript_contributes_nothing(*, tmp_path: Path) -> None:
    session = transcript(tmp_path=tmp_path, lines=(record(text="usage limit reached"),))
    path = tmp_path / ".claude" / "projects" / "-repo" / f"{session.session_id}.jsonl"
    path.unlink()
    path.mkdir()

    assert session_refusals(session=session) == ()


def test_only_the_tail_is_read_and_its_leading_fragment_is_dropped(*, tmp_path: Path) -> None:
    """A transcript is a whole session, so the read is bounded to its tail.

    The record pushed above the bound is the one a passing refusal would have to
    come from, and the fragment the cut leaves behind must not be read as a
    record of its own.
    """
    old = record(text=f"Claude AI usage limit reached|{int(RESET_AT)}", at=RECORDED_AT - 7_200)
    padding = tuple(
        json.dumps({"timestamp": stamp(at=RECORDED_AT), "filler": "x" * 900}) for _ in range(100)
    )
    recent = record(text=f"Claude AI usage limit reached|{int(RESET_AT)}")
    session = transcript(tmp_path=tmp_path, lines=(old, *padding, recent))

    assert session_refusals(session=session) == (
        Refusal(recorded_at=RECORDED_AT, window=WINDOW_FIVE_HOUR, resets_at=RESET_AT),
    )


def test_a_stored_refusal_missing_its_own_terms_is_not_read_back(*, tmp_path: Path) -> None:
    """A store row that cannot say what it is contributes no hold.

    The same fail-closed direction as an unparseable record: a row with no
    account, no window or no time of its own is dropped rather than defaulted,
    because every one of those fields is load-bearing for the hold it would
    otherwise impose.
    """
    del tmp_path
    state: dict[str, object] = {
        "refusals": [
            {"window": WINDOW_FIVE_HOUR, "recorded_at": RECORDED_AT},
            {"account": "a", "window": "fortnightly", "recorded_at": RECORDED_AT},
            {"account": "a", "window": WINDOW_FIVE_HOUR},
            "not a record at all",
        ]
    }

    assert remembered_refusals(state=state) == ()


def test_a_weekly_refusal_takes_the_weekly_headroom_as_zero() -> None:
    """The dimension the refusal NAMES is the one taken as zero, not the other."""
    usage = UsageRecord(
        five_hour_remaining=80.0,
        seven_day_remaining=60.0,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None,
        fable_resets_at=None,
    )
    state = RefusalState(
        held=frozenset({"a"}),
        active=RememberedRefusal(
            account="a",
            refusal=Refusal(recorded_at=RECORDED_AT, window=WINDOW_SEVEN_DAY, resets_at=RESET_AT),
            window_reset_at=None,
        ),
    )

    bound = trigger_binding(refusal=state, current=usage, active_name="a", protection_floors={})

    assert bound.dimension == WINDOW_SEVEN_DAY
    assert bound.usage.seven_day_remaining == 0.0
    assert bound.usage.five_hour_remaining == 80.0
