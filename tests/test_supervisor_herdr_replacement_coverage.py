"""Coverage-only fail-closed edges for the accepted Herdr successor Red."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import _herdr_replacement_authorization
import _herdr_replacement_process
import _herdr_replacement_store
import _supervisor_herdr_recovery
import _supervisor_herdr_replacement
import _supervisor_herdr_successor
import herdr_adapter
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
from _supervisor_launch_profile import ClaudeLaunchPlan
from test_supervisor_builders import (
    FakeTmux,
    arm_ready_marker,
    busy_capture,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)


def _live_server_supervisor(**kwargs: Any) -> supervisor.Supervisor:
    """A supervisor whose fixture herdr server (pid 700) is a LIVE generation.

    A replacement recorded on a server generation that no longer runs is retired
    (overseer-nztq44), so a fixture that models a live server must say so rather than
    leave the host's real `/proc` to answer for pid 700.
    """
    sup = make_supervisor(**kwargs)
    sup.starttime_of = lambda *, pid: "server-start" if pid == 700 else None
    return sup


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


def _snapshot(*, foreground: int = 300) -> SimpleNamespace:
    shell = _process(pid=100, starttime="shell-start", executable="/bin/bash", pgrp=100)
    leader = _process(pid=300, starttime="leader-new", executable="/usr/bin/node", pgrp=300)
    runtime = _process(pid=301, starttime="runtime-new", executable="/usr/bin/node", pgrp=300)
    return SimpleNamespace(
        shell=shell,
        foreground_group=foreground,
        processes=(shell, leader, runtime),
    )


def _transaction(*, target: str, phase: str) -> dict[str, object]:
    return {
        "version": 1,
        "phase": phase,
        "target": target,
        "server": {
            "socket_path": "/tmp/herdr.sock",
            "pid": 700,
            "starttime": "server-start",
            "pane_id": "w1:p9",
        },
        "runtime": "claude",
        "predecessor": {"pid": 201, "starttime": "runtime-old", "process_group": 200},
        "shell": {
            "pid": 100,
            "starttime": "shell-start",
            "executable": "/bin/bash",
            "argv": ["/bin/bash"],
            "process_group": 100,
            "session_id": 90,
        },
        "round": {
            "ready_mtime": 1001.0,
            "round_at": 1000.0,
            "session_identity": "claude:201:runtime-old:topic",
        },
        "launch": {
            "command": "claude --dangerously-skip-permissions -n topic",
            "cwd": "/repo",
            "env": {"ANTHROPIC_MODEL": None},
        },
    }


def _world(*, tmp_path: Path) -> tuple[supervisor.Supervisor, FakeTmux, registry.Track, str]:
    repo, topic = make_plan(tmp_path=tmp_path)
    target = _target(tmp_path=tmp_path)
    fake = FakeTmux()
    fake.serve(session=target, repo=repo, capture=idle_capture(ctx=100), cmd="node")
    sup = _live_server_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1003.0)
    track = mapped_track(repo=repo, topic=topic, session=target)
    return sup, fake, track, target


def _write(*, track: registry.Track, transaction: dict[str, object]) -> None:
    scratch = _herdr_replacement_store.scratch_path(track=track)
    _herdr_replacement_store.durable_write(
        path=scratch / _herdr_replacement_store.RECORD_NAME,
        value=transaction,
    )


def test_malformed_successor_identity_fails_closed() -> None:
    transaction = _transaction(target="herdr:test", phase="launch-attempted")

    observed = _herdr_replacement_process.proven_successor(
        transaction=transaction,
        snapshot=cast(_herdr_replacement_process.ReplacementSnapshot, _snapshot()),
        identity="not-a-runtime-identity",
    )

    assert observed is None


def test_direct_reentry_refuses_a_predecessor_that_survived_its_signal(*, tmp_path: Path) -> None:
    sup, fake, track, target = _world(tmp_path=tmp_path)
    transaction = _transaction(target=target, phase="signal-attempted")
    _write(track=track, transaction=transaction)
    shell = _process(pid=100, starttime="shell-start", executable="/bin/bash", pgrp=100)
    leader = _process(pid=200, starttime="leader-old", executable="/usr/bin/node", pgrp=200)
    runtime = _process(pid=201, starttime="runtime-old", executable="/usr/bin/node", pgrp=200)
    fake.herdr_replacement_snapshot = lambda *, session: SimpleNamespace(
        shell=shell,
        foreground_group=200,
        processes=(shell, leader, runtime),
    )

    failure = _supervisor_herdr_replacement.begin_herdr_replacement(
        sup=sup,
        track=track,
        target=target,
        launch=ClaudeLaunchPlan(command="claude", env={}),
    )

    assert failure is not None
    assert failure.condition == "herdr-predecessor-survived"


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("record-changed", "replacement-failed"),
        ("shell-not-idle", "replacement-failed"),
        ("launch-observation-error", "replacement-failed"),
        ("resume-error", "replacement-failed"),
        ("completed-old-ready-read-only", "replacement-failed"),
        ("completed-clean", None),
        ("before-stop", "replacement-pending"),
    ],
)
def test_recovery_edges_remain_diagnostic(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str, expected: str | None
) -> None:
    sup, fake, track, target = _world(tmp_path=tmp_path)
    phase = {
        "record-changed": "stopped-awaiting-shell",
        "shell-not-idle": "stopped-awaiting-shell",
        "launch-observation-error": "stopped-awaiting-shell",
        "resume-error": "launch-attempted",
        "completed-old-ready-read-only": "completed",
        "completed-clean": "completed",
    }.get(case, "before-stop")
    transaction = _transaction(target=target, phase=phase)
    _write(track=track, transaction=transaction)
    fake.herdr_replacement_snapshot = lambda *, session: _snapshot(foreground=300)
    fake.herdr_launch = lambda **_kwargs: SimpleNamespace(ok=True, error="")
    if case == "record-changed":
        reads = iter((transaction, None))
        monkeypatch.setattr(
            _herdr_replacement_store,
            "read_transaction",
            lambda *, path: next(reads),
        )
    elif case == "shell-not-idle":
        fake.herdr_replacement_snapshot = lambda *, session: _snapshot(foreground=300)
    elif case == "launch-observation-error":
        fake.herdr_replacement_snapshot = lambda *, session: (_ for _ in ()).throw(
            ValueError("fixture observation failure")
        )
    elif case == "resume-error":
        monkeypatch.setattr(
            _supervisor_herdr_successor,
            "resume_proven_successor",
            lambda **_kwargs: (_ for _ in ()).throw(ValueError("fixture resume failure")),
        )
    elif case == "completed-old-ready-read-only":
        _ = arm_ready_marker(repo=Path(track.repo), topic=track.topic, mtime=1001.0)

    row = _supervisor_herdr_recovery.reconcile_bare_shell(
        sup=sup, track=track, target=target, act=case != "completed-old-ready-read-only"
    )

    assert (None if row is None else row.status) == expected


@pytest.mark.parametrize("unavailable", ["session", "pane"])
def test_public_tick_surfaces_partial_transaction_when_target_is_unavailable(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unavailable: str
) -> None:
    sup, fake, track, target = _world(tmp_path=tmp_path)
    _write(track=track, transaction=_transaction(target=target, phase="stopped-awaiting-shell"))
    if unavailable == "session":
        fake.sessions.remove(target)
    else:
        fake.no_pane_sessions.add(target)
    monkeypatch.setattr(sup, "build_rows", lambda *, act: [track])
    fake.herdr_launch = lambda **_kwargs: pytest.fail("unavailable target must not launch")
    fake.herdr_terminate = lambda **_kwargs: pytest.fail("unavailable target must not signal")

    rows = sup.tick(act=True)

    assert [row.status for row in rows] == ["replacement-pending"]
    assert "stopped-awaiting-shell" in rows[0].note
    assert [call for call in fake.calls if call[0] in {"keys", "paste"}] == []


def test_signal_attempt_recovery_proves_exit_before_launching_once(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sup, fake, track, target = _world(tmp_path=tmp_path)
    _write(track=track, transaction=_transaction(target=target, phase="signal-attempted"))
    fake.cmds[target] = "bash"
    fake.herdr_replacement_snapshot = lambda *, session: _snapshot(foreground=100)
    launches: list[object] = []
    fake.herdr_launch = lambda **kwargs: launches.append(kwargs) or SimpleNamespace(
        ok=False, error="lost acknowledgement", effect_unknown=True
    )
    monkeypatch.setattr(herdr_replacement_process, "proc_starttime", lambda *, pid: None)
    monkeypatch.setattr(sup, "build_rows", lambda *, act: [track])

    rows = sup.tick(act=True)

    record = _herdr_replacement_store.read_transaction(
        path=_herdr_replacement_store.scratch_path(track=track)
        / _herdr_replacement_store.RECORD_NAME
    )
    assert len(launches) == 1
    assert record is not None and record["phase"] == "launch-attempted"
    assert [row.status for row in rows] == ["replacement-pending"]


def test_signal_attempt_recovery_surfaces_a_surviving_predecessor(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sup, fake, track, target = _world(tmp_path=tmp_path)
    _write(track=track, transaction=_transaction(target=target, phase="signal-attempted"))
    shell = _process(pid=100, starttime="shell-start", executable="/bin/bash", pgrp=100)
    leader = _process(pid=200, starttime="leader-old", executable="/usr/bin/node", pgrp=200)
    runtime = _process(pid=201, starttime="runtime-old", executable="/usr/bin/node", pgrp=200)
    fake.herdr_replacement_snapshot = lambda *, session: SimpleNamespace(
        shell=shell,
        foreground_group=200,
        processes=(shell, leader, runtime),
    )
    fake.herdr_launch = lambda **_kwargs: pytest.fail("surviving predecessor must not launch")
    monkeypatch.setattr(
        herdr_replacement_process,
        "proc_starttime",
        lambda *, pid: "runtime-old",
    )
    monkeypatch.setattr(sup, "build_rows", lambda *, act: [track])

    rows = sup.tick(act=True)

    assert [row.status for row in rows] == ["replacement-failed"]
    assert "survived" in rows[0].note


def test_recreated_codex_rename_attempt_routes_to_guarded_continuation(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sup, _fake, track, target = _world(tmp_path=tmp_path)
    transaction = _transaction(target=target, phase="rename-attempted")
    transaction.update(
        {
            "runtime": "codex",
            "predecessor_rollout": "019f548d-0000-7000-8000-000000000001",
            "successor": _herdr_replacement_process.process_record(
                process=_process(
                    pid=301,
                    starttime="runtime-new",
                    executable="/usr/bin/node",
                    pgrp=300,
                )
            ),
            "successor_rollout": "019f548d-0000-7000-8000-000000000002",
            "rename": f"/rename {track.topic}",
            "resume": "read the durable handoff",
        }
    )
    _write(track=track, transaction=transaction)
    calls: list[str] = []
    monkeypatch.setattr(
        _supervisor_herdr_successor,
        "resume_proven_successor",
        lambda **_kwargs: calls.append("resume") or "rename remains pending",
    )

    row = _supervisor_herdr_recovery.reconcile_bare_shell(
        sup=sup,
        track=track,
        target=target,
        act=True,
    )

    assert calls == ["resume"]
    assert row is not None and row.status == "replacement-failed"


def test_scalar_transaction_is_reported_as_malformed_instead_of_crashing(*, tmp_path: Path) -> None:
    sup, _fake, track, target = _world(tmp_path=tmp_path)
    record_path = (
        _herdr_replacement_store.scratch_path(track=track) / _herdr_replacement_store.RECORD_NAME
    )
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text("[]", encoding="utf-8")
    try:
        row = _supervisor_herdr_recovery.reconcile_bare_shell(
            sup=sup,
            track=track,
            target=target,
            act=True,
        )
        status = None if row is None else row.status
    except (AttributeError, TypeError, ValueError):
        status = "uncaught-transaction-error"

    assert status == "replacement-failed"


def test_partial_transaction_cannot_authorize_a_bare_shell_launch(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sup, fake, track, target = _world(tmp_path=tmp_path)
    complete = _transaction(target=target, phase="stopped-awaiting-shell")
    partial = {key: complete[key] for key in ("phase", "target", "predecessor", "shell", "launch")}
    _herdr_replacement_store.durable_write(
        path=_herdr_replacement_store.scratch_path(track=track)
        / _herdr_replacement_store.RECORD_NAME,
        value=partial,
    )
    fake.herdr_replacement_snapshot = lambda *, session: _snapshot(foreground=100)
    launches: list[object] = []
    fake.herdr_launch = lambda **kwargs: launches.append(kwargs) or SimpleNamespace(
        ok=True, error="", effect_unknown=False
    )
    monkeypatch.setattr(herdr_replacement_process, "proc_starttime", lambda *, pid: None)

    row = _supervisor_herdr_recovery.reconcile_bare_shell(
        sup=sup,
        track=track,
        target=target,
        act=True,
    )

    assert launches == []
    assert row is not None and row.status == "replacement-failed"


def test_final_authorization_requires_the_recorded_live_ready_token(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sup, _fake, track, target = _world(tmp_path=tmp_path)
    transaction = _transaction(target=target, phase="before-stop")
    identity = f"claude:201:runtime-old:{track.topic}"
    transaction["round"] = {
        "ready_mtime": 1001.0,
        "round_at": 1000.0,
        "session_identity": identity,
    }
    registry.write_injection_stamp(
        repo=track.repo,
        topic=track.topic,
        ts=1000.0,
        session_identity=identity,
        stamp_path=sup.stamp_path,
    )
    monkeypatch.setattr(
        signals,
        "read_state",
        lambda **_kwargs: SimpleNamespace(token=signals.STATE_BLOCKED, mtime=1001.0),
    )

    assert (
        _herdr_replacement_authorization.round_still_authorizes(
            sup=sup,
            track=track,
            transaction=transaction,
        )
        is False
    )


@pytest.mark.parametrize("changed_field", ["argv", "session_id"])
def test_idle_shell_requires_the_exact_recorded_process_image(*, changed_field: str) -> None:
    transaction = _transaction(target="herdr:test", phase="stopped-awaiting-shell")
    snapshot = _snapshot(foreground=100)
    if changed_field == "argv":
        snapshot.shell.argv = ("/bin/bash", "--noprofile")
    else:
        snapshot.shell.session_id = 91

    assert (
        _herdr_replacement_process.retained_shell_is_idle(
            transaction=transaction,
            snapshot=cast(_herdr_replacement_process.ReplacementSnapshot, snapshot),
        )
        is False
    )


def test_empty_composer_is_not_submission_provenance() -> None:
    assert pane_router_submit_signals.submitted(capture=idle_capture(ctx=100)) is False
    assert pane_router_submit_signals.submitted(capture=busy_capture(ctx=100)) is True


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("identity-missing", "identity is not yet observable"),
        ("record-changed", "replacement changed"),
        ("gate", "structured gate"),
        ("input-not-ready", "input is not ready"),
        ("resume-missing", "no certifiable resume"),
        ("submit-failed", "submission was not confirmed"),
    ],
)
def test_successor_continuation_edges_fail_closed(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str, message: str
) -> None:
    sup, fake, track, target = _world(tmp_path=tmp_path)
    transaction = _transaction(target=target, phase="launch-attempted")
    _write(track=track, transaction=transaction)
    fake.herdr_replacement_snapshot = lambda *, session: _snapshot()
    if case != "identity-missing":
        sup.claude_identity_by_session[(target, track.topic)] = (
            f"claude:301:runtime-new:{track.topic}"
        )
    if case == "record-changed":
        changed = dict(transaction)
        changed["phase"] = "successor-observed"
        _write(track=track, transaction=changed)
    elif case == "gate":
        fake.panes[target] = "Continue?\n❯ 1. Yes\n  2. No\n"
    elif case == "input-not-ready":
        fake.panes[target] = "starting"
    elif case == "resume-missing":
        monkeypatch.setattr(_supervisor_herdr_successor, "resume_for_track", lambda *, track: None)
    elif case == "submit-failed":
        fake.paste_ok = False

    reason = _supervisor_herdr_successor.resume_proven_successor(
        sup=sup,
        track=track,
        target=target,
        transaction=transaction,
    )

    assert reason is not None
    assert message in reason


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("submitted", (True, False)),
        ("empty-composer", (False, True)),
        ("wrong-text", (False, False)),
        ("known-enter-failure", (False, False)),
        ("unknown-enter", (False, True)),
        ("unrecognized-after-enter", (False, True)),
    ],
)
def test_native_enter_retry_is_stateless_and_exact(
    *, tmp_path: Path, case: str, expected: tuple[bool, bool]
) -> None:
    target = _target(tmp_path=tmp_path)
    resume = "read the durable handoff"
    pending = idle_capture(ctx=100).replace("\n❯ \n", f"\n❯ {resume}\n")
    captures = [pending, busy_capture(ctx=100)]
    if case == "empty-composer":
        captures = [pending, idle_capture(ctx=100)]
    if case == "wrong-text":
        captures = [pending.replace(resume, "unrelated text")]
    elif case == "unknown-enter":
        captures = [pending, pending]
    elif case == "unrecognized-after-enter":
        captures = [pending, "redrawn without recognizable input"]
    outcome = herdr_write.WriteOutcome(
        ok=case not in {"known-enter-failure", "unknown-enter"},
        error="fixture Enter outcome",
        effect_unknown=case == "unknown-enter",
    )
    observer = SimpleNamespace(
        capture_pane=lambda *, target, retain_ansi: herdr_adapter.PaneCapture(
            ok=True,
            text=captures.pop(0) if len(captures) > 1 else captures[0],
            error="",
        )
    )
    writer = SimpleNamespace(send_enter=lambda *, target: outcome)
    driver = pane_router.MixedPaneDriver(
        tmux=FakeTmux(),
        herdr=cast(pane_router_reads.HerdrObserver, observer),
        herdr_writer=cast(pane_router_submit_signals.HerdrInput, writer),
    )

    result = driver.retry_prompt_enter_once(
        session=target,
        text=resume,
        sleep=lambda _seconds: None,
    )

    assert result == expected


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("successor-changed", "successor no longer matches"),
        ("text-changed", "text is absent"),
        ("budget-exhausted", "budget is exhausted"),
        ("native-unknown", "outcome is unknown"),
        ("native-failed", "was not confirmed"),
    ],
)
def test_durable_resume_retry_refuses_every_unproven_edge(
    *, tmp_path: Path, case: str, message: str
) -> None:
    sup, fake, track, target = _world(tmp_path=tmp_path)
    runtime = _process(pid=301, starttime="runtime-new", executable="/usr/bin/node", pgrp=300)
    resume = "read the durable handoff"
    transaction = _transaction(target=target, phase="resume-attempted")
    transaction["successor"] = _herdr_replacement_process.process_record(process=runtime)
    transaction["resume"] = resume
    if case == "successor-changed":
        transaction["successor"] = {"pid": 999}
    elif case == "budget-exhausted":
        transaction["resume_retry_attempts"] = 8
    _write(track=track, transaction=transaction)
    fake.herdr_replacement_snapshot = lambda *, session: _snapshot()
    fake.panes[target] = idle_capture(ctx=100).replace("\n❯ \n", f"\n❯ {resume}\n")
    if case == "text-changed":
        fake.panes[target] = fake.panes[target].replace(resume, "unrelated text")
    if case in {"native-unknown", "native-failed"}:
        fake.retry_prompt_enter_once = lambda **_kwargs: (
            False,
            case == "native-unknown",
        )
    sup.claude_identity_by_session[(target, track.topic)] = (
        f"claude:{runtime.pid}:{runtime.starttime}:{track.topic}"
    )

    reason = _supervisor_herdr_successor.resume_proven_successor(
        sup=sup,
        track=track,
        target=target,
        transaction=transaction,
    )

    assert reason is not None
    assert message in reason


def test_out_of_band_runtime_retires_a_stalled_resume_transaction_and_its_round(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sup, fake, track, target = _world(tmp_path=tmp_path)
    transaction = _transaction(target=target, phase="resume-attempted")
    transaction["successor"] = _herdr_replacement_process.process_record(
        process=_process(pid=301, starttime="runtime-new", executable="/usr/bin/node", pgrp=300)
    )
    transaction["resume"] = "read the durable handoff"
    _write(track=track, transaction=transaction)
    registry.write_injection_stamp(
        repo=track.repo,
        topic=track.topic,
        ts=1000.0,
        session_identity="claude:201:runtime-old:topic",
        stamp_path=sup.stamp_path,
    )
    _ = arm_ready_marker(repo=Path(track.repo), topic=track.topic, mtime=1001.0)
    sup.claude_identity_by_session[(target, track.topic)] = "claude:401:runtime-oob:topic"
    monkeypatch.setattr(sup, "build_rows", lambda *, act: [track])
    fake.herdr_terminate = lambda **_kwargs: pytest.fail("retirement must not signal")
    fake.herdr_launch = lambda **_kwargs: pytest.fail("retirement must not launch")

    rows = sup.tick(act=True)

    record = (
        _herdr_replacement_store.scratch_path(track=track) / _herdr_replacement_store.RECORD_NAME
    )
    assert not record.exists()
    assert (
        registry.read_injection_stamp(repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path)
        is None
    )
    assert signals.read_state(repo=track.repo, topic=track.topic) is None
    assert [row.status for row in rows] != ["replacement-failed"]


@pytest.mark.parametrize(
    ("own_ready_mtime", "own_stamp"),
    [
        pytest.param(2000.0, None, id="own-ready-only"),
        pytest.param(None, (1900.0, "claude:401:runtime-oob:topic"), id="own-newer-round-only"),
        pytest.param(2000.0, (1900.0, "claude:401:runtime-oob:topic"), id="own-ready-and-round"),
    ],
)
def test_out_of_band_retirement_leaves_the_live_sessions_own_declaration_and_round(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    own_ready_mtime: float | None,
    own_stamp: tuple[float, str] | None,
) -> None:
    sup, fake, track, target = _world(tmp_path=tmp_path)
    transaction = _transaction(target=target, phase="resume-attempted")
    transaction["successor"] = _herdr_replacement_process.process_record(
        process=_process(pid=301, starttime="runtime-new", executable="/usr/bin/node", pgrp=300)
    )
    transaction["resume"] = "read the durable handoff"
    _write(track=track, transaction=transaction)
    stamp_at, stamp_identity = own_stamp or (1000.0, "claude:201:runtime-old:topic")
    registry.write_injection_stamp(
        repo=track.repo,
        topic=track.topic,
        ts=stamp_at,
        session_identity=stamp_identity,
        stamp_path=sup.stamp_path,
    )
    _ = arm_ready_marker(
        repo=Path(track.repo),
        topic=track.topic,
        mtime=1001.0 if own_ready_mtime is None else own_ready_mtime,
    )
    sup.claude_identity_by_session[(target, track.topic)] = "claude:401:runtime-oob:topic"
    monkeypatch.setattr(sup, "build_rows", lambda *, act: [track])
    fake.herdr_terminate = lambda **_kwargs: pytest.fail("retirement must not signal")
    fake.herdr_launch = lambda **_kwargs: pytest.fail("retirement must not launch")

    _ = sup.tick(act=True)

    record = (
        _herdr_replacement_store.scratch_path(track=track) / _herdr_replacement_store.RECORD_NAME
    )
    assert not record.exists()
    state = signals.read_state(repo=track.repo, topic=track.topic)
    assert state is not None
    assert state.mtime == (1001.0 if own_ready_mtime is None else own_ready_mtime)
    round_record = registry.read_round_record(
        repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path
    )
    assert round_record.at == stamp_at
    assert round_record.session_identity == stamp_identity
