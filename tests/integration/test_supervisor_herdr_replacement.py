"""Durable, ready-only replacement of a supervised process in a Herdr pane."""

from __future__ import annotations

import fcntl
import json
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import IO, cast

import _supervisor_herdr_replacement
import _supervisor_state
import herdr_adapter
import herdr_calls
import herdr_identity
import herdr_replacement_process
import herdr_write
import pane_router
import pane_router_reads
import pane_router_submit_signals
import pytest
import registry
import signals
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


def _arm_hazard(
    *,
    hazard: str,
    world: _World,
    monkeypatch: pytest.MonkeyPatch,
) -> IO[str] | None:
    if hazard == "lock-failed":
        lock = world.repo / "tmp" / "overseer" / world.topic / ".herdr-replacement.lock"
        handle = lock.open("a+", encoding="utf-8")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handle
    if hazard == "write-failed":

        def fail_write(**_kwargs: object) -> None:
            raise OSError("fixture durable write failure")

        monkeypatch.setattr(_supervisor_herdr_replacement, "_durable_write", fail_write)
    elif hazard == "changed-interlock":
        original = world.fake.herdr_replacement_snapshot

        def remove_ready(*, session: str) -> SimpleNamespace:
            snapshot = original(session=session)
            signals.state_path(repo=str(world.repo), topic=world.topic).unlink()
            return snapshot

        world.fake.herdr_replacement_snapshot = remove_ready
    elif hazard == "reused-process-identity":
        reused = _running_snapshot()
        reused.processes[-1].starttime = "reused-start"
        world.snapshot["value"] = reused
    else:
        running = _running_snapshot()
        running.shell = running.processes[-1]
        world.snapshot["value"] = running
    return None


@pytest.mark.parametrize(
    "hazard",
    [
        "lock-failed",
        "write-failed",
        "changed-interlock",
        "reused-process-identity",
        "exec-replaced-root-shell",
    ],
)
def test_replacement_prerequisite_failure_never_signals(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hazard: str
) -> None:
    world, sup, track = _armed_world(tmp_path=tmp_path)
    signal_count = 0

    def count_signal(*, session: str, process_group: int) -> SimpleNamespace:
        nonlocal signal_count
        signal_count += 1
        return SimpleNamespace(ok=True, error="")

    world.fake.herdr_terminate = count_signal
    held_lock = _arm_hazard(hazard=hazard, world=world, monkeypatch=monkeypatch)
    try:
        sup.evaluate(track=track, act=True)
    finally:
        if held_lock is not None:
            held_lock.close()

    assert signal_count == 0
    assert any(key[-1] == "herdr-replacement-refused" for key in sup.alerted)


def test_round_lost_after_ready_certification_is_restored_for_the_next_tick(
    *, tmp_path: Path
) -> None:
    world, sup, track = _armed_world(tmp_path=tmp_path)
    original_snapshot = world.fake.herdr_replacement_snapshot
    lose_round = True

    def snapshot_after_round_loss(*, session: str) -> SimpleNamespace:
        nonlocal lose_round
        snapshot = original_snapshot(session=session)
        if lose_round:
            lose_round = False
            registry.clear_injection_stamp(
                repo=track.repo,
                topic=track.topic,
                stamp_path=sup.stamp_path,
            )
        return snapshot

    world.fake.herdr_replacement_snapshot = snapshot_after_round_loss

    refused = sup.evaluate(track=track, act=True)

    declared = signals.read_state(repo=track.repo, topic=track.topic)
    restored_round = registry.read_round_record(
        repo=track.repo,
        topic=track.topic,
        stamp_path=sup.stamp_path,
    )
    assert refused.status == "replacement-failed"
    assert declared is not None and declared.token == signals.STATE_READY
    assert restored_round.at == 1000.0
    assert restored_round.session_identity == f"claude:201:runtime-start:{track.topic}"
    assert world.observed_at_signal == {}

    retried = sup.evaluate(track=track, act=True)

    assert retried.status == "restarting"
    assert world.observed_at_signal["phase"] == "signal-attempted"


