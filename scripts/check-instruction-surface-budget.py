#!/usr/bin/env python3
"""Check the repo-owned always-loaded instruction surface budget.

The harness limit is 150,000 characters across all loaded instruction files.
This repo can only control its root AGENTS.md/CLAUDE.md surface, while the
user-global ~/.claude/CLAUDE.md is also loaded by the harness. The repo budget
therefore reserves 5,000 characters below the harness limit: enough for the
2,272-character global file measured with the work item plus roughly the same
amount again for drift outside this repository.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

__all__: list[str] = ["main", "measure_instruction_surface"]

_DEFAULT_BUDGET = 145_000
_ENFORCE_ENV = "LIVESPEC_FAIL_IF_INSTRUCTION_SURFACE_OVER_BUDGET"
_ROOT_INSTRUCTION_PATHS = ("AGENTS.md", "CLAUDE.md")


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
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    report = measure_instruction_surface(root=root, budget=args.budget)
    enforce = args.enforce or bool(os.environ.get(_ENFORCE_ENV))
    stream = sys.stderr if report.overflow > 0 else sys.stdout

    _write_report(report=report, enforce=enforce, stream=stream)
    if report.overflow > 0 and enforce:
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
    _ = parser.add_argument("--budget", type=int, default=_DEFAULT_BUDGET)
    _ = parser.add_argument("--enforce", action="store_true")
    return parser


def _write_report(*, report: Report, enforce: bool, stream: TextIO) -> None:
    paths = ", ".join(path.name for path in report.paths) or "<none>"
    if report.overflow > 0:
        severity = "ERROR" if enforce else "WARNING"
        _ = stream.write(
            f"{severity}: instruction surface over budget: "
            f"current={report.current_chars} chars; "
            f"budget={report.budget} chars; "
            f"overflow={report.overflow} chars; "
            f"enforce_env={_ENFORCE_ENV}; "
            f"paths={paths}\n"
        )
        return
    _ = stream.write(
        "OK: instruction surface within budget: "
        f"current={report.current_chars} chars; "
        f"budget={report.budget} chars; "
        f"headroom={report.headroom} chars; "
        f"paths={paths}\n"
    )


if __name__ == "__main__":
    sys.exit(main())
