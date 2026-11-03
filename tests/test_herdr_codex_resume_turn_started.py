"""Codex Herdr retry evidence that does not inspect a rollout body."""

from __future__ import annotations

from types import SimpleNamespace

import _supervisor_herdr_codex_retry
import pane_router_submit_signals


def test_idle_successor_re_pastes_instead_of_counting_its_identity_as_a_turn(*, tmp_path) -> None:
    """A fresh, idle successor has not begun the durable resume turn yet."""
    captures = iter(
        (
            "● transcript quote: exact\n› \n  gpt-5.5 high · /repo · Context 95% left\n",
            "● transcript quote: exact\n› exact\n  gpt-5.5 high · /repo · Context 95% left\n",
        )
    )
    writes: list[dict[str, str]] = []
    tmux = SimpleNamespace(
        capture_pane=lambda **kwargs: next(captures),
        bracketed_paste=lambda **kwargs: writes.append(kwargs) or True,
        retry_prompt_enter_once=lambda **kwargs: (True, False),
    )
    sup = SimpleNamespace(
        tmux=tmux,
        sleep=lambda _seconds: None,
        live_codex={
            ("pane", "topic"): SimpleNamespace(pid=301, session_id="fresh-rollout"),
        },
    )
    current = {
        "resume": "exact",
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
    assert writes == [{"session": "pane", "text": "exact"}]


def test_busy_successor_marks_resume_submitted_without_another_write(*, tmp_path) -> None:
    """An active successor turn is sufficient submission evidence without rollout reads."""
    writes: list[object] = []
    tmux = SimpleNamespace(
        capture_pane=lambda **kwargs: "◦ Working (1s · esc to interrupt)\n",
        bracketed_paste=lambda **kwargs: writes.append(kwargs) or True,
        send_keys=lambda **kwargs: writes.append(kwargs) or True,
    )
    sup = SimpleNamespace(tmux=tmux, sleep=lambda _seconds: None, live_codex={})
    current = {"resume": "exact"}

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


def test_composer_reader_rejects_a_statusline_without_a_composer_row() -> None:
    """Only the actual composer row immediately above the statusline counts."""
    capture = "transcript only\n  gpt-5.5 high · /repo · Context 95% left\n"

    assert pane_router_submit_signals.codex_composer_text(capture=capture) is None
