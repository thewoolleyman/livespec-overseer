"""daemon_log — finite retention for the append-only overseer daemon history.

The daemon's whole event history IS its stderr: every structured record goes through
``streams.write_stderr`` to ``sys.stderr``, which the launcher points at
``<checkout>/tmp/overseer/daemon.log`` and which the daemon then owns for the life of
the process. Append-only was deliberate — the log is HISTORY, the one surface that can
answer "what happened, and when?" — but UNBOUNDED was not a decision, it was the
absence of one, and it is a disk-safety defect. Measured 2026-09-11T09:03Z: one live
``overseerd`` held that file open at 8,622,275,412 bytes spanning 45 days, on a
filesystem with 268 GiB free. Nothing in the repository would ever have closed it.

This module is the retention seam, and it keeps ONE policy (:data:`DEFAULT_RETENTION`)
plus the three mechanics that honour it:

* **Rotation.** When the next write would take the active file past its bound,
  ``daemon.log`` becomes ``daemon.log.1``, each retained generation shifts one older,
  and the generation past the bound is deleted. Generation 1 is ALWAYS the newest
  retained history, so the ordering is readable from the filenames alone.
* **Descriptor ownership.** :func:`bounded_daemon_history` points BOTH ``sys.stderr``
  and the process's stderr DESCRIPTOR at the active file, and so does every rotation.
  The descriptor half is what makes a rotation complete rather than partial: the shell
  redirect the launcher installs (``overseerd 2>> …/daemon.log``), every subprocess the
  daemon spawns, and the interpreter's own crash traceback all write through fd 2, and
  none of them can be told that a rotation happened. Re-pointing fd 2 tells all of them
  at once.
* **Migration, in two halves split by what each may destroy.** A ``daemon.log`` already
  past the bound before any of this existed must NOT be truncated or unlinked while a
  live daemon still holds it open. The SAFE half needs no special handling and no
  special permission: ordinary rotation fires on the very first write, because the file
  is already over the bound, and renames it to ``daemon.log.1`` INTACT — so the active
  path is bounded from then on and anything still holding that inode keeps a reachable
  file. What is left is a retained generation many times the bound, and reclaiming that
  means releasing its inode. That half — :func:`trim_over_bound_generations`, reached
  through :func:`reclaim_over_bound_history` — may run ONLY once the caller holds the
  daemon's SINGLETON LOCK, because owning a descriptor proves which file this process
  writes, not that it is the only writer.

Stdlib-only, like every module in this folder, and it imports no sibling: it sits
BELOW ``streams``, which consults it on every stderr write.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

__all__: list[str] = [
    "DEFAULT_RETENTION",
    "HISTORY_FILENAME",
    "MAX_ACTIVE_BYTES",
    "RETAINED_GENERATIONS",
    "Retention",
    "active_history_size",
    "bound_stderr_history",
    "bounded_daemon_history",
    "generation_path",
    "reclaim_over_bound_history",
    "retained_generation_paths",
    "rotate_generations",
    "trim_over_bound_generations",
]

# The one name of the daemon's event history, owned here because this module is what
# bounds it; `daemon.py` and `start.py` build their paths from this constant so the
# launcher and the retention policy can never disagree about which file is bounded.
HISTORY_FILENAME = "daemon.log"

# 128 MiB per file, 7 retained generations — a hard 1 GiB ceiling on the whole history.
# The arithmetic is stated rather than asserted so an operator can re-judge it: the
# live log grew 8,622,275,412 bytes in 45 days (~190 MB/day) and its newest 64 MiB held
# ~157,100 structured records, so 1 GiB is roughly FIVE DAYS of fleet history at the
# rate measured on 2026-09-11. That is the trade — five days bounded, against an 8.6 GiB
# file that was still climbing. Re-measure the rate before changing either number.
MAX_ACTIVE_BYTES = 128 * 1024 * 1024
RETAINED_GENERATIONS = 7

# The process stderr descriptor. Re-pointing it is what makes a rotation reach the
# writers that never go through `sys.stderr` at all (see the module docstring).
_STDERR_FD = 2
_SALVAGE_SUFFIX = ".salvaged"


@dataclass(frozen=True, kw_only=True)
class Retention:
    """A FINITE retention bound: one active file plus ``retained_generations`` older."""

    max_active_bytes: int
    retained_generations: int

    @property
    def total_bytes(self) -> int:
        """The ceiling on everything this policy keeps on disk, active file included."""
        return self.max_active_bytes * (self.retained_generations + 1)


DEFAULT_RETENTION = Retention(
    max_active_bytes=MAX_ACTIVE_BYTES,
    retained_generations=RETAINED_GENERATIONS,
)


def generation_path(*, log_path: Path, generation: int) -> Path:
    """The path of retained ``generation`` — 1 is the newest, the bound is the oldest."""
    return log_path.with_name(f"{log_path.name}.{generation}")


def retained_generation_paths(*, log_path: Path, retention: Retention) -> list[Path]:
    """Every retained generation path under ``retention``, newest first."""
    return [
        generation_path(log_path=log_path, generation=generation)
        for generation in range(1, retention.retained_generations + 1)
    ]


def active_history_size(*, log_path: Path) -> int:
    """Bytes already in the active history file; 0 when it does not exist yet."""
    if not log_path.is_file():
        return 0
    return log_path.stat().st_size


def rotate_generations(*, log_path: Path, retention: Retention) -> None:
    """Shift every retained generation one older and drop the one past the bound.

    Renames only, oldest first, so no generation is ever overwritten by a younger one
    and the active file keeps its own descriptor throughout — a rename moves a NAME,
    not an open file, which is why a daemon may rotate the log it is writing to.
    """
    paths = retained_generation_paths(log_path=log_path, retention=retention)
    paths[-1].unlink(missing_ok=True)
    for index in range(len(paths) - 1, 0, -1):
        newer = paths[index - 1]
        if newer.is_file():
            _ = newer.replace(paths[index])
    if log_path.is_file():
        _ = log_path.replace(paths[0])


def _keep_newest_bytes(*, path: Path, keep: int) -> int:
    """Replace ``path`` with its newest ``keep`` bytes, starting at a record boundary.

    Seeks rather than reads forward, so a multi-gigabyte file costs one seek and one
    bounded read. The leading PARTIAL record is dropped: a history file whose first line
    is half a JSON record is worse than one record shorter. A tail carrying no newline
    at all is a single record longer than the bound and is kept whole instead.
    """
    with path.open("rb") as source:
        _ = source.seek(-keep, os.SEEK_END)
        tail = source.read()
    _, newline, whole = tail.partition(b"\n")
    salvaged = whole if newline else tail
    trimmed = path.with_name(f"{path.name}{_SALVAGE_SUFFIX}")
    _ = trimmed.write_bytes(salvaged)
    _ = trimmed.replace(path)
    return len(salvaged)


def trim_over_bound_generations(*, log_path: Path, retention: Retention) -> int:
    """Trim any RETAINED generation a pre-retention history left over the bound.

    Returns the bytes reclaimed, 0 when every generation was already inside the bound.

    This is the second half of the migration, and the destructive one. Ordinary rotation
    does the first half on its own and does it SAFELY: the over-bound ``daemon.log``
    becomes ``daemon.log.1`` by rename, intact, so the active path is bounded from the
    next write onward and anything still holding that inode keeps a reachable file. What
    remains is a retained generation many times the bound — the 8.6 GiB measured on
    2026-09-11 — and reclaiming it means releasing that inode, which is why this is the
    half that needs the exclusivity precondition :func:`reclaim_over_bound_history`
    carries. The active file is never touched here, so no descriptor is re-pointed.
    """
    reclaimed = 0
    for path in retained_generation_paths(log_path=log_path, retention=retention):
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size <= retention.max_active_bytes:
            continue
        reclaimed += size - _keep_newest_bytes(path=path, keep=retention.max_active_bytes)
    return reclaimed


def _open_active_history(*, log_path: Path) -> TextIO:
    """Open the active history for append and point the stderr DESCRIPTOR at it."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("a", encoding="utf-8", buffering=1)
    _ = os.dup2(handle.fileno(), _STDERR_FD)
    return handle


