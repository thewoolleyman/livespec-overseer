"""Production performers fail closed across launch and stream lifecycle races."""

from __future__ import annotations

import os
import signal
import time
from contextlib import suppress
from pathlib import Path
from types import ModuleType

import pytest

from overseer._lpm_observations import ObservationSanitizer
from overseer._vendor.returns.result import Failure

__all__: list[str] = []


def _write_executable(*, path: Path, body: str) -> None:
    path.write_text(f"#!/usr/bin/env python3\n{body}", encoding="utf-8")
    path.chmod(0o755)


def _close_if_open(*, descriptors: list[int]) -> None:
    for descriptor in descriptors:
        try:
            os.close(descriptor)
        except OSError:
            continue


def _kill_and_reap_if_live(*, pid: int | None) -> None:
    if pid is None:
        return
    with suppress(OSError):
        os.kill(pid, signal.SIGKILL)
    with suppress(OSError):
        os.waitpid(pid, 0)


def _assert_closed(*, descriptors: list[int]) -> None:
    for descriptor in descriptors:
        with pytest.raises(OSError, match="Bad file descriptor"):
            os.fstat(descriptor)


def _command(*, module: ModuleType, path: Path) -> object:
    status = path.stat()
    return module.ExecutionCommand(
        path=str(path.resolve()),
        device=status.st_dev,
        inode=status.st_ino,
        arguments=(),
    )


def _sanitizer() -> ObservationSanitizer:
    def token_handle(*, value: str) -> str:
        assert value == "sk-ant-oat01-partial"
        return "terminal-opaque"

    return ObservationSanitizer(
        token_handles={},
        sensitive_values=frozenset(),
        new_token_handle=token_handle,
    )


def test_browser_resolution_races_return_unavailable(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import overseer._lpm_browser_performer as module

    candidate_dir = tmp_path / "bin"
    candidate_dir.mkdir()
    candidate = candidate_dir / "google-chrome"
    _write_executable(path=candidate, body="raise SystemExit(0)\n")
    real_resolve = Path.resolve

    def fail_candidate_resolve(self: Path, *, strict: bool = False) -> Path:
        if self == candidate:
            raise FileNotFoundError("candidate disappeared during resolution")
        return real_resolve(self, strict=strict)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "resolve", fail_candidate_resolve)
        resolved = module.resolve_installed_google_chrome(
            search_path=(candidate_dir,),
            environ={"PATH": os.environ["PATH"]},
            timeout_seconds=0.1,
        )
    assert isinstance(resolved, Failure)

    real_stat = Path.stat
    candidate_stats = 0

    def fail_post_probe_stat(self: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        nonlocal candidate_stats
        if self == candidate:
            candidate_stats += 1
            if candidate_stats == 2:
                raise FileNotFoundError("candidate disappeared after identity probe")
        return real_stat(self, follow_symlinks=follow_symlinks)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "stat", fail_post_probe_stat)
        patch.setattr(module, "is_google_chrome", lambda **_kwargs: True)
        resolved = module.resolve_installed_google_chrome(
            search_path=(candidate_dir,),
            environ={"PATH": os.environ["PATH"]},
            timeout_seconds=0.1,
        )
    assert isinstance(resolved, Failure)


def test_chrome_identity_probe_closes_setup_failures(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import overseer._lpm_chrome_identity as module

    candidate = tmp_path / "google-chrome"
    _write_executable(path=candidate, body="raise SystemExit(0)\n")
    real_pipe2 = os.pipe2
    descriptors: list[int] = []

    def record_pipe(flags: int) -> tuple[int, int]:
        pair = real_pipe2(flags)
        descriptors.extend(pair)
        return pair

    try:
        with monkeypatch.context() as patch:
            patch.setattr(module.os, "pipe2", record_pipe)
            patch.setattr(
                module.os,
                "open",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("no null fd")),
            )
            assert not module.is_google_chrome(
                executable=candidate,
                environ={"PATH": os.environ["PATH"]},
                timeout_seconds=0.1,
            )
        _assert_closed(descriptors=descriptors)
    finally:
        _close_if_open(descriptors=descriptors)


