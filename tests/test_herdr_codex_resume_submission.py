"""Durable evidence that a Codex replacement already took its resume turn."""

from __future__ import annotations

from types import SimpleNamespace

import _supervisor_herdr_codex_retry


def test_live_exact_successor_marks_resume_submitted_without_a_second_paste(*, tmp_path) -> None:
    """An operator turn in the proven successor must never receive a duplicate resume."""
    writes: list[object] = []
    tmux = SimpleNamespace(
        capture_pane=lambda **kwargs: "◦ Working (1s · esc to interrupt)\n",
        bracketed_paste=lambda **kwargs: writes.append(kwargs) or True,
        send_keys=lambda **kwargs: writes.append(kwargs) or True,
    )
    sup = SimpleNamespace(
        tmux=tmux,
        sleep=lambda _seconds: None,
        live_codex={
            ("pane", "topic"): SimpleNamespace(pid=301, session_id="fresh-rollout"),
        },
    )
    current = {
        "resume": "read the durable handoff",
        "successor": {"pid": 301},
        "successor_rollout": "fresh-rollout",
    }

    submitted, reason = _supervisor_herdr_codex_retry.retry_pending(
        sup=sup,
        target="pane",
        current=current,
        record_path=tmp_path / "transaction.json",
        key="resume",
    )

    assert submitted is True
    assert reason == ""
    assert current["resume_submitted"] is True
    assert writes == []
