"""The Herdr hand-relaunch path judges the live registry, not the cycle-start snapshot."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import _supervisor_codex_rebind
import _supervisor_evaluate_target
import _supervisor_herdr_stall
import herdr_identity
import pytest
import registry

__all__: list[str] = []

_PREDECESSOR = "claude:3368048:853366328:topic"
_PANE_PID = 50
_CLAUDE_PID = 100
_STOP = object()


def _coordinate() -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/run/herdr.sock",
            server_pid=401,
            server_starttime="start-401",
            pane_id="w2J:p5",
        )
    )


def _setup(*, tmp_path: Path, live_name: str, live_start: str) -> tuple[SimpleNamespace, Path, str]:
    session = _coordinate()
    repo = tmp_path / "repo"
    (repo / "plan" / "topic").mkdir(parents=True)
    store = tmp_path / "mapping.jsonl"
    registry.append_mapping(
        track=registry.PlanTrack(
            topic="topic",
            repo=str(repo),
            tmux=session,
            epic="topic",
            observed_session_identity=_PREDECESSOR,
        ),
        store_path=store,
    )
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / f"{_CLAUDE_PID}.json").write_text(
        json.dumps(
            {
                "pid": _CLAUDE_PID,
                "name": live_name,
                "cwd": str(repo),
                "procStart": live_start,
                "status": "idle",
            }
        ),
        encoding="utf-8",
    )
    sup = SimpleNamespace(
        tmux=SimpleNamespace(
            renumbered_herdr_coordinate=lambda *, session, observed_session_identity, **_kwargs: (
                None if observed_session_identity == _PREDECESSOR else session
            ),
            session_exists=lambda *, session: False,
        ),
        sessions_dir=sessions,
        store_path=store,
        colliding_topics=set(),
        starttime_of=lambda *, pid: live_start if pid == _CLAUDE_PID else None,
        ppid_of=lambda *, pid: _PANE_PID if pid == _CLAUDE_PID else None,
        claude_pane_pid_to_session={_PANE_PID: session},
        claude_joined_pids={_CLAUDE_PID},
        claude_status_by_session={session: "idle"},
        claude_names_by_session={session: {"topic"}},
        claude_identity_by_session={(session, "topic"): f"claude:{_CLAUDE_PID}:old:topic"},
        log=lambda **_kwargs: None,
    )
    return sup, store, session


def _evaluate(*, sup: SimpleNamespace, store: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(_supervisor_codex_rebind, "rebound_codex_coordinate", lambda **_kw: None)
    monkeypatch.setattr(_supervisor_evaluate_target, "_unresolved_target", lambda **_kw: _STOP)
    monkeypatch.setattr(_supervisor_herdr_stall, "reconcile_and_alert", lambda **_kw: _STOP)
    track = registry.read_valid_mapping(store_path=store)[0]
    return _supervisor_evaluate_target.resolve_evaluate_target(
        sup=cast("Any", sup), track=track, act=True
    )


def _recorded(*, store: Path) -> str | None:
    return registry.read_valid_mapping(store_path=store)[0].observed_session_identity


def test_a_relaunch_records_the_live_registry_identity_not_the_snapshot(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sup, store, _session = _setup(tmp_path=tmp_path, live_name="topic", live_start="new")

    result = _evaluate(sup=sup, store=store, monkeypatch=monkeypatch)

    assert result is _STOP
    assert _recorded(store=store) == f"claude:{_CLAUDE_PID}:new:topic"


def test_a_session_renamed_since_the_snapshot_is_not_recorded_as_the_topic(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sup, store, _session = _setup(tmp_path=tmp_path, live_name="other", live_start="new")

    result = _evaluate(sup=sup, store=store, monkeypatch=monkeypatch)

    assert result is _STOP
    assert _recorded(store=store) == _PREDECESSOR
