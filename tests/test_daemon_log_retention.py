"""Regression coverage for the BOUND on the overseer daemon's event-history log.

The defect these pin: `tmp/overseer/daemon.log` was append-only AND unbounded, and on
2026-09-11 a live `overseerd` held it open at 8,622,275,412 bytes spanning 45 days. This
file owns the retention POLICY and its mechanics — the bound, the rotation, the
generation ordering, and the salvage of an over-bound file. `test_daemon_log_startup.py`
owns what the DAEMON does with them at startup, and the operator-facing surfaces.

The bound proof deliberately drives `streams.write_stderr` rather than a rotation helper
called by hand: that function is the single funnel the daemon's whole history arrives on,
so it is the only place a bound can be proven to hold for every event.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

import pytest
import streams

__all__: list[str] = []

_PACKAGE = Path(__file__).resolve().parent.parent / "overseer"


def _daemon_log() -> ModuleType:
    """The retention seam, imported only once its module exists on disk."""
    module_path = _PACKAGE / "daemon_log.py"
    assert module_path.is_file(), (
        "overseer/daemon_log.py must hold the daemon history retention seam; "
        "the daemon log is otherwise append-only and unbounded"
    )
    return importlib.import_module("daemon_log")


@contextmanager
def _bounded(
    *,
    log_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    max_active_bytes: int,
    retained_generations: int,
) -> Iterator[int]:
    """Run a block under the daemon's own history ownership with a tiny bound."""
    module = _daemon_log()
    monkeypatch.setattr(
        module,
        "DEFAULT_RETENTION",
        module.Retention(
            max_active_bytes=max_active_bytes,
            retained_generations=retained_generations,
        ),
    )
    with module.bounded_daemon_history(log_path=log_path) as salvaged:
        yield salvaged


def _existing_generations(*, log_path: Path) -> list[Path]:
    module = _daemon_log()
    return [
        path
        for path in module.retained_generation_paths(
            log_path=log_path, retention=module.DEFAULT_RETENTION
        )
        if path.is_file()
    ]


def test_the_retention_bound_is_explicit_and_finite() -> None:
    """An unbounded default is the defect; the shipped policy must be a real ceiling."""
    module = _daemon_log()

    assert module.HISTORY_FILENAME == "daemon.log"
    assert module.MAX_ACTIVE_BYTES > 0
    assert module.RETAINED_GENERATIONS > 0
    assert module.DEFAULT_RETENTION.max_active_bytes == module.MAX_ACTIVE_BYTES
    assert module.DEFAULT_RETENTION.retained_generations == module.RETAINED_GENERATIONS
    assert module.DEFAULT_RETENTION.total_bytes == module.MAX_ACTIVE_BYTES * (
        module.RETAINED_GENERATIONS + 1
    )


def test_generation_paths_are_ordered_newest_first(*, tmp_path: Path) -> None:
    """Generation 1 is the newest retained history, so ordering reads off the names."""
    module = _daemon_log()
    log_path = tmp_path / "daemon.log"
    retention = module.Retention(max_active_bytes=64, retained_generations=3)

    assert module.generation_path(log_path=log_path, generation=2) == tmp_path / "daemon.log.2"
    assert module.retained_generation_paths(log_path=log_path, retention=retention) == [
        tmp_path / "daemon.log.1",
        tmp_path / "daemon.log.2",
        tmp_path / "daemon.log.3",
    ]


def test_rotation_shifts_every_generation_and_drops_the_one_past_the_bound(
    *, tmp_path: Path
) -> None:
    """Renames only, oldest first, so no generation is overwritten by a younger one."""
    module = _daemon_log()
    log_path = tmp_path / "daemon.log"
    retention = module.Retention(max_active_bytes=64, retained_generations=3)
    log_path.write_text("active\n", encoding="utf-8")
    for generation, body in ((1, "newest\n"), (2, "middle\n"), (3, "oldest\n")):
        module.generation_path(log_path=log_path, generation=generation).write_text(
            body, encoding="utf-8"
        )

    module.rotate_generations(log_path=log_path, retention=retention)

    assert not log_path.exists()
    assert [
        module.generation_path(log_path=log_path, generation=generation).read_text(encoding="utf-8")
        for generation in (1, 2, 3)
    ] == ["active\n", "newest\n", "middle\n"]


def test_rotation_with_one_retained_generation_replaces_it(*, tmp_path: Path) -> None:
    """The shift loop is empty at a bound of one; the active file still becomes gen 1."""
    module = _daemon_log()
    log_path = tmp_path / "daemon.log"
    retention = module.Retention(max_active_bytes=64, retained_generations=1)
    log_path.write_text("active\n", encoding="utf-8")
    module.generation_path(log_path=log_path, generation=1).write_text("gone\n", encoding="utf-8")

    module.rotate_generations(log_path=log_path, retention=retention)

    assert (
        module.generation_path(log_path=log_path, generation=1).read_text(encoding="utf-8")
        == "active\n"
    )