def test_surviving_predecessor_receives_only_one_signal_per_ready_round(*, tmp_path: Path) -> None:
    world, sup, track = _armed_world(tmp_path=tmp_path)
    signal_count = 0

    def leave_predecessor_live(*, session: str, process_group: int) -> SimpleNamespace:
        nonlocal signal_count
        signal_count += 1
        return SimpleNamespace(ok=True, error="")

    world.fake.herdr_terminate = leave_predecessor_live

    sup.evaluate(track=track, act=True)
    sup.evaluate(track=track, act=True)

    record = json.loads(
        (world.repo / "tmp" / "overseer" / world.topic / ".herdr-replacement.json").read_text(
            encoding="utf-8"
        )
    )
    assert signal_count == 1
    assert record["phase"] == "signal-attempted"
    assert any(key[-1] == "herdr-predecessor-survived" for key in sup.alerted)


@pytest.mark.parametrize(("foreign_foreground", "expected_launches"), [(False, 1), (True, 0)])
def test_successor_launch_is_fenced_and_requires_the_original_idle_shell(
    *, tmp_path: Path, foreign_foreground: bool, expected_launches: int
) -> None:
    world, sup, track = _armed_world(tmp_path=tmp_path)
    launches: list[dict[str, object]] = []

    def stop(*, session: str, process_group: int) -> SimpleNamespace:
        idle = _idle_snapshot()
        if foreign_foreground:
            foreign = _process(pid=300, starttime="foreign", executable="sleep", pgrp=300)
            idle.foreground_group = 300
            idle.processes = (*idle.processes, foreign)
        world.snapshot["value"] = idle
        return SimpleNamespace(ok=True, error="")

    def launch(**kwargs: object) -> SimpleNamespace:
        record_path = world.repo / "tmp" / "overseer" / world.topic / ".herdr-replacement.json"
        launches.append({"kwargs": kwargs, "record": json.loads(record_path.read_text())})
        return SimpleNamespace(ok=False, effect_unknown=True, error="lost acknowledgement")

    world.fake.herdr_terminate = stop
    world.fake.herdr_launch = launch
    sup.evaluate(track=track, act=True)

    assert len(launches) == expected_launches
    if launches:
        assert launches[0]["record"]["phase"] == "launch-attempted"


@pytest.mark.parametrize("phase", ["stopped-awaiting-shell", "launch-attempted"])
def test_recreated_supervisor_recovers_only_a_never_attempted_launch(
    *, tmp_path: Path, phase: str
) -> None:
    world, first, track = _armed_world(tmp_path=tmp_path)
    counts = {"signal": 0, "launch": 0}

    def stop(*, session: str, process_group: int) -> SimpleNamespace:
        counts["signal"] += 1
        world.snapshot["value"] = _idle_snapshot()
        if phase == "stopped-awaiting-shell":
            world.snapshot["value"].foreground_group = 300
        return SimpleNamespace(ok=True, error="")

    def launch(**_kwargs: object) -> SimpleNamespace:
        counts["launch"] += 1
        return SimpleNamespace(ok=False, effect_unknown=True, error="lost acknowledgement")

    world.fake.herdr_terminate = stop
    world.fake.herdr_launch = launch
    first.evaluate(track=track, act=True)
    world.snapshot["value"] = _idle_snapshot()
    world.fake.cmds[world.target] = "bash"
    recreated = make_supervisor(tmp_path=tmp_path, fake=world.fake, now=lambda: 1003.0)

    recreated.evaluate(track=track, act=True)

    assert counts == {"signal": 1, "launch": 1}


class _ProcStatPath:
    def __init__(self, samples: list[object]) -> None:
        self.samples = samples

    def read_text(self, *, encoding: str) -> str:
        sample = self.samples.pop(0)
        if isinstance(sample, BaseException):
            raise sample
        return cast(str, sample)


def _proc_stat(*, starttime: str) -> str:
    return "1 (agent) S 1 200 90 " + " ".join(["0"] * 15 + [starttime])


