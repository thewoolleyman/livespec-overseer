"""A stalled Codex Herdr replacement is retired once the pane runs a third Codex generation.

The Claude arm (overseer-rwxaqe) reads the third generation from the registry identity.
A managed Codex carrier holds no rollout file open, so the Codex arm reads it from the
pane's foreground process instead: its pid and /proc start time in the retained shell.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
from types import SimpleNamespace

import _herdr_replacement_process
import _herdr_replacement_store
import codex_sessions
import herdr_identity
import pytest
import registry
import signals
from _supervisor_view import RowView
from test_supervisor_builders import (
    FakeTmux,
    arm_ready_marker,
    codex_idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)

PREDECESSOR_ROLLOUT = "019f548d-0000-7000-8000-000000000001"
LIVE_ROLLOUT = "019f548d-0000-7000-8000-000000000009"


def _process(*, pid: int, starttime: str, pgrp: int, executable: str = "/usr/bin/codex"):
    return SimpleNamespace(
        pid=pid,
        starttime=starttime,
        executable=executable,
        argv=(executable,),
        process_group=pgrp,
        session_id=90,
    )


def _snapshot(
    *,
    live_pid: int,
    live_starttime: str,
    runtime_executable: str = "/usr/bin/codex",
    foreground: int = 500,
    shell_starttime: str = "shell-start",
):
    shell = _process(pid=100, starttime=shell_starttime, pgrp=100, executable="/bin/bash")
    leader = _process(pid=500, starttime="oob-leader", pgrp=500, executable="/usr/bin/node")
    runtime = _process(
        pid=live_pid, starttime=live_starttime, pgrp=500, executable=runtime_executable
    )
    return SimpleNamespace(
        shell=shell, foreground_group=foreground, processes=(shell, leader, runtime)
    )


def _target(*, tmp_path: Path) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=str(tmp_path / "herdr.sock"),
            server_pid=700,
            server_starttime="server-start",
            pane_id="w1:p9",
        )
    )


def _transaction(*, target: str, repo: Path) -> dict[str, object]:
    shell = _process(pid=100, starttime="shell-start", pgrp=100, executable="/bin/bash")
    successor = _process(pid=301, starttime="runtime-new", pgrp=300)
    return {
        "version": 1,
        "phase": "resume-attempted",
        "target": target,
        "server": {
            "socket_path": "/tmp/herdr.sock",
            "pid": 700,
            "starttime": "server-start",
            "pane_id": "w1:p9",
        },
        "runtime": "codex",
        "predecessor": {"pid": 201, "starttime": "runtime-old", "process_group": 200},
        "predecessor_rollout": PREDECESSOR_ROLLOUT,
        "successor": _herdr_replacement_process.process_record(process=successor),
        "shell": _herdr_replacement_process.process_record(process=shell),
        "round": {
            "ready_mtime": 1001.0,
            "round_at": 1000.0,
            "session_identity": "codex:201:runtime-old:topic",
        },
        "launch": {"command": "codex", "cwd": str(repo), "env": {}},
        "resume": "read the durable handoff",
    }


def _world(
    *,
    tmp_path: Path,
    live_pid: int,
    live_starttime: str,
    ctx: int = 100,
    snapshot_overrides: dict[str, object] | None = None,
    drop_successor: bool = False,
):
    repo, topic = make_plan(tmp_path=tmp_path)
    target = _target(tmp_path=tmp_path)
    fake = FakeTmux()
    fake.serve(session=target, repo=repo, capture=codex_idle_capture(ctx=ctx), cmd="codex")
    fake.herdr_replacement_snapshot = lambda *, session: _snapshot(
        live_pid=live_pid, live_starttime=live_starttime, **(snapshot_overrides or {})
    )
    fake.herdr_terminate = lambda **_kwargs: pytest.fail("retirement must not signal")
    fake.herdr_launch = lambda **_kwargs: pytest.fail("retirement must not launch")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1003.0)
    starttimes = {700: "server-start", 501: "oob-start", 301: "runtime-new"}
    sup.starttime_of = lambda *, pid: starttimes.get(pid)
    track = mapped_track(repo=repo, topic=topic, session=target)
    record = (
        _herdr_replacement_store.scratch_path(track=track) / _herdr_replacement_store.RECORD_NAME
    )
    transaction = _transaction(target=target, repo=repo)
    if drop_successor:
        del transaction["successor"]
    _herdr_replacement_store.durable_write(path=record, value=transaction)
    registry.write_injection_stamp(
        repo=track.repo,
        topic=track.topic,
        ts=1000.0,
        session_identity="codex:201:runtime-old:topic",
        stamp_path=sup.stamp_path,
    )
    _ = arm_ready_marker(repo=Path(track.repo), topic=track.topic, mtime=1001.0)
    return sup, fake, track, target, record


def _evaluate(*, sup, track) -> tuple[RowView, str]:
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        row = sup.evaluate(track=track, act=True)
    return row, stderr.getvalue()


@pytest.mark.parametrize("holds_session_record", [False, True], ids=["no-rollout", "rollout"])
def test_third_codex_generation_retires_the_stalled_replacement_and_its_round(
    *, tmp_path: Path, holds_session_record: bool
) -> None:
    sup, fake, track, target, record = _world(
        tmp_path=tmp_path, live_pid=501, live_starttime="oob-start"
    )
    if holds_session_record:
        sup.live_codex[(target, track.topic)] = codex_sessions.CodexSession(
            pid=501, name=track.topic, cwd=track.repo, session_id=LIVE_ROLLOUT
        )

    row, stderr = _evaluate(sup=sup, track=track)

    assert not record.exists()
    assert (
        registry.read_injection_stamp(repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path)
        is None
    )
    assert signals.read_state(repo=track.repo, topic=track.topic) is None
    assert row.status != "replacement-failed"
    assert fake.paste_texts() == []
    events = [line for line in stderr.splitlines() if "retired stalled Herdr replacement" in line]
    assert len(events) == 1
    for fragment in (track.repo, track.topic, target, "resume-attempted", "codex:501:oob-start"):
        assert fragment in events[0]


@pytest.mark.parametrize(
    ("live_pid", "live_starttime"),
    [
        pytest.param(301, "runtime-new", id="recorded-successor"),
        pytest.param(201, "runtime-old", id="recorded-predecessor"),
    ],
)
def test_a_recorded_generation_in_the_pane_is_not_retired(
    *, tmp_path: Path, live_pid: int, live_starttime: str
) -> None:
    sup, _fake, track, _target_name, record = _world(
        tmp_path=tmp_path, live_pid=live_pid, live_starttime=live_starttime
    )

    _ = _evaluate(sup=sup, track=track)

    assert record.exists()


@pytest.mark.parametrize(
    ("snapshot_overrides", "drop_successor"),
    [
        pytest.param({"runtime_executable": "/usr/bin/node"}, False, id="no-codex-process"),
        pytest.param({"foreground": 100}, False, id="shell-is-foreground"),
        pytest.param({"shell_starttime": "replaced-shell"}, False, id="retained-shell-replaced"),
        pytest.param({}, True, id="no-recorded-successor"),
    ],
)
def test_a_pane_without_a_provable_third_codex_generation_is_not_retired(
    *, tmp_path: Path, snapshot_overrides: dict[str, object], drop_successor: bool
) -> None:
    sup, _fake, track, _target_name, record = _world(
        tmp_path=tmp_path,
        live_pid=501,
        live_starttime="oob-start",
        snapshot_overrides=snapshot_overrides,
        drop_successor=drop_successor,
    )

    _ = _evaluate(sup=sup, track=track)

    assert record.exists()


def test_the_live_codex_session_is_observed_and_wrapped_up_after_retirement(
    *, tmp_path: Path
) -> None:
    sup, fake, track, target, record = _world(
        tmp_path=tmp_path, live_pid=501, live_starttime="oob-start", ctx=40
    )
    sup.live_codex[(target, track.topic)] = codex_sessions.CodexSession(
        pid=501, name=track.topic, cwd=track.repo, session_id=LIVE_ROLLOUT
    )

    row, _stderr = _evaluate(sup=sup, track=track)

    assert not record.exists()
    assert row.status == "warned"
    assert row.ctx == 40
    assert any("start wrapping up" in text for text in fake.paste_texts())
