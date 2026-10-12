"""Public-tick proof that initial Herdr replacement observes predecessor exit directly."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import herdr_identity
import herdr_replacement_process
import pytest
import registry
import supervisor
from test_supervisor_builders import (
    FakeTmux,
    arm_ready_marker,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)


@dataclass(frozen=True, kw_only=True)
class _World:
    repo: Path
    topic: str
    sup: supervisor.Supervisor
    track: registry.Track
    counts: dict[str, int]


def _process(*, pid: int, starttime: str, executable: str, group: int) -> SimpleNamespace:
    return SimpleNamespace(
        pid=pid,
        starttime=starttime,
        executable=executable,
        argv=(executable,),
        process_group=group,
        session_id=90,
    )


def _running_snapshot() -> SimpleNamespace:
    shell = _process(pid=100, starttime="shell-start", executable="/bin/bash", group=100)
    leader = _process(pid=200, starttime="leader-start", executable="/usr/bin/node", group=200)
    runtime = _process(
        pid=201,
        starttime="runtime-start",
        executable="/usr/bin/node",
        group=200,
    )
    return SimpleNamespace(
        shell=shell,
        foreground_group=200,
        processes=(leader, runtime),
    )


def _idle_snapshot() -> SimpleNamespace:
    shell = _process(pid=100, starttime="shell-start", executable="/bin/bash", group=100)
    return SimpleNamespace(shell=shell, foreground_group=100, processes=(shell,))


def _armed_world(*, tmp_path: Path) -> _World:
    repo, topic = make_plan(tmp_path=tmp_path)
    target = herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=str(tmp_path / "herdr.sock"),
            server_pid=700,
            server_starttime="server-start",
            pane_id="w1:p9",
        )
    )
    fake = FakeTmux()
    fake.serve(session=target, repo=repo, capture=idle_capture(ctx=10), cmd="node")
    fake.pane_pid_map[target] = 100
    snapshot = {"value": _running_snapshot()}
    counts = {"signal": 0, "launch": 0}
    fake.herdr_replacement_snapshot = lambda *, session: snapshot["value"]

    def terminate(*, session: str, process_group: int) -> SimpleNamespace:
        assert session == target
        assert process_group == 200
        counts["signal"] += 1
        snapshot["value"] = _idle_snapshot()
        return SimpleNamespace(ok=True, error="")

    def launch(**_kwargs: object) -> SimpleNamespace:
        counts["launch"] += 1
        return SimpleNamespace(ok=False, effect_unknown=True, error="lost acknowledgement")

    fake.herdr_terminate = terminate
    fake.herdr_launch = launch
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1002.0)
    identity = f"claude:201:runtime-start:{topic}"
    sup.claude_identity_by_session[(target, topic)] = identity
    sup.claude_names_by_session[target] = {topic}
    sup.refresh_claude_status = lambda: None
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=identity,
        stamp_path=sup.stamp_path,
    )
    _ = arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    track = replace(
        mapped_track(repo=repo, topic=topic, session=target),
        model_profile={"harness": "claude", "model": "opus[1m]", "wrapper": None},
    )
    return _World(repo=repo, topic=topic, sup=sup, track=track, counts=counts)


@pytest.mark.parametrize(
    ("direct_observation", "expected_launches", "expected_phase", "expected_condition"),
    [
        ("same", 0, "signal-attempted", "herdr-predecessor-survived"),
        ("reused", 0, "signal-attempted", "herdr-predecessor-reused"),
        ("unreadable", 0, "signal-attempted", "herdr-predecessor-unreadable"),
        ("gone", 1, "launch-attempted", None),
    ],
)
def test_initial_public_tick_requires_direct_predecessor_absence_after_signal(
    *,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    direct_observation: str,
    expected_launches: int,
    expected_phase: str,
    expected_condition: str | None,
) -> None:
    world = _armed_world(tmp_path=tmp_path)
    monkeypatch.setattr(world.sup, "build_rows", lambda *, act: [world.track])
    observed_pids: list[int] = []

    def direct_starttime(*, pid: int) -> str | None:
        observed_pids.append(pid)
        if direct_observation == "unreadable":
            raise OSError("fixture predecessor generation unreadable")
        if direct_observation == "same":
            return "runtime-start"
        if direct_observation == "reused":
            return "reused-start"
        return None

    monkeypatch.setattr(herdr_replacement_process, "proc_starttime", direct_starttime)

    rows = world.sup.tick(act=True)

    record_path = world.repo / "tmp" / "overseer" / world.topic / ".herdr-replacement.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert observed_pids == [201]
    assert world.counts == {"signal": 1, "launch": expected_launches}
    assert record["phase"] == expected_phase
    if expected_condition is None:
        assert rows[0].status == "restarting"
    else:
        assert rows[0].status == "replacement-failed"
        assert any(key[-1] == expected_condition for key in world.sup.alerted)