def _active_history_path() -> Path | None:
    """The bounded history file ``sys.stderr`` is attached to, or None for any other.

    ``getattr`` rather than ``sys.stderr.name`` because a replaced stderr need not have
    a name at all: pytest's capture buffer raises ``AttributeError`` for it, and a real
    terminal answers ``"<stderr>"``. Both correctly resolve to "not a history file", so
    the one-shot track CLI, ``overseer-start`` and the test suite never rotate the live
    daemon's log out from under it.
    """
    candidate = Path(str(getattr(sys.stderr, "name", "")))
    if candidate.name != HISTORY_FILENAME or not candidate.is_file():
        return None
    return candidate


def _reopen_active_history(*, log_path: Path) -> None:
    """Install a fresh active history in place of the one ``sys.stderr`` holds.

    ``sys.stderr`` is never left closed or unset: the outgoing handle is flushed (so no
    buffered record spills into the wrong file), the fresh file is installed, and only
    THEN is the outgoing handle closed.
    """
    closing = sys.stderr
    _ = closing.flush()
    sys.stderr = _open_active_history(log_path=log_path)
    _ = closing.close()


def _rotate_stderr_history(*, log_path: Path, retention: Retention) -> None:
    """Shift the generations under the live writer and reopen a fresh active file.

    The generations shift while the outgoing handle still holds the renamed inode — a
    rename moves a NAME, not an open file — so no write can be lost between the two
    steps.
    """
    rotate_generations(log_path=log_path, retention=retention)
    _reopen_active_history(log_path=log_path)