@pytest.mark.parametrize(
    ("samples", "expected", "error"),
    [
        ([_proc_stat(starttime="same"), _proc_stat(starttime="same")], "same", None),
        ([FileNotFoundError(), FileNotFoundError()], None, None),
        ([PermissionError("unreadable")], None, "unreadable"),
        ([_proc_stat(starttime="one"), _proc_stat(starttime="two")], None, "changed"),
        (["malformed"], None, "malformed"),
    ],
)
def test_predecessor_generation_reader_requires_stable_direct_proc_evidence(
    *,
    monkeypatch: pytest.MonkeyPatch,
    samples: list[object],
    expected: str | None,
    error: str | None,
) -> None:
    reader = getattr(herdr_replacement_process, "proc_starttime", None)
    assert reader is not None, "recovery needs a direct stable predecessor-generation reader"
    monkeypatch.setattr(
        herdr_replacement_process,
        "Path",
        lambda _value: _ProcStatPath(samples),
    )

    if error is None:
        assert reader(pid=201) == expected
    else:
        with pytest.raises(OSError, match=error):
            reader(pid=201)


def _stopped_transaction(*, tmp_path: Path) -> tuple[_World, registry.Track, dict[str, int], Path]:
    world, first, track = _armed_world(tmp_path=tmp_path)
    counts = {"signal": 0, "launch": 0}

    def stop(*, session: str, process_group: int) -> SimpleNamespace:
        counts["signal"] += 1
        busy = _idle_snapshot()
        busy.foreground_group = 300
        world.snapshot["value"] = busy
        return SimpleNamespace(ok=True, error="")

    def launch(**_kwargs: object) -> SimpleNamespace:
        counts["launch"] += 1
        return SimpleNamespace(ok=True, effect_unknown=False, error="")

    world.fake.herdr_terminate = stop
    world.fake.herdr_launch = launch
    first.evaluate(track=track, act=True)
    record_path = world.repo / "tmp" / "overseer" / world.topic / ".herdr-replacement.json"
    return world, track, counts, record_path


@pytest.mark.parametrize("predecessor_observation", ["live", "unreadable"])
def test_recreated_public_tick_refuses_a_live_or_unreadable_recorded_predecessor(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    predecessor_observation: str,
) -> None:
    world, track, counts, record_path = _stopped_transaction(tmp_path=tmp_path)
    world.snapshot["value"] = _idle_snapshot()
    world.fake.cmds[world.target] = "bash"
    world.fake.calls.clear()
    recreated = make_supervisor(tmp_path=tmp_path, fake=world.fake, now=lambda: 1003.0)
    monkeypatch.setattr(recreated, "build_rows", lambda *, act: [track])

    def observe_predecessor(*, pid: int) -> str | None:
        assert pid == 201
        if predecessor_observation == "unreadable":
            raise OSError("fixture predecessor generation unreadable")
        return "runtime-start"

    monkeypatch.setattr(
        herdr_replacement_process,
        "proc_starttime",
        observe_predecessor,
        raising=False,
    )

    rows = recreated.tick(act=True)

    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert counts == {"signal": 1, "launch": 0}
    assert record["phase"] == "stopped-awaiting-shell"
    assert [row.status for row in rows] == ["replacement-failed"]
    assert "predecessor" in rows[0].note


@pytest.mark.parametrize(
    ("record_case", "act", "expected_status"),
    [
        ("absent", True, "session-gone"),
        ("malformed", True, "replacement-failed"),
        ("mismatched", True, "replacement-failed"),
        ("valid-read-only", False, "replacement-pending"),
    ],
)
def test_public_tick_never_acts_on_an_unusable_bare_shell_transaction(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_case: str,
    act: bool,
    expected_status: str,
) -> None:
    world, track, counts, record_path = _stopped_transaction(tmp_path=tmp_path)
    if record_case == "absent":
        record_path.unlink()
    elif record_case == "malformed":
        record_path.write_text("{not-json", encoding="utf-8")
    elif record_case == "mismatched":
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["target"] = _target(tmp_path=tmp_path / "other")
        record_path.write_text(json.dumps(record), encoding="utf-8")
    world.snapshot["value"] = _idle_snapshot()
    world.fake.cmds[world.target] = "bash"
    world.fake.calls.clear()
    counts["signal"] = 0
    recreated = make_supervisor(tmp_path=tmp_path, fake=world.fake, now=lambda: 1003.0)
    monkeypatch.setattr(recreated, "build_rows", lambda *, act: [track])

    try:
        rows = recreated.tick(act=act)
        statuses = [row.status for row in rows]
    except (OSError, TypeError, ValueError):
        statuses = ["uncaught-transaction-error"]

    input_calls = [call for call in world.fake.calls if call[0] in {"keys", "paste"}]
    assert counts == {"signal": 0, "launch": 0}
    assert input_calls == []
    assert expected_status in statuses


