"""Naming and resume phase boundary coverage for a proven Codex successor."""

from __future__ import annotations

from types import SimpleNamespace

import _supervisor_herdr_codex_naming
import _supervisor_herdr_codex_successor
import _supervisor_herdr_successor
import _supervisor_restart
import herdr_identity
import pytest
from test_supervisor_builders import codex_idle_capture

NEW = "019f548d-0000-7000-8000-000000000002"


def _sup(*, capture: str, paste_ok: bool = True, enter=None, keys_ok: bool = True):
    """A successor pane double. ``enter`` supplies the stateless exact-payload submitter a
    Herdr driver carries; omitting it models a driver that has none."""
    pastes: list[str] = []
    keys: list[str] = []
    pane = SimpleNamespace(
        capture_pane=lambda **kwargs: capture,
        bracketed_paste=lambda **kwargs: pastes.append(kwargs["text"]) or paste_ok,
        send_keys=lambda **kwargs: keys.append(kwargs["keys"]) or keys_ok,
        pastes=pastes,
        keys=keys,
    )
    if enter is not None:
        pane.retry_prompt_enter_once = lambda **kwargs: enter
    return SimpleNamespace(
        tmux=pane,
        codex_home="/codex",
        refresh_codex_sessions=lambda: None,
        sleep=lambda _seconds: None,
    )


def _track():
    return SimpleNamespace(topic="topic")


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("gate", "fresh Codex successor is waiting at a structured gate"),
        ("not-idle", "fresh Codex successor input is not ready"),
        ("unnamed", "fresh Codex successor was never named for this plan topic"),
    ],
)
def test_rename_refuses_unready_or_unobserved_successor(
    *, tmp_path, monkeypatch, case: str, expected: str
) -> None:
    capture = {
        "gate": "› 1. Yes, continue\n  2. No",
        "not-idle": "Codex is starting",
    }.get(case, codex_idle_capture(ctx=100))
    sup = _sup(capture=capture)
    current = {"phase": "launch-attempted"}
    monkeypatch.setattr(
        _supervisor_herdr_codex_naming.codex_sessions,
        "latest_session_for_thread_name",
        lambda **kwargs: None,
    )

    reason = _supervisor_herdr_codex_successor._rename_successor(
        sup=sup,
        track=_track(),
        target="pane",
        current=current,
        record_path=tmp_path / "record.json",
        rollout=NEW,
    )

    assert reason == expected


@pytest.mark.parametrize(
    ("case", "pane"),
    [
        ("paste-refused", {"paste_ok": False, "enter": (True, False)}),
        ("enter-never-landed", {"enter": (False, False)}),
    ],
)
def test_a_naming_submission_that_provably_missed_leaves_the_successor_unnamed(
    *, tmp_path, monkeypatch, case: str, pane: dict[str, object]
) -> None:
    """A no-turn payload holds no attempt, so a provable miss is reported, not replayed.

    Neither shape may be read as named: the index is not even consulted, because the
    payload the index would have to answer for never reached the composer.
    """
    del case
    sup = _sup(capture=codex_idle_capture(ctx=100), **pane)
    current = {"phase": "launch-attempted"}
    monkeypatch.setattr(
        _supervisor_herdr_codex_naming.codex_sessions,
        "latest_session_for_thread_name",
        lambda **kwargs: pytest.fail("a missed naming submission must never be proven named"),
    )

    reason = _supervisor_herdr_codex_successor._rename_successor(
        sup=sup,
        track=_track(),
        target="pane",
        current=current,
        record_path=tmp_path / "record.json",
        rollout=NEW,
    )

    assert reason == "fresh Codex successor was never named for this plan topic"
    assert sup.tmux.keys == []
    # The durable record still says the naming was attempted, so the next observation
    # owes this pane the guarded Enter-only retry rather than a second paste.
    assert current["phase"] == "rename-attempted"


@pytest.mark.parametrize("becomes_named", [False, True])
def test_rename_attempted_uses_only_guarded_enter_retry(
    *, tmp_path, monkeypatch, becomes_named: bool
) -> None:
    sup = _sup(capture=codex_idle_capture(ctx=100))
    current = {"phase": "rename-attempted", "rename": "/rename topic"}
    indexed = iter((None, NEW if becomes_named else None))
    monkeypatch.setattr(
        _supervisor_herdr_codex_naming.codex_sessions,
        "latest_session_for_thread_name",
        lambda **kwargs: next(indexed),
    )
    retried = []
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_herdr_codex_retry,
        "retry_pending",
        lambda **kwargs: retried.append(kwargs) or (becomes_named, "retry remained uncertain"),
    )

    reason = _supervisor_herdr_codex_successor._rename_successor(
        sup=sup,
        track=_track(),
        target="pane",
        current=current,
        record_path=tmp_path / "record.json",
        rollout=NEW,
    )

    assert reason == (None if becomes_named else "retry remained uncertain")
    assert retried[0]["key"] == "rename"
    assert current["phase"] == ("successor-observed" if becomes_named else "rename-attempted")


