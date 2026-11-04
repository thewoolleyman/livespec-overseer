"""Codex Herdr retry evidence that does not inspect a rollout body."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import _supervisor_herdr_codex_retry
import pane_router_submit_signals

_WRAPPED_RESUME_CAPTURE = (
    Path(__file__).parent / "fixtures" / "codex-composer" / "0.166.0-wrapped-resume.txt"
).read_text(encoding="utf-8")
_WRAPPED_RESUME = "resume plan epic … read its ledger-held plan state"
_WARNINGS_FOOTER_CAPTURE = (
    Path(__file__).parent / "fixtures" / "codex-composer" / "0.166.0-warnings-footer.txt"
).read_text(encoding="utf-8")


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


def test_composer_reader_accepts_a_cwd_statusline_without_context() -> None:
    """The cwd-bearing statusline remains a fallback when Context is absent."""
    capture = "› /rename codex-restart-proof\n  gpt-5.5 high · /repo · master · Ready\n"

    assert (
        pane_router_submit_signals.codex_composer_text(capture=capture)
        == "/rename codex-restart-proof"
    )


def test_warnings_footer_keeps_only_the_composer_for_rename_and_resume_retries(*, tmp_path) -> None:
    """A footer below Codex's statusline never becomes pending composer input."""
    resume = "resume plan epic overseer-uzvcbn in repository /data/projects/livespec-overseer"
    captures = {
        "rename": _WARNINGS_FOOTER_CAPTURE,
        "resume": _WARNINGS_FOOTER_CAPTURE.replace("/rename codex-restart-proof", resume),
    }

    for key, text in (("rename", "/rename codex-restart-proof"), ("resume", resume)):
        retries: list[dict[str, object]] = []
        tmux = SimpleNamespace(
            capture_pane=lambda capture=captures[key], **_kwargs: capture,
            retry_prompt_enter_once=lambda retries=retries, **kwargs: retries.append(kwargs)
            or (True, False),
        )

        assert pane_router_submit_signals.codex_composer_text(capture=captures[key]) == text
        submitted, reason = _supervisor_herdr_codex_retry.retry_pending(
            sup=SimpleNamespace(tmux=tmux, sleep=lambda _seconds: None),
            target="pane",
            current={key: text},
            record_path=tmp_path / f"{key}.json",
            key=key,
        )

        assert submitted is True
        assert reason == ""
        assert retries == [{"session": "pane", "text": text, "sleep": retries[0]["sleep"]}]


def test_warnings_footer_does_not_authorize_a_transcript_echo_as_composer_input() -> None:
    """Only the final composer block can authorize an Enter-only retry."""
    capture = _WARNINGS_FOOTER_CAPTURE.replace("› /rename codex-restart-proof", "› unrelated input")

    assert pane_router_submit_signals.codex_composer_text(capture=capture) == "unrelated input"


def test_wrapped_codex_resume_above_a_spacer_is_retried_with_enter(*, tmp_path) -> None:
    """The measured 0.166 composer layout retains its exact durable resume payload."""
    retries: list[dict[str, object]] = []
    tmux = SimpleNamespace(
        capture_pane=lambda **_kwargs: _WRAPPED_RESUME_CAPTURE,
        retry_prompt_enter_once=lambda **kwargs: retries.append(kwargs) or (True, False),
    )

    submitted, reason = _supervisor_herdr_codex_retry.retry_pending(
        sup=SimpleNamespace(tmux=tmux, sleep=lambda _seconds: None),
        target="pane",
        current={"resume": _WRAPPED_RESUME},
        record_path=tmp_path / "transaction.json",
        key="resume",
    )

    assert submitted is True
    assert reason == ""
    assert retries == [{"session": "pane", "text": _WRAPPED_RESUME, "sleep": retries[0]["sleep"]}]


def test_spacer_above_codex_statusline_preserves_an_empty_composer() -> None:
    """A blank spacer is layout, rather than composer content."""
    capture = _WRAPPED_RESUME_CAPTURE.replace(
        "› resume plan epic … read its\n  ledger-held plan state", "› "
    )

    assert pane_router_submit_signals.codex_composer_empty(capture=capture) is True


def test_other_text_in_a_spaced_codex_composer_never_retries_enter(*, tmp_path) -> None:
    """Only the exact durable payload may authorize the bounded Enter retry."""
    retries: list[object] = []
    capture = _WRAPPED_RESUME_CAPTURE.replace(
        "› resume plan epic … read its\n  ledger-held plan state", "› unrelated operator text"
    )
    tmux = SimpleNamespace(
        capture_pane=lambda **_kwargs: capture,
        retry_prompt_enter_once=lambda **kwargs: retries.append(kwargs) or (True, False),
    )

    submitted, reason = _supervisor_herdr_codex_retry.retry_pending(
        sup=SimpleNamespace(tmux=tmux, sleep=lambda _seconds: None),
        target="pane",
        current={"resume": _WRAPPED_RESUME},
        record_path=tmp_path / "transaction.json",
        key="resume",
    )

    assert submitted is False
    assert reason == "pending Codex resume is absent, gated, or differs from durable text"
    assert retries == []
