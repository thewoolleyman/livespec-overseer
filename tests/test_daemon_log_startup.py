"""Regression coverage for the daemon taking OWNERSHIP of its bounded history.

The companion to `test_daemon_log_retention.py`, which owns the retention policy and its
mechanics. This file owns what `overseerd` does with them, driven through `daemon.main`
because owning the history is a property of STARTING the daemon rather than of calling a
helper:

* it takes the stderr DESCRIPTOR, not just `sys.stderr`. The launcher's
  `overseerd 2>> …/daemon.log` redirect, every subprocess the daemon spawns, and the
  interpreter's own crash traceback all write through fd 2 and cannot be told a rotation
  happened, so a rotation that left fd 2 behind would be half a rotation;
* it MIGRATES a `daemon.log` that is already over the bound. The live file was
  8,622,275,412 bytes when retention was introduced (measured 2026-09-11) and the
  launcher's redirect still held that inode open, so the migration may neither discard
  the history nor truncate the file underneath its own writer;
* it states the bound, the retained generations and the recovery procedure in `--help`,
  which is the only place a source-free operator can find them.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from types import ModuleType

import _supervisor_diagnostics
import pytest

from overseer import daemon

__all__: list[str] = []

_PACKAGE = Path(__file__).resolve().parent.parent / "overseer"
_STDERR_FD_LINK = Path("/proc/self/fd/2")


def _daemon_log() -> ModuleType:
    """The retention seam, imported only once its module exists on disk."""
    module_path = _PACKAGE / "daemon_log.py"
    assert module_path.is_file(), "overseer/daemon_log.py must hold the retention seam"
    return importlib.import_module("daemon_log")


def _run_daemon_with_bound(
    *,
    log_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bound: int,
    events: int,
) -> list[str]:
    """Start and stop the daemon through its real entry point under a tiny bound.

    Returns what the process's stderr DESCRIPTOR pointed at while the daemon was running
    — the evidence that ownership reached fd 2 and survived every rotation before it.
    """
    module = _daemon_log()
    observed: list[str] = []

    def _fake_run(*, warn_percent: int | None = None, idle_nudge: bool = True) -> int:
        del warn_percent, idle_nudge
        for index in range(events):
            _supervisor_diagnostics.log(message=f"live event {index:04d}")
        observed.append(str(_STDERR_FD_LINK.readlink()))
        return 0

    monkeypatch.setattr(daemon, "_default_daemon_log_path", lambda: log_path, raising=False)
    monkeypatch.setattr(daemon.supervisor, "run_daemon", _fake_run)
    monkeypatch.setattr(
        module,
        "DEFAULT_RETENTION",
        module.Retention(max_active_bytes=bound, retained_generations=3),
    )

    assert daemon.main(argv=[]) == 0
    return observed


def test_the_daemon_owns_its_stderr_descriptor_across_a_rotation(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The live-writer proof: events after a rotation reach the ACTIVE history file.

    The descriptor assertion is the load-bearing half. Re-pointing `sys.stderr` alone
    would satisfy every byte-level assertion below while leaving the launcher's redirect,
    subprocess stderr and crash tracebacks writing into a closed generation.
    """
    module = _daemon_log()
    log_path = tmp_path / "tmp" / "overseer" / "daemon.log"
    bound = 1024
    before = str(_STDERR_FD_LINK.readlink())

    observed = _run_daemon_with_bound(
        log_path=log_path, monkeypatch=monkeypatch, bound=bound, events=80
    )

    assert observed == [str(log_path)], "the daemon must own fd 2, not just sys.stderr"
    assert str(_STDERR_FD_LINK.readlink()) == before, "fd 2 must be restored on the way out"
    active = log_path.read_text(encoding="utf-8")
    assert log_path.stat().st_size <= bound
    assert module.generation_path(log_path=log_path, generation=1).is_file()
    assert "live event 0079" in active, "the newest event must land in the ACTIVE file"
    assert "live event 0000" not in active, "the oldest event must have been rotated out"
    for line in active.splitlines():
        assert json.loads(line)["severity"] == "info"


def test_a_pre_existing_over_bound_log_is_migrated_at_startup(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`held` stands in for the launcher redirect that still has the old inode open."""
    module = _daemon_log()
    log_path = tmp_path / "tmp" / "overseer" / "daemon.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        "".join(f"old record {index:05d}\n" for index in range(400)), encoding="utf-8"
    )
    original_size = log_path.stat().st_size
    held = os.open(log_path, os.O_WRONLY | os.O_APPEND)
    inode_before = os.fstat(held).st_ino
    bound = 2048

    _ = _run_daemon_with_bound(log_path=log_path, monkeypatch=monkeypatch, bound=bound, events=0)
    held_size = os.fstat(held).st_size
    os.close(held)

    assert held_size == original_size, "the file a live daemon holds open was truncated"
    assert log_path.stat().st_ino != inode_before, "the active file must be a fresh inode"
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    migrated = [event for event in events if event["event"] == "daemon-log-migrated"]
    assert len(migrated) == 1, "the migration must be recorded as an event, not done silently"
    assert 0 < migrated[0]["salvaged_bytes"] <= bound
    preserved = module.generation_path(log_path=log_path, generation=1).read_text(encoding="utf-8")
    assert "old record 00399\n" in preserved, "the newest history must stay recoverable"


def test_help_states_the_bound_the_generations_and_the_recovery_procedure(
    *, capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A source-free operator must learn the bound and how to read retained history."""
    module = _daemon_log()
    log_path = tmp_path / "tmp" / "overseer" / "daemon.log"
    monkeypatch.setattr(daemon, "_default_daemon_log_path", lambda: log_path, raising=False)

    with pytest.raises(SystemExit) as exc_info:
        daemon.main(argv=["--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "Event-history retention" in help_text
    assert str(module.MAX_ACTIVE_BYTES) in help_text
    assert f"{module.RETAINED_GENERATIONS} retained generation" in help_text
    assert str(module.DEFAULT_RETENTION.total_bytes) in help_text
    assert f"daemon.log.{module.RETAINED_GENERATIONS}" in help_text
    assert "oldest-first" in help_text
    assert "never truncated" in help_text


def test_the_launcher_and_the_retention_policy_resolve_one_filename(*, tmp_path: Path) -> None:
    """The documented launch path must redirect into the file the policy bounds.

    Pinned structurally, because the failure mode is drift rather than a wrong value:
    two independent `"daemon.log"` literals agree until one of them is edited, and then
    the launcher creates a file nothing bounds while the daemon bounds a file nothing
    writes. Both sides resolve the single constant `daemon_log` owns instead.
    """
    module = _daemon_log()
    target = tmp_path / module.HISTORY_FILENAME

    for source in ("start.py", "daemon.py"):
        body = (_PACKAGE / source).read_text(encoding="utf-8")
        assert "daemon_log.HISTORY_FILENAME" in body, f"{source} must resolve the one filename"
    assert daemon.default_daemon_log_path().name == module.HISTORY_FILENAME
    command = daemon.start.daemon_command(warn_percent=None, log_path=target)
    assert command.endswith(f"2>> {target}")
