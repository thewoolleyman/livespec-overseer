"""Durable, ready-only replacement of a supervised process in a Herdr pane."""

from __future__ import annotations

import fcntl
import json
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import herdr_identity
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


@dataclass(kw_only=True)
class _World:
    repo: Path
    topic: str
    target: str
    fake: FakeTmux
    snapshot: dict[str, SimpleNamespace]
    observed_at_signal: dict[str, object]


def _target(*, tmp_path: Path) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=str(tmp_path / "herdr.sock"),
            server_pid=700,
            server_starttime="server-start",
            pane_id="w1:p9",
        )
    )


def _process(*, pid: int, starttime: str, executable: str, pgrp: int) -> SimpleNamespace:
    return SimpleNamespace(
        pid=pid,
        starttime=starttime,
        executable=executable,
        argv=(executable,),
        process_group=pgrp,
        session_id=90,
    )


def _running_snapshot() -> SimpleNamespace:
    shell = _process(pid=100, starttime="shell-start", executable="/bin/bash", pgrp=100)
    leader = _process(pid=200, starttime="leader-start", executable="/usr/bin/node", pgrp=200)
    runtime = _process(pid=201, starttime="runtime-start", executable="/usr/bin/node", pgrp=200)
    return SimpleNamespace(
        ok=True,
        error="",
        shell=shell,
        foreground_group=200,
        processes=(leader, runtime),
    )


def _idle_snapshot() -> SimpleNamespace:
    shell = _process(pid=100, starttime="shell-start", executable="/bin/bash", pgrp=100)
    return SimpleNamespace(
        ok=True,
        error="",
        shell=shell,
        foreground_group=100,
        processes=(shell,),
    )


def _configure_fake(*, world: _World) -> None:
    def replacement_snapshot(*, session: str) -> SimpleNamespace:
        assert session == world.target
        return world.snapshot["value"]

    def terminate(*, session: str, process_group: int) -> SimpleNamespace:
        assert session == world.target
        assert process_group == 200
        scratch = world.repo / "tmp" / "overseer" / world.topic
        world.observed_at_signal.update(
            json.loads((scratch / ".herdr-replacement.json").read_text(encoding="utf-8"))
        )
        with (scratch / ".herdr-replacement.lock").open("a+", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                world.observed_at_signal["lock_held"] = False
            except BlockingIOError:
                world.observed_at_signal["lock_held"] = True
        world.snapshot["value"] = _idle_snapshot()
        return SimpleNamespace(ok=True, error="")

    world.fake.herdr_replacement_snapshot = replacement_snapshot
    world.fake.herdr_terminate = terminate
    world.fake.herdr_launch = lambda **_kwargs: SimpleNamespace(
        ok=False,
        effect_unknown=True,
        error="lost launch acknowledgement",
    )


def _armed_world(*, tmp_path: Path) -> tuple[_World, supervisor.Supervisor, registry.Track]:
    repo, topic = make_plan(tmp_path=tmp_path)
    target = _target(tmp_path=tmp_path)
    fake = FakeTmux()
    fake.serve(session=target, repo=repo, capture=idle_capture(ctx=10), cmd="node")
    fake.pane_pid_map[target] = 100
    world = _World(
        repo=repo,
        topic=topic,
        target=target,
        fake=fake,
        snapshot={"value": _running_snapshot()},
        observed_at_signal={},
    )
    _configure_fake(world=world)
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
    return world, sup, track


def test_ready_authorization_is_durably_bound_before_the_herdr_signal(*, tmp_path: Path) -> None:
    world, sup, track = _armed_world(tmp_path=tmp_path)

    sup.evaluate(track=track, act=True)

    observed = world.observed_at_signal
    assert observed["lock_held"] is True
    assert observed["phase"] == "signal-attempted"
    assert observed["target"] == world.target
    assert observed["runtime"] == "claude"
    assert observed["predecessor"] == {
        "pid": 201,
        "starttime": "runtime-start",
        "process_group": 200,
    }
    assert observed["shell"] == {
        "pid": 100,
        "starttime": "shell-start",
        "executable": "/bin/bash",
        "argv": ["/bin/bash"],
        "process_group": 100,
        "session_id": 90,
    }
    assert observed["round"] == {
        "ready_mtime": 1001.0,
        "round_at": 1000.0,
        "session_identity": f"claude:201:runtime-start:{world.topic}",
    }
    launch = observed["launch"]
    assert isinstance(launch, dict)
    assert launch["command"].startswith("claude --model 'opus[1m]'")
    assert launch["cwd"] == str(world.repo)
    assert launch["env"]["ANTHROPIC_MODEL"] is None
