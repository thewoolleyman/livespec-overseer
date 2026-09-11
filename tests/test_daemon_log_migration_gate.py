"""Regression coverage for WHEN over-bound daemon history may be RECLAIMED.

Migrating the 8,622,275,412-byte log measured on 2026-09-11 splits into two halves, and
the split is by what each may destroy.

The safe half needs no permission: the file is already over the bound, so ordinary
rotation fires on the first write and renames it to `daemon.log.1` INTACT. Anything still
holding that inode — the launcher's `overseerd 2>> …/daemon.log` redirect, or a sibling
daemon — keeps a reachable file, and the active path is bounded from then on.

Reclaiming that oversized generation is the unsafe half: trimming it releases the inode,
and a sibling `overseerd` holding it would go on appending to an unlinked file and
silently lose its history. Owning fd 2 cannot answer "am I the only writer?" — the
per-store singleton lock can, and a live sibling holds it. So reclamation runs from
inside the lock, and a daemon refused that lock leaves the history alone. These tests pin
both sides.
"""

from __future__ import annotations

import fcntl
import importlib
import io
import json
import os
from pathlib import Path
from types import ModuleType

import _supervisor_lifecycle
import pytest
import supervisor

__all__: list[str] = []

_PACKAGE = Path(__file__).resolve().parent.parent / "overseer"
_BOUND = 2048


def _daemon_log() -> ModuleType:
    """The retention seam, imported only once its module exists on disk."""
    module_path = _PACKAGE / "daemon_log.py"
    assert module_path.is_file(), "overseer/daemon_log.py must hold the retention seam"
    return importlib.import_module("daemon_log")


def _gated_seam() -> ModuleType:
    """The seam, with reclamation present AS ITS OWN STEP and wired to the lock holder.

    Both assertions are the design claim rather than a smoke test: reclamation has to be
    separable from startup (so it can be withheld) and it has to be called from the run
    loop (the only place that has proven exclusivity).
    """
    module = _daemon_log()
    assert hasattr(module, "reclaim_over_bound_history"), (
        "reclaiming over-bound retained history must be its own step, so it can be "
        "withheld from a daemon that has not proven it is the only writer"
    )
    wiring = (_PACKAGE / "_supervisor_lifecycle.py").read_text(encoding="utf-8")
    assert "reclaim_over_bound_history" in wiring, (
        "the reclaim must be called from the run loop, which is what holds the "
        "singleton lock; calling it at startup runs it before any lock is attempted"
    )
    return module


class _FakeTmux:
    def list_sessions(self) -> list[str]:
        return []


def _supervisor_for(*, tmp_path: Path) -> supervisor.Supervisor:
    """A Supervisor whose whole host surface is injected, so `run` only needs the lock.

    `require_render_terminal=False` is load-bearing: left at its default, `run_loop`
    refuses on the no-controlling-terminal gate BEFORE reaching the lock, so both sides
    of the gate would look identical and the lock-refusal test would pass for the wrong
    reason. That is how the first draft of these tests was wrong.
    """
    sup = supervisor.Supervisor(
        tmux=_FakeTmux(),
        store_path=tmp_path / "map.jsonl",
        stamp_path=tmp_path / "stamps.json",
        watch_repos=[],
        status_path=tmp_path / "status.json",
        runtime_state_path=tmp_path / "runtime-state.json",
        proc_root=tmp_path,
        which=lambda _name: "/usr/bin/tmux",
        out=io.StringIO(),
        sleep=lambda _seconds: None,
        require_render_terminal=False,
    )
    sup.tick = lambda *, act: None  # type: ignore[assignment]
    return sup


def _over_bound_log(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An over-bound active history, plus a tiny policy to judge it against."""
    module = _daemon_log()
    log_path = tmp_path / "tmp" / "overseer" / "daemon.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("".join(f"old {index:05d}\n" for index in range(400)), encoding="utf-8")
    monkeypatch.setattr(
        module,
        "DEFAULT_RETENTION",
        module.Retention(max_active_bytes=_BOUND, retained_generations=3),
    )
    return log_path


def test_the_run_loop_reclaims_over_bound_history_once_it_holds_the_lock(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reclamation happens from inside the lock, and says so in the live history."""
    module = _gated_seam()
    log_path = _over_bound_log(tmp_path=tmp_path, monkeypatch=monkeypatch)
    original_size = log_path.stat().st_size
    generation = module.generation_path(log_path=log_path, generation=1)

    with module.bounded_daemon_history(log_path=log_path):
        _supervisor_for(tmp_path=tmp_path).run(once=True)

    assert generation.is_file(), "rotation must have retained the over-bound file"
    assert generation.stat().st_size <= _BOUND, "the retained generation was not reclaimed"
    preserved = generation.read_text(encoding="utf-8")
    assert preserved.startswith("old "), "a partial leading record must be dropped"
    assert "old 00399\n" in preserved, "the newest history must stay recoverable"
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    reclaimed = [event for event in events if event["event"] == "daemon-log-reclaimed"]
    assert len(reclaimed) == 1, "reclamation must be recorded, not done silently"
    assert reclaimed[0]["reclaimed_bytes"] == original_size - generation.stat().st_size


def test_a_daemon_refused_the_singleton_lock_reclaims_nothing(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dangerous case: a second daemon must not free an inode a sibling still holds.

    `held` stands in for that sibling's descriptor. Rotation still moves the oversized
    file out of the active path — that is a rename, so the descriptor follows it and
    nothing is lost — but the file must survive at full size, because only the lock
    holder may release it.
    """
    module = _gated_seam()
    log_path = _over_bound_log(tmp_path=tmp_path, monkeypatch=monkeypatch)
    original_size = log_path.stat().st_size
    held = os.open(log_path, os.O_WRONLY | os.O_APPEND)
    inode_before = os.fstat(held).st_ino
    sup = _supervisor_for(tmp_path=tmp_path)
    incumbent = _supervisor_lifecycle.singleton_lock_path(sup=sup).open("w", encoding="utf-8")
    fcntl.flock(incumbent.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    with module.bounded_daemon_history(log_path=log_path):
        sup.run(once=True)
    os.close(held)
    incumbent.close()

    generation = module.generation_path(log_path=log_path, generation=1)
    assert generation.stat().st_size == original_size, "a refused daemon reclaimed history"
    assert generation.stat().st_ino == inode_before, "the sibling's inode was released"
    # The SPECIFIC refusal matters: a bare "refusing to start" also matches the
    # no-controlling-terminal gate, which would pass this test without the lock ever
    # being consulted.
    assert "another overseer daemon holds" in log_path.read_text(encoding="utf-8")


def test_reclaiming_with_no_daemon_history_attached_is_inert() -> None:
    """Every non-daemon caller — the one-shot CLI, overseer-start, this suite — no-ops."""
    assert _gated_seam().reclaim_over_bound_history() == 0


def test_history_already_inside_the_bound_is_left_alone_by_the_lock_holder(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Holding the lock is permission to reclaim, never a reason to rewrite anything."""
    module = _gated_seam()
    log_path = tmp_path / "tmp" / "overseer" / "daemon.log"
    log_path.parent.mkdir(parents=True)
    generation = module.generation_path(log_path=log_path, generation=1)
    generation.write_text("retained and small\n", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "DEFAULT_RETENTION",
        module.Retention(max_active_bytes=_BOUND, retained_generations=3),
    )

    with module.bounded_daemon_history(log_path=log_path):
        reclaimed = module.reclaim_over_bound_history()

    assert reclaimed == 0
    assert generation.read_text(encoding="utf-8") == "retained and small\n"
