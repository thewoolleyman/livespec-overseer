"""A replacement left open on a DEAD herdr server generation is retired (overseer-nztq44).

Measured on daemon 5.33.0, 2026-10-20: `agent-session-stall-prevention` had a durable
replacement at `resume-attempted` since 2026-10-14, bound to herdr server 3384132. The
host power-off of 2026-10-19 killed that server, and every process the record names went
with it. No observation could ever satisfy or refute the record again, so the bare-shell
gate refused the track as `replacement-failed` on every tick, forever, and the
server-restart re-adoption (overseer-rwrkkr) left it alone because an unfinished
replacement owned it.

A record whose recorded server generation is PROVABLY gone (its pid no longer runs with
the recorded start time) can do no further harm, so an acting tick retires it: the
record is kept intact as a diagnostic file, the predecessor's own `ready` stops being a
declaration, and the track takes its ordinary classification. A generation that still
runs keeps refusing, and the read-only path never retires anything.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import _herdr_replacement_store
import _supervisor_herdr_stall
import herdr_identity
import registry
import signals
import supervisor

__all__: list[str] = []

_SOCKET = "/home/ubuntu/.config/herdr/herdr.sock"
_DEAD_PID = 3384132
_LIVE_PID = 169821
_READY_MTIME = 1791985519.0


def _coordinate(*, pid: int) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=_SOCKET,
            server_pid=pid,
            server_starttime=f"start-{pid}",
            pane_id="w2H:p6",
        )
    )


def _transaction() -> dict[str, object]:
    return {
        "version": 1,
        "phase": "resume-attempted",
        "target": _coordinate(pid=_DEAD_PID),
        "runtime": "claude",
        "server": {
            "socket_path": _SOCKET,
            "pid": _DEAD_PID,
            "starttime": f"start-{_DEAD_PID}",
            "pane_id": "w2H:p6",
        },
        "predecessor": {"pid": 969525, "process_group": 969525, "starttime": "834585961"},
        "shell": {
            "pid": 2676862,
            "process_group": 2676862,
            "session_id": 2676862,
            "starttime": "778473807",
            "executable": "/usr/bin/zsh",
            "argv": ["/usr/bin/zsh"],
        },
        "successor": {
            "pid": 1367373,
            "process_group": 1367373,
            "session_id": 2676862,
            "starttime": "835708448",
            "executable": "/usr/bin/claude",
            "argv": ["claude", "-n", "topic"],
        },
        "round": {
            "ready_mtime": _READY_MTIME,
            "round_at": _READY_MTIME - 97.0,
            "session_identity": "claude:969525:834585961:topic",
        },
        "launch": {
            "command": "claude --dangerously-skip-permissions -n topic",
            "cwd": "/repo",
            "env": {"ANTHROPIC_MODEL": None},
        },
        "resume": "resume plan epic topic in repository /repo; read its ledger-held plan state",
    }


def _setup(
    *, tmp_path: Path, running: dict[int, str]
) -> tuple[supervisor.Supervisor, registry.Track, Path]:
    repo = tmp_path / "repo"
    (repo / "plan" / "topic").mkdir(parents=True)
    store = tmp_path / "mapping.jsonl"
    registry.append_mapping(
        track=registry.PlanTrack(
            topic="topic",
            repo=str(repo),
            tmux=_coordinate(pid=_LIVE_PID),
            epic="topic",
            observed_session_identity="claude:969525:834585961:topic",
        ),
        store_path=store,
    )
    track = registry.read_valid_mapping(store_path=store)[0]
    scratch = _herdr_replacement_store.scratch_path(track=track)
    _herdr_replacement_store.durable_write(
        path=scratch / _herdr_replacement_store.RECORD_NAME, value=_transaction()
    )
    state = signals.state_path(repo=str(repo), topic="topic")
    _ = state.write_text("ready\n", encoding="utf-8")
    os.utime(state, (_READY_MTIME, _READY_MTIME))
    sup = supervisor.Supervisor(
        tmux=SimpleNamespace(pane_pid_sessions=dict, capture_pane=lambda **_kwargs: ""),
        store_path=store,
        stamp_path=tmp_path / "stamps.json",
        out=io.StringIO(),
        require_render_terminal=False,
        now=lambda: 1792460000.0,
        sleep=lambda _seconds: None,
        codex_home=tmp_path / "no-codex",
        codex_pids_of_comm=lambda *, comm: [],
        runtime_model_of=lambda *, pid: None,
    )
    sup.starttime_of = lambda *, pid: running.get(pid)
    return sup, track, scratch


def _retired(*, scratch: Path) -> list[Path]:
    return sorted(scratch.glob(".herdr-replacement.retired-*.json"))


def test_an_acting_tick_retires_a_replacement_on_a_dead_server_generation(
    *, tmp_path: Path
) -> None:
    sup, track, scratch = _setup(tmp_path=tmp_path, running={_LIVE_PID: f"start-{_LIVE_PID}"})

    row = _supervisor_herdr_stall.reconcile_and_alert(
        sup=sup, track=track, target=_coordinate(pid=_LIVE_PID), act=True, alert=True
    )

    retired = _retired(scratch=scratch)
    assert row is None
    assert not (scratch / _herdr_replacement_store.RECORD_NAME).exists()
    assert len(retired) == 1
    assert json.loads(retired[0].read_text(encoding="utf-8")) == _transaction()


def test_the_retired_replacements_own_ready_no_longer_declares_anything(*, tmp_path: Path) -> None:
    sup, track, _scratch = _setup(tmp_path=tmp_path, running={_LIVE_PID: f"start-{_LIVE_PID}"})

    _ = _supervisor_herdr_stall.reconcile_and_alert(
        sup=sup, track=track, target=_coordinate(pid=_LIVE_PID), act=True, alert=True
    )

    state = signals.read_state(repo=track.repo, topic=track.topic)
    assert state is not None
    assert state.token == signals.STATE_READY_EXPIRED


def test_the_retirement_raises_one_alert_naming_the_dead_generation_and_the_record(
    *, tmp_path: Path
) -> None:
    sup, track, scratch = _setup(tmp_path=tmp_path, running={_LIVE_PID: f"start-{_LIVE_PID}"})

    _ = _supervisor_herdr_stall.reconcile_and_alert(
        sup=sup, track=track, target=_coordinate(pid=_LIVE_PID), act=True, alert=True
    )

    messages = [
        message
        for (_repo, topic, condition), message in sup.alerted.items()
        if topic == "topic" and condition == "herdr-replacement-retired"
    ]
    assert len(messages) == 1
    assert f"{_DEAD_PID}/start-{_DEAD_PID}" in str(messages[0])
    assert _retired(scratch=scratch)[0].name in str(messages[0])


def test_a_track_still_naming_the_dead_generation_is_retired_on_an_acting_tick(
    *, tmp_path: Path
) -> None:
    sup, track, scratch = _setup(tmp_path=tmp_path, running={_LIVE_PID: f"start-{_LIVE_PID}"})

    row = _supervisor_herdr_stall.reconcile_and_alert(
        sup=sup, track=track, target=_coordinate(pid=_DEAD_PID), act=False, alert=True
    )

    assert row is None
    assert len(_retired(scratch=scratch)) == 1


def test_a_replacement_whose_server_generation_still_runs_keeps_refusing(*, tmp_path: Path) -> None:
    sup, track, scratch = _setup(
        tmp_path=tmp_path,
        running={_DEAD_PID: f"start-{_DEAD_PID}", _LIVE_PID: f"start-{_LIVE_PID}"},
    )

    row = _supervisor_herdr_stall.reconcile_and_alert(
        sup=sup, track=track, target=_coordinate(pid=_LIVE_PID), act=True, alert=True
    )

    assert row is not None
    assert row.status == "replacement-failed"
    assert (scratch / _herdr_replacement_store.RECORD_NAME).exists()
    assert _retired(scratch=scratch) == []
    state = signals.read_state(repo=track.repo, topic=track.topic)
    assert state is not None
    assert state.token == signals.STATE_READY


def test_a_reused_server_pid_is_still_a_dead_generation(*, tmp_path: Path) -> None:
    sup, track, scratch = _setup(
        tmp_path=tmp_path,
        running={_DEAD_PID: "start-of-a-reused-pid", _LIVE_PID: f"start-{_LIVE_PID}"},
    )

    _ = _supervisor_herdr_stall.reconcile_and_alert(
        sup=sup, track=track, target=_coordinate(pid=_LIVE_PID), act=True, alert=True
    )

    assert len(_retired(scratch=scratch)) == 1


def test_the_read_only_path_never_retires_a_replacement(*, tmp_path: Path) -> None:
    sup, track, scratch = _setup(tmp_path=tmp_path, running={_LIVE_PID: f"start-{_LIVE_PID}"})

    row = _supervisor_herdr_stall.reconcile_and_alert(
        sup=sup, track=track, target=_coordinate(pid=_LIVE_PID), act=False, alert=False
    )

    assert row is not None
    assert row.status == "replacement-failed"
    assert (scratch / _herdr_replacement_store.RECORD_NAME).exists()
    assert _retired(scratch=scratch) == []