def test_rotation_tolerates_absent_generations_and_an_absent_active_file(*, tmp_path: Path) -> None:
    """A history that has not rotated yet has gaps; rotating must not require them."""
    module = _daemon_log()
    log_path = tmp_path / "daemon.log"
    retention = module.Retention(max_active_bytes=64, retained_generations=3)
    module.generation_path(log_path=log_path, generation=2).write_text("two\n", encoding="utf-8")

    module.rotate_generations(log_path=log_path, retention=retention)

    assert not module.generation_path(log_path=log_path, generation=1).exists()
    assert not module.generation_path(log_path=log_path, generation=2).exists()
    assert (
        module.generation_path(log_path=log_path, generation=3).read_text(encoding="utf-8")
        == "two\n"
    )
    assert module.active_history_size(log_path=log_path) == 0


def test_writes_past_the_threshold_rotate_and_no_file_exceeds_the_bound(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The deterministic bound proof: drive the real write funnel past the threshold."""
    log_path = tmp_path / "tmp" / "overseer" / "daemon.log"
    bound = 512
    generations = 3

    with _bounded(
        log_path=log_path,
        monkeypatch=monkeypatch,
        max_active_bytes=bound,
        retained_generations=generations,
    ):
        for index in range(120):
            streams.write_stderr(text=f"record {index:04d} {'x' * 40}\n")

    retained = _existing_generations(log_path=log_path)
    assert len(retained) == generations
    for path in [log_path, *retained]:
        assert path.stat().st_size <= bound, f"{path} breached the {bound}-byte bound"

    def first_index(*, path: Path) -> int:
        return int(path.read_text(encoding="utf-8").splitlines()[0].split()[1])

    ordered = [*reversed(retained), log_path]
    indices = [first_index(path=path) for path in ordered]
    assert indices == sorted(indices), f"generations are out of order: {indices}"
    assert "record 0119" in log_path.read_text(encoding="utf-8")


def test_a_record_larger_than_the_bound_is_kept_whole_in_an_empty_generation(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bound governs RETENTION, never whether an event is recorded at all."""
    log_path = tmp_path / "tmp" / "overseer" / "daemon.log"
    oversized = f"{'q' * 900}\n"

    with _bounded(
        log_path=log_path,
        monkeypatch=monkeypatch,
        max_active_bytes=256,
        retained_generations=2,
    ):
        streams.write_stderr(text=oversized)
        assert log_path.read_text(encoding="utf-8") == oversized
        streams.write_stderr(text="after\n")

    assert log_path.read_text(encoding="utf-8") == "after\n"
    assert (
        _daemon_log().generation_path(log_path=log_path, generation=1).read_text(encoding="utf-8")
        == oversized
    )


def test_a_process_whose_stderr_is_not_the_live_history_never_rotates(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one-shot track CLI and overseer-start must never rotate the daemon's log.

    Three shapes, all of which must be inert: a capture buffer with no name at all, a
    named file that is not the history, and a history path whose file is gone.
    """
    module = _daemon_log()
    assert module.bound_stderr_history(chunk="from a capture buffer\n") is False

    for name in ("other.log", "daemon.log"):
        surrogate = tmp_path / name
        handle = surrogate.open("a", encoding="utf-8")
        monkeypatch.setattr("sys.stderr", handle)
        surrogate.unlink()
        assert module.bound_stderr_history(chunk="not the live history file\n") is False
        handle.close()


def test_trimming_an_over_bound_generation_keeps_its_newest_whole_records(
    *,
    tmp_path: Path,
) -> None:
    """Reclaiming must preserve recoverable history, starting at a record boundary."""
    module = _daemon_log()
    log_path = tmp_path / "daemon.log"
    retention = module.Retention(max_active_bytes=256, retained_generations=2)
    generation = module.generation_path(log_path=log_path, generation=2)
    generation.write_text(
        "".join(f"old record {index:05d}\n" for index in range(400)), encoding="utf-8"
    )
    original_size = generation.stat().st_size

    reclaimed = module.trim_over_bound_generations(log_path=log_path, retention=retention)

    preserved = generation.read_text(encoding="utf-8")
    assert reclaimed == original_size - generation.stat().st_size
    assert generation.stat().st_size <= retention.max_active_bytes
    assert preserved.startswith("old record "), "a partial leading record must be dropped"
    assert "old record 00399\n" in preserved, "the newest history must be recoverable"
    assert "old record 00000" not in preserved


def test_trimming_keeps_a_single_over_bound_record_whole(*, tmp_path: Path) -> None:
    """A tail with no record boundary in it is one long record, not a partial one."""
    module = _daemon_log()
    log_path = tmp_path / "daemon.log"
    retention = module.Retention(max_active_bytes=256, retained_generations=2)
    generation = module.generation_path(log_path=log_path, generation=1)
    generation.write_text("z" * 600, encoding="utf-8")

    assert module.trim_over_bound_generations(log_path=log_path, retention=retention) == 344
    assert generation.read_text(encoding="utf-8") == "z" * 256


def test_generations_already_inside_the_bound_are_never_rewritten(*, tmp_path: Path) -> None:
    """An absent generation and a small one are both left exactly as they are."""
    module = _daemon_log()
    log_path = tmp_path / "daemon.log"
    retention = module.Retention(max_active_bytes=256, retained_generations=2)
    generation = module.generation_path(log_path=log_path, generation=2)
    generation.write_text("small\n", encoding="utf-8")

    assert module.trim_over_bound_generations(log_path=log_path, retention=retention) == 0
    assert generation.read_text(encoding="utf-8") == "small\n"
    assert not module.generation_path(log_path=log_path, generation=1).exists()
