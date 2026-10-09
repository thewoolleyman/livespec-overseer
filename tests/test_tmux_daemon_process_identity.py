"""Deterministic edge coverage for exact tmux foreground daemon identity.

The native regression in ``test_tmux_daemon_liveness`` is the behavioral Red.
These postimplementation companions make every fail-closed process-evidence edge
gradeable on hosts where the relevant ``/proc`` races cannot be staged reliably.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from overseer import tmux_daemon_liveness

__all__: list[str] = []

ROOT = 10
CHILD = 20
FOREGROUND_GROUP = 30


def _stat(*, process_group: object, foreground_group: object, starttime: object) -> str:
    fields = [
        "S",
        "1",
        str(process_group),
        "1",
        "0",
        str(foreground_group),
        *("0" for _ in range(13)),
        str(starttime),
    ]
    return f"10 (process name) {' '.join(fields)}"


def _find(
    *,
    command: bytes | None,
    child_stat: str | None,
    daemon_executable: Path,
    executable: str | None,
    root_stat: str | None = None,
    stat_of: Callable[..., str | None] | None = None,
) -> tmux_daemon_liveness.DaemonProcessIdentity | None:
    selected_root = root_stat or _stat(
        process_group=ROOT,
        foreground_group=FOREGROUND_GROUP,
        starttime="root-start",
    )

    def read_children(*, pid: int) -> list[int]:
        return [CHILD] if pid == ROOT else []

    def read_command(*, pid: int) -> bytes | None:
        return command if pid == CHILD else None

    def read_stat(*, pid: int) -> str | None:
        return selected_root if pid == ROOT else child_stat

    def read_executable(*, pid: int) -> str | None:
        return executable if pid == CHILD else None

    return tmux_daemon_liveness.foreground_daemon_process(
        root_pid=ROOT,
        daemon_executable=daemon_executable,
        children_of=read_children,
        cmdline_of=read_command,
        stat_of=stat_of or read_stat,
        executable_of=read_executable,
    )


def _prepared_daemon(*, root: Path, runtime: Path | None = None) -> tuple[Path, str]:
    selected_runtime = Path(sys.executable).resolve() if runtime is None else runtime.resolve()
    bin_dir = root / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").symlink_to(selected_runtime)
    daemon_executable = bin_dir / "overseerd"
    daemon_executable.write_text("candidate console script", encoding="utf-8")
    return daemon_executable, str(selected_runtime)


def test_exact_foreground_identity_accepts_both_shipped_daemon_argument_roles(
    *, tmp_path: Path
) -> None:
    daemon_executable, runtime = _prepared_daemon(root=tmp_path / "candidate")
    foreground = _stat(
        process_group=FOREGROUND_GROUP,
        foreground_group=FOREGROUND_GROUP,
        starttime="child-start",
    )
    commands = (
        f"{runtime}\0-m\0overseer.daemon\0".encode(),
        f"{runtime}\0{daemon_executable}\0".encode(),
    )

    identities = [
        _find(
            command=command,
            child_stat=foreground,
            daemon_executable=daemon_executable,
            executable=runtime,
        )
        for command in commands
    ]

    assert all(identity is not None for identity in identities)
    assert identities[0] == tmux_daemon_liveness.DaemonProcessIdentity(
        pid=CHILD,
        starttime="child-start",
        executable=runtime,
        argv=(runtime, "-m", "overseer.daemon"),
        process_group=FOREGROUND_GROUP,
    )


def test_foreground_identity_skips_cycles_and_background_daemons(*, tmp_path: Path) -> None:
    daemon_executable, runtime = _prepared_daemon(root=tmp_path / "candidate")
    stats = {
        ROOT: _stat(
            process_group=ROOT,
            foreground_group=FOREGROUND_GROUP,
            starttime="root-start",
        ),
        20: _stat(process_group=20, foreground_group=20, starttime="background"),
        30: _stat(
            process_group=FOREGROUND_GROUP,
            foreground_group=FOREGROUND_GROUP,
            starttime="foreground",
        ),
    }
    children = {ROOT: [30, 20, ROOT], 20: [30], 30: [20]}

    identity = tmux_daemon_liveness.foreground_daemon_process(
        root_pid=ROOT,
        daemon_executable=daemon_executable,
        children_of=lambda *, pid: list(children.get(pid, [])),
        cmdline_of=lambda *, pid: f"{runtime}\0{daemon_executable}\0".encode(),
        stat_of=lambda *, pid: stats.get(pid),
        executable_of=lambda *, pid: runtime if pid in stats else None,
    )

    assert identity is not None
    assert (identity.pid, identity.starttime) == (30, "foreground")


def test_incomplete_or_contradictory_process_evidence_fails_closed(*, tmp_path: Path) -> None:
    daemon_executable, runtime = _prepared_daemon(root=tmp_path / "candidate")
    cat_command = shutil.which("cat")
    assert cat_command is not None
    cat_runtime = str(Path(cat_command).resolve())
    foreground = _stat(
        process_group=FOREGROUND_GROUP,
        foreground_group=FOREGROUND_GROUP,
        starttime="child-start",
    )
    exact = f"{runtime}\0{daemon_executable}\0".encode()
    lookalike = tmp_path / "lookalike" / "overseerd"
    lookalike.parent.mkdir()
    lookalike.write_text("unrelated console script", encoding="utf-8")
    missing_runtime_daemon = tmp_path / "missing-runtime" / "bin" / "overseerd"
    missing_runtime_daemon.parent.mkdir(parents=True)
    missing_runtime_daemon.write_text("no sibling interpreter", encoding="utf-8")
    malformed_number = _stat(
        process_group="not-an-int",
        foreground_group=FOREGROUND_GROUP,
        starttime="child-start",
    )
    cases = (
        _find(
            command=exact,
            child_stat=foreground,
            daemon_executable=daemon_executable,
            executable=runtime,
            root_stat="malformed",
        ),
        _find(
            command=exact,
            child_stat=foreground,
            daemon_executable=daemon_executable,
            executable=runtime,
            root_stat=_stat(process_group=ROOT, foreground_group=0, starttime="root"),
        ),
        _find(
            command=None,
            child_stat=foreground,
            daemon_executable=daemon_executable,
            executable=runtime,
        ),
        _find(
            command=exact,
            child_stat="malformed",
            daemon_executable=daemon_executable,
            executable=runtime,
        ),
        _find(
            command=exact,
            child_stat=malformed_number,
            daemon_executable=daemon_executable,
            executable=runtime,
        ),
        _find(
            command=exact,
            child_stat=foreground,
            daemon_executable=daemon_executable,
            executable=None,
        ),
        _find(
            command=b"sh\0-c\0echo overseerd\0",
            child_stat=foreground,
            daemon_executable=daemon_executable,
            executable=runtime,
        ),
        _find(
            command=b"/missing/runtime\0overseerd\0",
            child_stat=foreground,
            daemon_executable=daemon_executable,
            executable=runtime,
        ),
        _find(
            command=f"{runtime}\0{tmp_path / 'missing-console'}\0".encode(),
            child_stat=foreground,
            daemon_executable=daemon_executable,
            executable=runtime,
        ),
        _find(
            command=f"{cat_runtime}\0{daemon_executable}\0".encode(),
            child_stat=foreground,
            daemon_executable=daemon_executable,
            executable=cat_runtime,
        ),
        _find(
            command=f"{cat_runtime}\0-m\0overseer.daemon\0".encode(),
            child_stat=foreground,
            daemon_executable=daemon_executable,
            executable=cat_runtime,
        ),
        _find(
            command=f"{runtime}\0{lookalike}\0".encode(),
            child_stat=foreground,
            daemon_executable=daemon_executable,
            executable=runtime,
        ),
        _find(
            command=exact,
            child_stat=foreground,
            daemon_executable=daemon_executable,
            executable=str(tmp_path),
        ),
        _find(
            command=exact,
            child_stat=foreground,
            daemon_executable=tmp_path / "missing" / "overseerd",
            executable=runtime,
        ),
        _find(
            command=exact,
            child_stat=foreground,
            daemon_executable=missing_runtime_daemon,
            executable=runtime,
        ),
    )

    assert cases == (None,) * len(cases)


def test_prepared_daemon_resolution_races_fail_closed(
    *, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    daemon_executable, _runtime = _prepared_daemon(root=tmp_path / "candidate")

    def failed_resolution(self: Path, *, strict: bool = False) -> Path:
        del self, strict
        raise OSError("prepared identity changed during observation")

    monkeypatch.setattr(Path, "resolve", failed_resolution)

    assert (
        tmux_daemon_liveness.foreground_daemon_process(
            root_pid=ROOT,
            daemon_executable=daemon_executable,
        )
        is None
    )


def test_default_proc_readers_and_freshness_changes_fail_closed(*, tmp_path: Path) -> None:
    daemon_executable, runtime = _prepared_daemon(root=tmp_path / "candidate")
    foreground = _stat(
        process_group=FOREGROUND_GROUP,
        foreground_group=FOREGROUND_GROUP,
        starttime="child-start",
    )
    exact = f"{runtime}\0{daemon_executable}\0".encode()
    root_reads = 0
    child_reads = 0

    def changing_stat(*, pid: int) -> str:
        nonlocal child_reads, root_reads
        if pid == ROOT:
            root_reads += 1
            return _stat(
                process_group=ROOT,
                foreground_group=FOREGROUND_GROUP,
                starttime=f"root-{root_reads}",
            )
        child_reads += 1
        return _stat(
            process_group=FOREGROUND_GROUP,
            foreground_group=FOREGROUND_GROUP,
            starttime=f"child-{child_reads}",
        )

    missing_root = tmux_daemon_liveness.foreground_daemon_process(
        root_pid=999_999_999,
        daemon_executable=daemon_executable,
    )
    missing_executable = tmux_daemon_liveness.foreground_daemon_process(
        root_pid=ROOT,
        daemon_executable=daemon_executable,
        children_of=lambda *, pid: [999_999_999] if pid == ROOT else [],
        cmdline_of=lambda *, pid: exact,
        stat_of=lambda *, pid: foreground,
    )
    changed = _find(
        command=exact,
        child_stat=foreground,
        daemon_executable=daemon_executable,
        executable=runtime,
        stat_of=changing_stat,
    )

    assert (missing_root, missing_executable, changed) == (None, None, None)