def test_already_named_rollout_needs_no_enter_retry(*, tmp_path, monkeypatch) -> None:
    sup = _sup(capture=codex_idle_capture(ctx=100))
    current = {"phase": "rename-attempted", "rename": "/rename topic"}
    monkeypatch.setattr(
        _supervisor_herdr_codex_naming.codex_sessions,
        "latest_session_for_thread_name",
        lambda **kwargs: NEW,
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_herdr_codex_retry,
        "retry_pending",
        lambda **kwargs: pytest.fail("named rollout must not receive Enter"),
    )

    reason = _supervisor_herdr_codex_successor._rename_successor(
        sup=sup,
        track=_track(),
        target="pane",
        current=current,
        record_path=tmp_path / "record.json",
        rollout=NEW,
    )

    assert reason is None
    assert current["phase"] == "successor-observed"


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("missing", "recorded track has no durable resume continuation"),
        ("gate", "named Codex successor is waiting at a structured gate"),
        ("not-idle", "named Codex successor input is not ready"),
        ("submit-failed", "verified Codex successor resume submission was not confirmed"),
    ],
)
def test_resume_refuses_missing_gated_busy_or_unconfirmed_input(
    *, tmp_path, monkeypatch, case: str, expected: str
) -> None:
    capture = {
        "gate": "› 1. Yes, continue\n  2. No",
        "not-idle": "Codex is starting",
    }.get(case, codex_idle_capture(ctx=100))
    current = {"phase": "successor-observed"}
    if case != "missing":
        current["resume"] = "read handoff"
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_launch,
        "submit_prompt",
        lambda **kwargs: case != "submit-failed",
    )

    reason = _supervisor_herdr_codex_successor._resume_successor(
        sup=_sup(capture=capture),
        target="pane",
        current=current,
        record_path=tmp_path / "record.json",
    )

    assert reason == expected


@pytest.mark.parametrize("submitted", [False, True])
def test_resume_attempted_uses_only_guarded_enter_retry(
    *, tmp_path, monkeypatch, submitted: bool
) -> None:
    current = {"phase": "resume-attempted", "resume": "read handoff"}
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_herdr_codex_retry,
        "retry_pending",
        lambda **kwargs: (submitted, "retry remained uncertain"),
    )

    reason = _supervisor_herdr_codex_successor._resume_successor(
        sup=_sup(capture=codex_idle_capture(ctx=100)),
        target="pane",
        current=current,
        record_path=tmp_path / "record.json",
    )

    assert reason == (None if submitted else "retry remained uncertain")
    assert current["phase"] == ("completed" if submitted else "resume-attempted")


def test_generic_successor_route_delegates_codex_transaction(*, monkeypatch) -> None:
    transaction = {"runtime": "codex"}
    delegated = []
    monkeypatch.setattr(
        _supervisor_herdr_successor._supervisor_herdr_codex_successor,
        "continue_codex_successor",
        lambda **kwargs: delegated.append(kwargs) or "codex pending",
    )

    reason = _supervisor_herdr_successor.resume_proven_successor(
        sup=SimpleNamespace(),
        track=SimpleNamespace(),
        target="pane",
        transaction=transaction,
    )

    assert reason == "codex pending"
    assert delegated[0]["transaction"] is transaction


def test_restart_routes_qualified_herdr_codex_to_durable_replacement(
    *, tmp_path, monkeypatch
) -> None:
    target = herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=str(tmp_path / "herdr.sock"),
            server_pid=700,
            server_starttime="server-start",
            pane_id="w1:p9",
        )
    )
    delegated = []
    failure = SimpleNamespace(reason="pending")
    sup = SimpleNamespace()
    track = SimpleNamespace()
    monkeypatch.setattr(
        _supervisor_restart,
        "handle_uncertified_restart_binder",
        lambda **kwargs: False,
    )
    monkeypatch.setattr(
        _supervisor_restart._supervisor_herdr_codex,
        "begin_codex_replacement",
        lambda **kwargs: delegated.append(kwargs) or failure,
    )

    result = _supervisor_restart.do_restart(
        sup=sup,
        track=track,
        target=target,
        is_codex=True,
    )

    assert result is failure
    assert delegated == [{"sup": sup, "track": track, "target": target}]