@pytest.mark.parametrize(
    ("hazard", "expected_signals", "condition"),
    [
        ("foreground-changed", 0, "herdr-replacement-refused"),
        ("shell-exec-replaced", 0, "herdr-replacement-refused"),
        ("predecessor-reused", 0, "herdr-replacement-refused"),
        ("signal-failed", 1, "herdr-signal-failed"),
    ],
)
def test_termination_reverifies_processes_and_surfaces_the_one_signal_failure(
    *, tmp_path: Path, hazard: str, expected_signals: int, condition: str
) -> None:
    world, sup, track = _armed_world(tmp_path=tmp_path)
    observations = [_running_snapshot(), _running_snapshot()]
    if hazard == "foreground-changed":
        observations[1].foreground_group = 300
    elif hazard == "shell-exec-replaced":
        observations[1].shell.executable = "/bin/zsh"
    elif hazard == "predecessor-reused":
        observations[1].processes[-1].starttime = "reused-start"
    snapshot_count = 0
    signal_count = 0

    def snapshot(*, session: str) -> SimpleNamespace:
        nonlocal snapshot_count
        value = observations[min(snapshot_count, 1)]
        snapshot_count += 1
        return value

    def terminate(*, session: str, process_group: int) -> SimpleNamespace:
        nonlocal signal_count
        signal_count += 1
        if hazard == "signal-failed":
            return SimpleNamespace(ok=False, error="SIGTERM refused")
        return SimpleNamespace(ok=True, error="")

    world.fake.herdr_replacement_snapshot = snapshot
    world.fake.herdr_terminate = terminate

    sup.evaluate(track=track, act=True)

    assert signal_count == expected_signals
    assert any(key[-1] == condition for key in sup.alerted)


def _launched_unknown_world(*, tmp_path: Path) -> tuple[_World, registry.Track, dict[str, int]]:
    world, first, track = _armed_world(tmp_path=tmp_path)
    counts = {"signal": 0, "launch": 0}

    def stop(*, session: str, process_group: int) -> SimpleNamespace:
        counts["signal"] += 1
        world.snapshot["value"] = _idle_snapshot()
        return SimpleNamespace(ok=True, error="")

    def launch(**_kwargs: object) -> SimpleNamespace:
        counts["launch"] += 1
        return SimpleNamespace(ok=False, effect_unknown=True, error="lost acknowledgement")

    world.fake.herdr_terminate = stop
    world.fake.herdr_launch = launch
    first.evaluate(track=track, act=True)
    return world, track, counts


def _install_successor(*, world: _World, successor_case: str) -> str:
    shell = _process(pid=100, starttime="shell-start", executable="/bin/bash", pgrp=100)
    launcher = _process(pid=300, starttime="launcher-new", executable="/usr/bin/node", pgrp=300)
    runtime = _process(pid=301, starttime="runtime-new", executable="/usr/bin/node", pgrp=300)
    if successor_case == "old-process":
        launcher = _process(pid=200, starttime="leader-start", executable="/usr/bin/node", pgrp=200)
        runtime = _process(pid=201, starttime="runtime-start", executable="/usr/bin/node", pgrp=200)
    elif successor_case == "reused-predecessor-pid":
        runtime = _process(pid=201, starttime="runtime-new", executable="/usr/bin/node", pgrp=300)
    elif successor_case == "replaced-shell":
        shell.executable = "/bin/zsh"
    foreground_group = 400 if successor_case == "wrong-foreground-group" else launcher.process_group
    world.snapshot["value"] = SimpleNamespace(
        ok=True,
        error="",
        shell=shell,
        foreground_group=foreground_group,
        processes=(shell, launcher, runtime),
    )
    world.fake.cmds[world.target] = "bun" if successor_case == "wrong-runtime" else "node"
    world.fake.panes[world.target] = idle_capture(ctx=100)
    world.fake.calls.clear()
    return f"claude:{runtime.pid}:{runtime.starttime}:{world.topic}"


