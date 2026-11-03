"""Exact-payload and one-Enter controls for durable Codex continuation retries."""

from __future__ import annotations

from types import SimpleNamespace

import _supervisor_config
import _supervisor_herdr_codex_retry
import pytest


def _capture(*, text: str) -> str:
    return f"● prior response\n› {text}\n  gpt-5.5 high · /repo · topic\n"


def _call(*, tmp_path, tmux, current, key="resume"):
    path = tmp_path / "transaction.json"
    return _supervisor_herdr_codex_retry.retry_pending(
        sup=SimpleNamespace(tmux=tmux, sleep=lambda _seconds: None),
        target="pane",
        current=current,
        record_path=path,
        key=key,
    )


@pytest.mark.parametrize("payload", [None, ""])
def test_retry_refuses_missing_durable_payload(*, tmp_path, payload) -> None:
    tmux = SimpleNamespace(capture_pane=lambda **kwargs: "")

    submitted, reason = _call(tmp_path=tmp_path, tmux=tmux, current={"resume": payload})

    assert submitted is False
    assert reason == "durable Codex resume payload is absent or malformed"


@pytest.mark.parametrize("capture", ["› exact\n› 1. Yes\n  2. No", _capture(text="different")])
def test_retry_refuses_gate_or_nonmatching_composer(*, tmp_path, capture: str) -> None:
    tmux = SimpleNamespace(capture_pane=lambda **kwargs: capture)

    submitted, reason = _call(tmp_path=tmp_path, tmux=tmux, current={"resume": "exact"})

    assert submitted is False
    assert reason == "pending Codex resume is absent, gated, or differs from durable text"


@pytest.mark.parametrize("attempts", [True, _supervisor_config.SUBMIT_MAX_ENTERS])
def test_retry_refuses_malformed_or_exhausted_budget(*, tmp_path, attempts) -> None:
    tmux = SimpleNamespace(capture_pane=lambda **kwargs: _capture(text="exact"))
    current = {"resume": "exact", "resume_retry_attempts": attempts}

    submitted, reason = _call(tmp_path=tmp_path, tmux=tmux, current=current)

    assert submitted is False
    assert reason == "pending Codex resume Enter retry budget is exhausted or malformed"


@pytest.mark.parametrize(
    ("outcome", "expected", "message"),
    [
        ((True, False), True, ""),
        ((False, True), False, "pending Codex resume Enter outcome is unknown"),
        ((False, False), False, "pending Codex resume Enter was not confirmed"),
    ],
)
def test_native_retry_records_budget_before_enter(
    *, tmp_path, outcome, expected: bool, message: str
) -> None:
    observed = {}

    def retry(**kwargs):
        observed.update(kwargs)
        observed["record"] = (tmp_path / "transaction.json").read_text(encoding="utf-8")
        return outcome

    tmux = SimpleNamespace(
        capture_pane=lambda **kwargs: _capture(text="exact"),
        retry_prompt_enter_once=retry,
    )
    current = {"resume": "exact"}

    submitted, reason = _call(tmp_path=tmp_path, tmux=tmux, current=current)

    assert submitted is expected
    assert reason == message
    assert current["resume_retry_attempts"] == 1
    assert '"resume_retry_attempts":1' in observed["record"]
    assert observed["session"] == "pane"
    assert observed["text"] == "exact"


@pytest.mark.parametrize(
    ("sent", "after", "expected", "message"),
    [
        (True, "◦ Working (1s • esc to interrupt)", True, ""),
        (True, _capture(text="exact"), False, "pending Codex resume Enter outcome is unknown"),
        (False, _capture(text="exact"), False, "pending Codex resume Enter was not confirmed"),
    ],
)
def test_fallback_retry_classifies_observed_submission(
    *, tmp_path, sent: bool, after: str, expected: bool, message: str
) -> None:
    frames = iter((_capture(text="exact"), after))
    keys = []
    tmux = SimpleNamespace(
        capture_pane=lambda **kwargs: next(frames),
        send_keys=lambda **kwargs: keys.append(kwargs) or sent,
    )

    submitted, reason = _call(
        tmp_path=tmp_path,
        tmux=tmux,
        current={"resume": "exact"},
    )

    assert submitted is expected
    assert reason == message
    assert keys == [{"session": "pane", "keys": "Enter"}]


def test_retry_re_pastes_only_when_the_codex_composer_is_empty(*, tmp_path) -> None:
    """Transcript text is not a pending composer payload.

    A lost first paste leaves the successor idle.  The exact resume text can still be
    visible in scrollback, but the retry must paste it afresh before it sends Enter.
    """
    captures = iter(
        (
            "● previous output quoted › exact\n› \n  gpt-5.5 high · /repo · Context 95% left\n",
            "● previous output quoted › exact\n› exact\n"
            "  gpt-5.5 high · /repo · Context 95% left\n",
        )
    )
    pastes: list[str] = []
    tmux = SimpleNamespace(
        capture_pane=lambda **kwargs: next(captures),
        bracketed_paste=lambda **kwargs: pastes.append(kwargs["text"]) or True,
        retry_prompt_enter_once=lambda **kwargs: (True, False),
    )

    submitted, reason = _call(tmp_path=tmp_path, tmux=tmux, current={"resume": "exact"})

    assert submitted is True
    assert reason == ""
    assert pastes == ["exact"]


def test_retry_reports_a_re_paste_that_never_reaches_the_composer(*, tmp_path) -> None:
    """A lost retry paste cannot be followed by an unsafe Enter."""
    captures = iter(
        (
            "› \n  gpt-5.5 high · /repo · Context 95% left\n",
            "› \n  gpt-5.5 high · /repo · Context 95% left\n",
        )
    )
    tmux = SimpleNamespace(
        capture_pane=lambda **kwargs: next(captures),
        bracketed_paste=lambda **kwargs: True,
        retry_prompt_enter_once=lambda **kwargs: pytest.fail("must not Enter without the paste"),
    )
    current = {"resume": "exact"}

    submitted, reason = _call(tmp_path=tmp_path, tmux=tmux, current=current)

    assert submitted is False
    assert reason == "pending Codex resume re-paste was not confirmed"
    assert current["resume_retry_attempts"] == 1