def bound_stderr_history(*, chunk: str) -> bool:
    """Rotate the active daemon history when ``chunk`` would push it past its bound.

    Called by ``streams.write_stderr`` on every write, BEFORE the write lands, so no
    generation ever exceeds :data:`DEFAULT_RETENTION`'s ``max_active_bytes``. Returns
    whether a rotation happened — False for every process whose stderr is not the
    daemon's history file, and False for an EMPTY active file, which takes an
    over-bound single record whole rather than dropping the event.

    The policy is read from the module at call time rather than taken as an argument:
    one bound governs the daemon, and a caller able to pass a different one could write
    records that outlive their own retention.
    """
    log_path = _active_history_path()
    if log_path is None:
        return False
    retention = DEFAULT_RETENTION
    size = active_history_size(log_path=log_path)
    if size == 0 or size + len(chunk.encode("utf-8")) <= retention.max_active_bytes:
        return False
    _rotate_stderr_history(log_path=log_path, retention=retention)
    return True


def reclaim_over_bound_history() -> int:
    """Reclaim over-bound retained history. ONLY for a caller holding the daemon lock.

    Returns the bytes reclaimed, or 0 when there was nothing over the bound — including
    for any process whose stderr is not the daemon's history file at all.

    **The precondition is the whole point.** Trimming a generation releases its inode, so
    running it while ANOTHER ``overseerd`` still has that inode open would leave that
    daemon appending to an unlinked file and silently losing its history. Owning fd 2
    cannot answer "am I the only writer?"; the per-store singleton lock can, and already
    exists to answer exactly that for the rest of the daemon. A live sibling daemon holds
    that lock, so a second daemon is refused it and leaves the sibling's history alone.

    That is also why this is not startup's job: at startup no lock has been attempted
    yet, so a second daemon would reclaim before learning it is not the owner.

    The active file is rotated here rather than left to the next write, so the result does
    not depend on whether anything has been logged yet. That rotation is the SAFE half
    either way — a rename the descriptor follows — and doing it explicitly is what makes
    the reclaim total: a log that is over the bound is always fully migrated by the time
    this returns, whether or not the daemon has emitted its first event.
    """
    log_path = _active_history_path()
    if log_path is None:
        return 0
    retention = DEFAULT_RETENTION
    if active_history_size(log_path=log_path) > retention.max_active_bytes:
        _rotate_stderr_history(log_path=log_path, retention=retention)
    return trim_over_bound_generations(log_path=log_path, retention=retention)


@contextmanager
def bounded_daemon_history(*, log_path: Path) -> Iterator[None]:
    """Own the daemon's event history under :data:`DEFAULT_RETENTION` for this block.

    Takes ownership of ``sys.stderr`` AND the stderr descriptor and restores both on
    exit. Migrating a pre-existing over-bound log is deliberately NOT done here — see
    :func:`migrate_active_history` for why that needs the singleton lock first.
    """
    original = sys.stderr
    saved_fd = os.dup(_STDERR_FD)
    sys.stderr = _open_active_history(log_path=log_path)
    try:
        yield
    finally:
        installed = sys.stderr
        sys.stderr = original
        _ = os.dup2(saved_fd, _STDERR_FD)
        os.close(saved_fd)
        installed.close()