@pytest.mark.parametrize(
    ("successor_case", "expected_pastes"),
    [
        ("fresh-runtime-child", 1),
        ("old-process", 0),
        ("reused-predecessor-pid", 0),
        ("replaced-shell", 0),
        ("wrong-foreground-group", 0),
        ("wrong-runtime", 0),
    ],
)
def test_recreated_tick_resumes_only_an_exact_fresh_successor(
    *, tmp_path: Path, successor_case: str, expected_pastes: int
) -> None:
    world, track, counts = _launched_unknown_world(tmp_path=tmp_path)
    identity = _install_successor(world=world, successor_case=successor_case)
    recreated = make_supervisor(tmp_path=tmp_path, fake=world.fake, now=lambda: 1003.0)
    recreated.claude_identity_by_session[(world.target, world.topic)] = identity
    recreated.claude_names_by_session[world.target] = {world.topic}
    recreated.refresh_claude_status = lambda: None

    recreated.evaluate(track=track, act=True)

    record = json.loads(
        (world.repo / "tmp" / "overseer" / world.topic / ".herdr-replacement.json").read_text(
            encoding="utf-8"
        )
    )
    pastes = [call for call in world.fake.calls if call[0] == "paste"]
    assert counts == {"signal": 1, "launch": 1}
    assert len(pastes) == expected_pastes
    if expected_pastes:
        assert record["phase"] == "completed"
        assert record["successor"] == {
            "pid": 301,
            "starttime": "runtime-new",
            "executable": "/usr/bin/node",
            "argv": ["/usr/bin/node"],
            "process_group": 300,
            "session_id": 90,
        }
        assert signals.read_state(repo=str(world.repo), topic=world.topic).token == "restarted"
    else:
        assert record["phase"] == "launch-attempted"


def test_recreated_tick_retries_only_enter_for_the_exact_pending_resume(*, tmp_path: Path) -> None:
    world, track, counts = _launched_unknown_world(tmp_path=tmp_path)
    identity = _install_successor(world=world, successor_case="fresh-runtime-child")
    original_send_keys = world.fake.send_keys

    def leave_resume_pending(*, session: str, keys: str) -> bool:
        world.fake.calls.append(("keys", session, keys))
        return True

    world.fake.send_keys = leave_resume_pending
    first = make_supervisor(tmp_path=tmp_path, fake=world.fake, now=lambda: 1003.0)
    first.claude_identity_by_session[(world.target, world.topic)] = identity
    first.claude_names_by_session[world.target] = {world.topic}
    first.evaluate(track=track, act=True)
    record_path = world.repo / "tmp" / "overseer" / world.topic / ".herdr-replacement.json"
    pending = json.loads(record_path.read_text(encoding="utf-8"))
    calls_before_recreation = len(world.fake.calls)
    world.fake.send_keys = original_send_keys
    recreated = make_supervisor(tmp_path=tmp_path, fake=world.fake, now=lambda: 1004.0)
    recreated.claude_identity_by_session[(world.target, world.topic)] = identity
    recreated.claude_names_by_session[world.target] = {world.topic}

    recreated.evaluate(track=track, act=True)

    after = world.fake.calls[calls_before_recreation:]
    final = json.loads(record_path.read_text(encoding="utf-8"))
    assert pending["phase"] == "resume-attempted"
    assert counts == {"signal": 1, "launch": 1}
    assert [call for call in after if call[0] == "paste"] == []
    assert [call for call in after if call[0] == "keys"] == [("keys", world.target, "Enter")]
    assert final["phase"] == "completed"


