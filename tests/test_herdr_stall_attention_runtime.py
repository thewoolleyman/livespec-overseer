"""The Codex-only manual recovery steps are never offered for a Claude replacement."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import _herdr_replacement_store
import _supervisor_herdr_stall
import test_herdr_dead_generation_replacement as fixture

__all__: list[str] = []

_MANUAL = "Manual steps"


def _alerted(*, tmp_path: Path, runtime: str) -> list[str]:
    sup, track, scratch = fixture._setup(
        tmp_path=tmp_path,
        running={
            fixture._LIVE_PID: f"start-{fixture._LIVE_PID}",
            fixture._DEAD_PID: f"start-{fixture._DEAD_PID}",
        },
    )
    record = scratch / _herdr_replacement_store.RECORD_NAME
    transaction = _herdr_replacement_store.read_transaction(path=record)
    assert transaction is not None
    transaction["runtime"] = runtime
    _herdr_replacement_store.durable_write(path=record, value=transaction)
    messages: list[str] = []
    sup.alert = lambda **kwargs: messages.append(kwargs["message"])  # pyright: ignore[reportAttributeAccessIssue]
    _ = _supervisor_herdr_stall.reconcile_and_alert(
        sup=sup,
        track=track,
        target=fixture._coordinate(pid=fixture._LIVE_PID),
        act=False,
        alert=True,
    )
    return messages


def test_a_stalled_claude_replacement_gets_no_codex_rename_steps(*, tmp_path: Path) -> None:
    messages = _alerted(tmp_path=tmp_path, runtime="claude")

    assert len(messages) == 1
    assert "phase resume-attempted" in messages[0]
    assert _MANUAL not in messages[0]
    assert "/rename" not in messages[0]


def test_a_stalled_codex_replacement_keeps_the_manual_steps(*, tmp_path: Path) -> None:
    messages = _alerted(tmp_path=tmp_path, runtime="codex")

    assert len(messages) == 1
    assert "Manual steps: /rename topic, then submit the durable resume line." in messages[0]


def test_the_claude_message_helper_stays_generic_for_both_stalled_phases() -> None:
    for phase in ("launch-attempted", "resume-attempted"):
        message = _supervisor_herdr_stall.stall_attention_message(
            track=SimpleNamespace(repo="/repo", topic="topic"),
            target="w2:p1",
            phase=phase,
            runtime="claude",
            reason="boom",
        )

        assert message == (
            f"herdr replacement stalled for /repo::topic at pane w2:p1; phase {phase}: boom."
        )
