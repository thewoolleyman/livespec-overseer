"""Native process, launch-rendering, and adapter edges for guarded Herdr replacement."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import herdr_adapter
import herdr_calls
import herdr_identity
import herdr_launch
import herdr_replacement
import herdr_replacement_process
import herdr_transport
import herdr_write
import pane_router
import pane_router_reads
import pane_router_submit_signals
import pytest
from test_supervisor_builders import FakeTmux


def _target(*, tmp_path: Path) -> herdr_identity.HerdrPaneTarget:
    return herdr_identity.HerdrPaneTarget(
        socket_path=str(tmp_path / "herdr.sock"),
        server_pid=700,
        server_starttime="server-start",
        pane_id="w1:p9",
    )


def _process(
    *,
    pid: int,
    starttime: str,
    executable: str,
    process_group: int,
    session_id: int = 90,
) -> herdr_replacement.ObservedProcess:
    return herdr_replacement.ObservedProcess(
        pid=pid,
        starttime=starttime,
        executable=executable,
        argv=(executable,),
        process_group=process_group,
        session_id=session_id,
    )


def _foreground(*, group: int = 200) -> herdr_calls.ForegroundProcess:
    return herdr_calls.ForegroundProcess(
        pane_id="w1:p9",
        shell_pid=100,
        process_group_id=group,
        name="node",
        cmdline="node claude",
        cwd="/repo",
    )


def _controller_world(
    *, tmp_path: Path
) -> tuple[
    herdr_replacement.ReplacementController,
    dict[int, herdr_replacement.ObservedProcess],
    dict[str, herdr_calls.ForegroundProcess],
    list[int],
]:
    shell = _process(
        pid=100,
        starttime="shell-start",
        executable=str(Path("/bin/sh").resolve()),
        process_group=100,
    )
    leader = _process(
        pid=200,
        starttime="leader-start",
        executable="/usr/bin/node",
        process_group=200,
    )
    runtime = _process(
        pid=201,
        starttime="runtime-start",
        executable="/usr/bin/node",
        process_group=200,
    )
    processes = {item.pid: item for item in (shell, leader, runtime)}
    foreground = {"value": _foreground()}
    signals: list[int] = []
    observer = SimpleNamespace(
        foreground=lambda *, target: herdr_adapter.ForegroundReading(
            ok=True,
            process=foreground["value"],
            error="",
        )
    )
    writer = SimpleNamespace(
        launch=lambda **_kwargs: herdr_write.WriteOutcome(
            ok=False,
            error="lost acknowledgement",
            effect_unknown=True,
        )
    )
    controller = herdr_replacement.ReplacementController(
        observer=cast(herdr_adapter.ForegroundObserver, observer),
        writer=cast(herdr_replacement.ReplacementWriter, writer),
        process_of=lambda *, pid: processes.get(pid),
        process_ids=lambda: tuple(processes),
        terminate_group=lambda *, process_group: signals.append(process_group),
        login_shells=frozenset({shell.executable}),
    )
    return controller, processes, foreground, signals


def test_launch_renderer_preserves_removals_assignments_and_shell_quoting() -> None:
    rendered = herdr_launch.render_launch(
        cwd="/repo with space",
        command="codex --model 'gpt 5'",
        env={"REMOVE_ME": None, "SET_ME": "two words"},
    )

    assert rendered == (
        "cd -- '/repo with space' && "
        "env -u REMOVE_ME 'SET_ME=two words' sh -c 'exec codex --model '\"'\"'gpt 5'\"'\"''"
    )
    with pytest.raises(ValueError, match="invalid variable name"):
        herdr_launch.render_launch(cwd="/repo", command="codex", env={"NOT-AN-ENV": "x"})


def test_writer_launch_uses_one_atomic_run_request(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []

    def request(_self: object, **kwargs: object) -> herdr_transport.RpcOutcome:
        calls.append(kwargs)
        return herdr_transport.RpcOutcome(
            ok=True,
            result={},
            error="",
            peer=None,
            timed_out=False,
            request_sent=True,
        )

    monkeypatch.setattr(herdr_write.HerdrWriter, "request", request)
    writer = herdr_write.HerdrWriter()

    outcome = writer.launch(
        target=_target(tmp_path=tmp_path),
        cwd="/repo",
        command="claude --model opus",
        env={"ANTHROPIC_MODEL": None},
    )

    assert outcome.ok
    assert calls[0]["params"] == {
        "pane_id": "w1:p9",
        "text": "cd -- /repo && env -u ANTHROPIC_MODEL sh -c 'exec claude --model opus'",
        "keys": ["Enter"],
    }


@pytest.mark.parametrize(
    "hazard",
    [
        "unreadable-foreground",
        "missing-shell",
        "missing-leader",
        "unsupported-shell",
        "shell-not-own-group",
        "foreign-session",
    ],
)
def test_snapshot_requires_a_registered_retained_shell_and_owned_group(
    *, tmp_path: Path, hazard: str
) -> None:
    controller, processes, _foreground_state, _signals = _controller_world(tmp_path=tmp_path)
    if hazard == "unreadable-foreground":
        controller = herdr_replacement.ReplacementController(
            observer=cast(
                herdr_adapter.ForegroundObserver,
                SimpleNamespace(
                    foreground=lambda *, target: herdr_adapter.ForegroundReading(
                        ok=False, process=None, error="socket generation changed"
                    )
                ),
            ),
            writer=controller.writer,
            process_of=controller.process_of,
            process_ids=controller.process_ids,
            terminate_group=controller.terminate_group,
            login_shells=controller.login_shells,
        )
    elif hazard == "missing-shell":
        del processes[100]
    elif hazard == "missing-leader":
        del processes[200]
    elif hazard == "unsupported-shell":
        controller = herdr_replacement.ReplacementController(
            observer=controller.observer,
            writer=controller.writer,
            process_of=controller.process_of,
            process_ids=controller.process_ids,
            terminate_group=controller.terminate_group,
            login_shells=frozenset(),
        )
    elif hazard == "shell-not-own-group":
        processes[100] = _process(
            pid=100,
            starttime="shell-start",
            executable=str(Path("/bin/sh").resolve()),
            process_group=200,
        )
    else:
        processes[200] = _process(
            pid=200,
            starttime="leader-start",
            executable="/usr/bin/node",
            process_group=200,
            session_id=91,
        )

    with pytest.raises(OSError, match="generation|retained|foreground"):
        controller.snapshot(target=_target(tmp_path=tmp_path))


@pytest.mark.parametrize(
    "hazard",
    [
        "missing-authorization-snapshot",
        "foreground-changed",
        "shell-exec-replaced",
        "leader-disappeared",
        "runtime-reused",
        "signal-error",
    ],
)
def test_termination_rechecks_every_recorded_group_generation(
    *, tmp_path: Path, hazard: str
) -> None:
    controller, processes, foreground, signals = _controller_world(tmp_path=tmp_path)
    expected = controller.snapshot(target=_target(tmp_path=tmp_path))
    if hazard == "missing-authorization-snapshot":
        expected = None
    elif hazard == "foreground-changed":
        foreground["value"] = _foreground(group=300)
    elif hazard == "shell-exec-replaced":
        processes[100] = _process(
            pid=100,
            starttime="shell-start",
            executable="/usr/bin/sleep",
            process_group=100,
        )
    elif hazard == "leader-disappeared":
        del processes[200]
    elif hazard == "runtime-reused":
        processes[201] = _process(
            pid=201,
            starttime="reused",
            executable="/usr/bin/node",
            process_group=200,
        )
    else:

        def fail_signal(*, process_group: int) -> None:
            raise OSError(f"cannot signal {process_group}")

        controller = herdr_replacement.ReplacementController(
            observer=controller.observer,
            writer=controller.writer,
            process_of=controller.process_of,
            process_ids=controller.process_ids,
            terminate_group=fail_signal,
            login_shells=controller.login_shells,
        )

    outcome = controller.terminate(
        target=_target(tmp_path=tmp_path),
        process_group=200,
        expected=expected,
    )

    assert not outcome.ok
    assert signals == []


def test_native_controller_reports_success_and_ambiguous_launch(*, tmp_path: Path) -> None:
    controller, _processes, _foreground_state, signals = _controller_world(tmp_path=tmp_path)
    expected = controller.snapshot(target=_target(tmp_path=tmp_path))

    terminated = controller.terminate(
        target=_target(tmp_path=tmp_path), process_group=200, expected=expected
    )
    launched = controller.launch(
        target=_target(tmp_path=tmp_path),
        cwd="/repo",
        command="claude",
        env={},
    )

    assert terminated.ok
    assert signals == [200]
    assert not launched.ok and launched.effect_unknown


def test_process_signal_adapter_calls_killpg(*, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, object]] = []
    monkeypatch.setattr(
        herdr_replacement.os,
        "killpg",
        lambda group, sent_signal: calls.append((group, sent_signal)),
    )

    herdr_replacement.terminate_process_group(process_group=321)

    assert calls and calls[0][0] == 321


def test_proc_reader_accepts_a_stable_live_generation_and_enumerates_pids() -> None:
    observed = herdr_replacement_process.proc_process(pid=os.getpid())

    assert observed is not None
    assert observed.pid == os.getpid()
    assert os.getpid() in herdr_replacement_process.proc_process_ids()


@pytest.mark.parametrize(
    ("stat", "link", "argv"),
    [
        (None, "/bin/sh", ("sh",)),
        ((100, 90, "one"), None, ("sh",)),
        ((100, 90, "one"), "/bin/sh", None),
        (((100, 90, "one"), (100, 90, "two")), "/bin/sh", ("sh",)),
        ((100, 90, "one"), ("/bin/sh", "/usr/bin/sleep"), ("sh",)),
    ],
)
def test_proc_reader_rejects_missing_or_changing_evidence(
    *,
    monkeypatch: pytest.MonkeyPatch,
    stat: object,
    link: object,
    argv: object,
) -> None:
    def sequence(value: object):
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], tuple):
            values = iter(value)
            return lambda **_kwargs: next(values)
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
            values = iter(value)
            return lambda **_kwargs: next(values)
        return lambda **_kwargs: value

    monkeypatch.setattr(herdr_replacement_process, "_stat_fields", sequence(stat))
    monkeypatch.setattr(herdr_replacement_process, "_executable", sequence(link))
    monkeypatch.setattr(herdr_replacement_process, "_argv", sequence(argv))

    assert herdr_replacement_process.proc_process(pid=123) is None


class FakeProcPath:
    mode = "valid"

    def __init__(self, value: str) -> None:
        self.value = value

    def read_text(self, *, encoding: str) -> str:
        if self.mode == "error":
            raise OSError("gone")
        if self.mode == "malformed":
            return "not a stat record"
        if self.mode == "short":
            return "1 (x) S"
        if self.mode == "bad-int":
            return "1 (x) S 1 nope 90 " + " ".join(["0"] * 16)
        if self.mode == "nonpositive":
            return "1 (x) S 1 0 90 " + " ".join(["0"] * 15 + ["start"])
        return "1 (x) S 1 200 90 " + " ".join(["0"] * 15 + ["start"])

    def readlink(self) -> FakeProcPath:
        if self.mode == "error":
            raise OSError("gone")
        return FakeProcPath("/bin/sh")

    def resolve(self) -> FakeProcPath:
        return self

    def read_bytes(self) -> bytes:
        if self.mode == "error":
            raise OSError("gone")
        return b"" if self.mode == "empty" else b"sh\0-i\0"

    def iterdir(self) -> tuple[SimpleNamespace, ...]:
        if self.mode == "error":
            raise OSError("gone")
        return (
            SimpleNamespace(name="7"),
            SimpleNamespace(name="not-a-pid"),
            SimpleNamespace(name="3"),
        )

    def __str__(self) -> str:
        return self.value


@pytest.mark.parametrize("mode", ["error", "malformed", "short", "bad-int", "nonpositive"])
def test_stat_path_reader_rejects_malformed_proc(
    *, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setattr(herdr_replacement_process, "Path", FakeProcPath)
    FakeProcPath.mode = mode

    assert herdr_replacement_process._stat_fields(pid=1) is None


def test_process_path_readers_accept_stable_proc(*, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(herdr_replacement_process, "Path", FakeProcPath)
    FakeProcPath.mode = "valid"
    assert herdr_replacement_process._stat_fields(pid=1) == (200, 90, "start")
    assert herdr_replacement_process._executable(pid=1) == "/bin/sh"
    assert herdr_replacement_process._argv(pid=1) == ("sh", "-i")
    assert herdr_replacement_process.proc_process_ids() == (3, 7)


@pytest.mark.parametrize("mode", ["error", "empty"])
def test_process_path_readers_reject_unreadable_proc(
    *, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setattr(herdr_replacement_process, "Path", FakeProcPath)
    FakeProcPath.mode = mode

    if mode == "error":
        assert herdr_replacement_process._executable(pid=1) is None
        assert herdr_replacement_process.proc_process_ids() == ()
    assert herdr_replacement_process._argv(pid=1) is None


def test_mixed_driver_refuses_a_non_herdr_replacement_target(*, tmp_path: Path) -> None:
    driver = pane_router.MixedPaneDriver(
        tmux=FakeTmux(),
        herdr=cast(pane_router_reads.HerdrObserver, SimpleNamespace()),
        herdr_writer=cast(pane_router_submit_signals.HerdrInput, SimpleNamespace()),
    )

    with pytest.raises(ValueError, match="qualified tmux target"):
        driver.herdr_replacement_snapshot(session="tmux:legacy")
