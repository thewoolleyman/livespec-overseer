#!/usr/bin/env python3
"""Check the repo-owned always-loaded instruction surface budget.

ARMED, AND WITH NO LEVER THAT CAN DISARM IT (work-item overseer-csl2). This
gate shipped WARN-only (work-item overseer-4z97.1): over budget it printed a
WARNING, exited 0, and escalated to an ERROR only when an enforcement
environment variable was set — which nothing in any workflow, hook or recipe
ever set. That was deliberate at the time rather than an oversight: the
surface was ~14,000 characters OVER budget, and an enforcing gate merged that
day would have reddened the aggregate for every seat and every dispatch in
the repo, since `just check` is the single local, pre-push AND CI entry point.
The prune has since landed — the relocated guidance lives in `.ai/<topic>.md`
files, each named from the root file — so the gate is now armed and the env
lever is GONE rather than merely left unset. An unarmed lever reads as
finished and stays unarmed for months, which is the same silent-no-op defect
the gate was built to end.

THE MEASURED POPULATION is this repository's root instruction surface:
`AGENTS.md` plus the `CLAUDE.md` symlink pointing at it, counted ONCE because
the two names are one file. A gate that summed them twice would over-report
by a factor of two; one that measured `AGENTS.md` alone under-reports nothing
here but would miss a future tree where the two names diverge.

WHAT IT CANNOT SEE, and why the budget sits below the limit. The harness limit
of 150,000 characters covers every instruction file the harness loads, which
includes the user-global `~/.claude/CLAUDE.md` — a file outside this
repository that no repo gate can read and whose size is not fixed. The budget
is therefore 145,000, reserving 5,000 characters for it: enough for the
2,272-character global file measured with the work-item plus roughly the same
again for drift outside this repository. Every report says so, on both the OK
and the ERROR branch, because a figure summing less than the limit it is
compared against is misleading unless it names its own blind spot.

CHARACTERS, NOT BYTES. The harness limit is stated in characters and the file
is UTF-8, so a byte count over-reports: measured on the overflowing tree,
157,689 bytes against 156,969 characters — a 720-character phantom overflow.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

__all__: list[str] = ["main", "measure_instruction_surface"]

_HARNESS_LIMIT = 150_000
_GLOBAL_RESERVE = 5_000
_DEFAULT_BUDGET = _HARNESS_LIMIT - _GLOBAL_RESERVE
_ROOT_INSTRUCTION_PATHS = ("AGENTS.md", "CLAUDE.md")
# Emitted on BOTH report branches. The population the gate sums is narrower
# than the population the harness limit governs, and a reader comparing
# `current` against 150,000 without that caveat would conclude there is more
# headroom than there is.
_POPULATION_NOTE = (
    "note: the measured population is this repo's root instruction surface only; "
    "the user-global ~/.claude/CLAUDE.md lies OUTSIDE it, because no repo gate can read "
    "a file outside the repo, and is covered by the "
    f"{_GLOBAL_RESERVE}-char reserve this budget leaves below the "
    f"{_HARNESS_LIMIT}-char harness limit.\n"
)


@dataclass(frozen=True, kw_only=True)
class Report:
    current_chars: int
    budget: int
    paths: tuple[Path, ...]

    @property
    def headroom(self) -> int:
        return self.budget - self.current_chars

    @property
    def overflow(self) -> int:
        return self.current_chars - self.budget


def measure_instruction_surface(*, root: Path, budget: int) -> Report:
    paths = _instruction_paths(root=root)
    current_chars = sum(len(path.read_text(encoding="utf-8")) for path in paths)
    return Report(current_chars=current_chars, budget=budget, paths=paths)


def main(*, argv: list[str] | None = None) -> int:
    """Measure the surface and FAIL when it is over budget — unconditionally.

    `--root` is the only knob, and it relocates the measurement rather than
    weakening it: the budget and the harness limit are module constants with
    no flag and no environment variable behind them, so there is no spelling
    of this invocation that reports an over-budget tree as passing.
    """
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    report = measure_instruction_surface(root=root, budget=_DEFAULT_BUDGET)
    stream = sys.stderr if report.overflow > 0 else sys.stdout

    _write_report(report=report, stream=stream)
    if report.overflow > 0:
        return 1
    return 0


def _instruction_paths(*, root: Path) -> tuple[Path, ...]:
    seen: set[Path] = set()
    paths: list[Path] = []
    for relative in _ROOT_INSTRUCTION_PATHS:
        path = root / relative
        if not path.exists():
            continue
        identity = path.resolve()
        if identity in seen:
            continue
        seen.add(identity)
        paths.append(path)
    return tuple(paths)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--root", type=Path, default=Path.cwd())
    return parser


def _write_report(*, report: Report, stream: TextIO) -> None:
    paths = ", ".join(path.name for path in report.paths) or "<none>"
    if report.overflow > 0:
        _ = stream.write(
            "ERROR: instruction surface over budget: "
            f"current={report.current_chars} chars; "
            f"budget={report.budget} chars; "
            f"harness_limit={_HARNESS_LIMIT} chars; "
            f"overflow={report.overflow} chars; "
            f"paths={paths}\n"
        )
        _ = stream.write(_POPULATION_NOTE)
        return
    _ = stream.write(
        "OK: instruction surface within budget: "
        f"current={report.current_chars} chars; "
        f"budget={report.budget} chars; "
        f"harness_limit={_HARNESS_LIMIT} chars; "
        f"headroom={report.headroom} chars; "
        f"paths={paths}\n"
    )
    _ = stream.write(_POPULATION_NOTE)


if __name__ == "__main__":
    sys.exit(main())