def test_chrome_identity_probe_reaps_after_post_spawn_io_failure(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import overseer._lpm_chrome_identity as module

    candidate = tmp_path / "google-chrome"
    _write_executable(path=candidate, body="import time\ntime.sleep(60)\n")
    real_spawn = os.posix_spawn
    spawned_pid: int | None = None

    def record_spawn(*args: object, **kwargs: object) -> int:
        nonlocal spawned_pid
        spawned_pid = real_spawn(*args, **kwargs)
        return spawned_pid

    try:
        with monkeypatch.context() as patch:
            patch.setattr(module.os, "posix_spawn", record_spawn)
            patch.setattr(
                module,
                "_drain",
                lambda **_kwargs: (_ for _ in ()).throw(OSError("probe read failed")),
            )
            assert not module.is_google_chrome(
                executable=candidate,
                environ={"PATH": os.environ["PATH"]},
                timeout_seconds=0.1,
            )
        assert spawned_pid is not None
        with pytest.raises(ChildProcessError):
            os.waitpid(spawned_pid, os.WNOHANG)
    finally:
        _kill_and_reap_if_live(pid=spawned_pid)


def test_terminal_spawn_closes_partial_pipe_setup(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import overseer._lpm_terminal_performer as module

    executable = tmp_path / "terminal-command"
    _write_executable(path=executable, body="raise SystemExit(0)\n")
    real_pipe2 = os.pipe2
    descriptors: list[int] = []
    calls = 0

    def fail_second_pipe(flags: int) -> tuple[int, int]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("second pipe unavailable")
        pair = real_pipe2(flags)
        descriptors.extend(pair)
        return pair

    performer = module.TerminalPerformer(
        command=_command(module=module, path=executable),
        sanitizer=_sanitizer(),
        environ={"PATH": os.environ["PATH"]},
        read_timeout_seconds=0.0,
    )
    try:
        with monkeypatch.context() as patch:
            patch.setattr(module.os, "pipe2", fail_second_pipe)
            assert performer.start() == {"version": 1, "status": "unavailable"}
        _assert_closed(descriptors=descriptors)
    finally:
        _close_if_open(descriptors=descriptors)


def test_terminal_spawn_reaps_when_nonblocking_setup_fails(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import overseer._lpm_terminal_performer as module

    executable = tmp_path / "terminal-command"
    _write_executable(path=executable, body="import time\ntime.sleep(60)\n")
    real_pipe2 = os.pipe2
    real_spawn = os.posix_spawn
    descriptors: list[int] = []
    spawned_pid: int | None = None

    def record_pipe(flags: int) -> tuple[int, int]:
        pair = real_pipe2(flags)
        descriptors.extend(pair)
        return pair

    def record_spawn(*args: object, **kwargs: object) -> int:
        nonlocal spawned_pid
        spawned_pid = real_spawn(*args, **kwargs)
        return spawned_pid

    performer = module.TerminalPerformer(
        command=_command(module=module, path=executable),
        sanitizer=_sanitizer(),
        environ={"PATH": os.environ["PATH"]},
        read_timeout_seconds=0.0,
    )
    try:
        with monkeypatch.context() as patch:
            patch.setattr(module.os, "pipe2", record_pipe)
            patch.setattr(module.os, "posix_spawn", record_spawn)
            patch.setattr(
                module.os,
                "set_blocking",
                lambda *_args: (_ for _ in ()).throw(OSError("fcntl failed")),
            )
            assert performer.start() == {"version": 1, "status": "unavailable"}
        _assert_closed(descriptors=descriptors)
        assert spawned_pid is not None
        with pytest.raises(ChildProcessError):
            os.waitpid(spawned_pid, os.WNOHANG)
    finally:
        _close_if_open(descriptors=descriptors)
        _kill_and_reap_if_live(pid=spawned_pid)


def test_terminal_poll_waits_for_child_and_stream_finality(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    import overseer._lpm_terminal_performer as module

    state = module._TerminalState(
        pid=12345,
        stdin_descriptor=-1,
        stdout_descriptor=-1,
        stderr_descriptor=-1,
        stdout_closed=True,
        stderr_closed=True,
    )
    calls: list[tuple[int, int]] = []

    def still_running(pid: int, options: int) -> tuple[int, int]:
        calls.append((pid, options))
        return 0, 0

    monkeypatch.setattr(module.os, "waitpid", still_running)
    assert module._poll(state=state) == (True, None)
    assert calls == [(state.pid, os.WNOHANG)]

    state.reaped = True
    state.exit_status = 0
    state.stdout_closed = False
    assert module._poll(state=state) == (True, 0)


def test_terminal_keeps_descendant_held_streams_incremental(tmp_path: Path) -> None:
    import overseer._lpm_terminal_performer as module

    executable = tmp_path / "terminal-descendant"
    _write_executable(
        path=executable,
        body=(
            "import os\n"
            "import time\n"
            "os.write(1, b'prefix sk-ant-oat01-par')\n"
            "if os.fork() == 0:\n"
            "    time.sleep(0.6)\n"
            "    os.write(1, b'tial\\n')\n"
            "    os._exit(0)\n"
            "os._exit(0)\n"
        ),
    )
    performer = module.TerminalPerformer(
        command=_command(module=module, path=executable),
        sanitizer=_sanitizer(),
        environ={"PATH": os.environ["PATH"]},
        read_timeout_seconds=0.1,
    )
    assert performer.start() == {"version": 1, "status": "ok"}
    time.sleep(0.2)
    first = performer.observe()
    time.sleep(0.5)
    observations = [first]
    for _ in range(5):
        observed = performer.observe()
        observations.append(observed)
        if observed.response.get("running") is False:
            break
    performer.close()

    assert first.response["running"] is True
    assert first.response["stdout"] == "prefix "
    assert observations[-1].response["running"] is False
    assert "".join(str(item.response.get("stdout", "")) for item in observations) == (
        "prefix [[redacted-token:terminal-opaque]]\n"
    )
