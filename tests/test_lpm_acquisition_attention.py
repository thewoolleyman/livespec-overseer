"""Browser attention retains authority only inside its clamped deadline."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType


def _resolve(
    *, attention: ModuleType, status: str, now: float, removal_raises: bool = False
) -> tuple[object, object, list[bytearray], list[object]]:
    captures = [bytearray(b"synthetic-capture")]
    events: list[object] = []
    session = attention.AttentionSession(
        profile_ref="profile:opaque",
        remaining_steps=11,
        deadline=100.0,
        captures=captures,
    )

    def remove_artifact() -> None:
        events.append("removed")
        if removal_raises:
            raise OSError("synthetic removal failure")

    outcome = attention.resolve_attention(
        session=session,
        status=status,
        now=now,
        remove_artifact=remove_artifact,
        transition_failed=lambda reason: events.append(("failed", reason)),
    )
    return outcome, session, captures, events


def _assert_deadline_clamping(*, attention: ModuleType) -> None:
    assert (
        attention.attention_deadline(
            raised_at=90.0,
            wait_seconds=20,
            worker_deadline=100.0,
        )
        == 100.0
    )
    assert (
        attention.attention_deadline(
            raised_at=10.0,
            wait_seconds=20,
            worker_deadline=100.0,
        )
        == 30.0
    )


def _assert_timely_authority_is_preserved(*, attention: ModuleType) -> None:
    pending = _resolve(attention=attention, status="pending", now=99.0)
    assert pending[0].action == "wait"
    assert pending[0].profile_ref == "profile:opaque"
    assert pending[0].remaining_steps == 11
    assert pending[1].profile_ref == "profile:opaque"
    assert pending[1].remaining_steps == 11
    assert pending[2][0] == bytearray(b"synthetic-capture")
    assert pending[3] == []

    resumed = _resolve(attention=attention, status="resolved", now=99.0)
    assert resumed[0].action == "resume"
    assert resumed[0].profile_ref == "profile:opaque"
    assert resumed[0].remaining_steps == 11
    assert resumed[1].profile_ref == "profile:opaque"
    assert resumed[1].remaining_steps == 11
    assert resumed[2][0] == bytearray(b"synthetic-capture")
    assert resumed[3] == ["removed"]


def _assert_terminal_attention_destroys_authority(*, attention: ModuleType) -> None:
    failures = (
        ("give-up", 99.0, True),
        ("pending", 100.0, False),
        ("unknown", 99.0, False),
    )
    for status, now, removal_raises in failures:
        failed = _resolve(
            attention=attention,
            status=status,
            now=now,
            removal_raises=removal_raises,
        )
        assert failed[0].action == "failed"
        assert failed[0].profile_ref is None
        assert failed[0].remaining_steps == 0
        assert failed[1].profile_ref is None
        assert failed[1].remaining_steps == 0
        assert failed[2] == [bytearray()]
        assert failed[3] == ["removed", ("failed", "flow-unavailable")]


def test_attention_authority_is_bounded_and_cleanup_survives_removal_errors() -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_acquisition_attention.py"
    assert module_path.is_file(), "the acquisition attention boundary must be implemented"
    attention = importlib.import_module("_lpm_acquisition_attention")

    _assert_deadline_clamping(attention=attention)
    _assert_timely_authority_is_preserved(attention=attention)
    _assert_terminal_attention_destroys_authority(attention=attention)