def test_completed_replacement_fences_failed_cleanup_then_allows_a_fresh_round(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    world, track, counts = _launched_unknown_world(tmp_path=tmp_path)
    identity = _install_successor(world=world, successor_case="fresh-runtime-child")
    recreated = make_supervisor(tmp_path=tmp_path, fake=world.fake, now=lambda: 1004.0)
    recreated.claude_identity_by_session[(world.target, world.topic)] = identity
    recreated.claude_names_by_session[world.target] = {world.topic}
    real_write = _supervisor_state.write_state_diagnostic
    monkeypatch.setattr(_supervisor_state, "write_state_diagnostic", lambda **_kwargs: False)

    recreated.evaluate(track=track, act=True)
    recreated.evaluate(track=track, act=True)

    preserved = registry.read_round_record(
        repo=str(world.repo), topic=world.topic, stamp_path=recreated.stamp_path
    )
    record_path = world.repo / "tmp" / "overseer" / world.topic / ".herdr-replacement.json"
    assert preserved.at == 1000.0
    assert counts == {"signal": 1, "launch": 1}
    assert json.loads(record_path.read_text(encoding="utf-8"))["phase"] == "completed"

    monkeypatch.setattr(_supervisor_state, "write_state_diagnostic", real_write)
    recreated.evaluate(track=track, act=True)
    registry.write_injection_stamp(
        repo=str(world.repo),
        topic=world.topic,
        ts=1005.0,
        session_identity=identity,
        stamp_path=recreated.stamp_path,
    )
    _ = arm_ready_marker(repo=world.repo, topic=world.topic, mtime=1006.0)
    recreated.evaluate(track=track, act=True)

    fresh = json.loads(record_path.read_text(encoding="utf-8"))
    assert counts == {"signal": 2, "launch": 2}
    assert fresh["round"]["ready_mtime"] == 1006.0
    assert fresh["predecessor"]["starttime"] == "runtime-new"


def test_tmux_pre_effect_failure_stays_retryable_and_native_herdr_is_explicit(
    *, tmp_path: Path
) -> None:
    repo, topic = make_plan(tmp_path=tmp_path / "tmux")
    tmux = FakeTmux()
    tmux.serve(session="legacy", repo=repo, capture=idle_capture(ctx=10))
    tmux.respawn_ok = False
    sup = make_supervisor(tmp_path=tmp_path / "tmux", fake=tmux, now=lambda: 1002.0)
    identity = f"claude:123:456:{topic}"
    sup.claude_identity_by_session[("legacy", topic)] = identity
    sup.claude_names_by_session["legacy"] = {topic}
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=identity,
        stamp_path=sup.stamp_path,
    )
    marker = arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    sup.evaluate(track=mapped_track(repo=repo, topic=topic, session="legacy"), act=True)

    assert marker.exists()
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 1000.0
    )
    assert tmux.has(method="respawn")
    assert hasattr(pane_router.MixedPaneDriver, "herdr_replacement_snapshot")
    target = _target(tmp_path=tmp_path)
    process = herdr_calls.ForegroundProcess(
        pane_id="w1:p9",
        shell_pid=100,
        process_group_id=200,
        name="node",
        cmdline="node claude",
        cwd=str(repo),
    )
    observer = SimpleNamespace(
        foreground=lambda *, target: herdr_adapter.ForegroundReading(
            ok=True, process=process, error=""
        )
    )
    launches: list[dict[str, object]] = []
    writer = SimpleNamespace(
        launch=lambda **kwargs: launches.append(kwargs)
        or herdr_write.WriteOutcome(ok=True, error="", effect_unknown=False)
    )
    processes = {
        item.pid: item
        for item in (
            _process(pid=100, starttime="shell-start", executable="/bin/bash", pgrp=100),
            _process(pid=200, starttime="leader-start", executable="/usr/bin/node", pgrp=200),
            _process(pid=201, starttime="runtime-start", executable="/usr/bin/node", pgrp=200),
        )
    }
    signals_sent: list[int] = []
    driver = pane_router.MixedPaneDriver(
        tmux=FakeTmux(),
        herdr=cast(pane_router_reads.HerdrObserver, observer),
        herdr_writer=cast(pane_router_submit_signals.HerdrInput, writer),
        replacement_process_of=lambda *, pid: processes.get(pid),
        replacement_process_ids=lambda: tuple(processes),
        replacement_terminator=lambda *, process_group: signals_sent.append(process_group),
    )

    snapshot = driver.herdr_replacement_snapshot(session=target)
    terminated = driver.herdr_terminate(session=target, process_group=200)
    launched = driver.herdr_launch(
        session=target,
        cwd=str(repo),
        command="claude --model opus",
        env={"ANTHROPIC_MODEL": None},
    )

    assert [item.pid for item in snapshot.processes] == [100, 200, 201]
    assert signals_sent == [200]
    assert terminated.ok and launched.ok
    assert launches == [
        {
            "target": herdr_identity.decode_target(value=target).herdr,
            "cwd": str(repo),
            "command": "claude --model opus",
            "env": {"ANTHROPIC_MODEL": None},
        }
    ]
