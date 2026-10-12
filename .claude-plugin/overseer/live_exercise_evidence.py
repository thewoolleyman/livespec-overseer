#!/usr/bin/env python3
"""Fail-closed verdicts for an isolated overseer lifecycle record."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

__all__: list[str] = ["main"]

REQUIRED_STAGES = (
    "bootstrap",
    "adoption",
    "wrap-up",
    "declaration",
    "replacement",
    "continuation",
)


def _verify_evidence(*, evidence: Path) -> tuple[int, str]:
    """Return a process code and an honest lifecycle verdict for ``evidence``."""
    if not evidence.is_file():
        return 1, f"INCOMPLETE lifecycle: evidence file is missing: {evidence}"

    observations: dict[str, tuple[str, str]] = {}
    for line_number, raw_line in enumerate(evidence.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            raw_record = json.loads(raw_line)
        except json.JSONDecodeError:
            return 1, f"FAILED lifecycle: malformed record at line {line_number}"
        if not isinstance(raw_record, dict):
            return 1, f"FAILED lifecycle: record {line_number} is not an object"
        record = cast("dict[str, object]", raw_record)
        stage = record.get("stage")
        if stage not in REQUIRED_STAGES:
            continue
        status = record.get("status")
        detail = record.get("detail", "")
        observations[cast("str", stage)] = (str(status), str(detail))

    for stage in REQUIRED_STAGES:
        observation = observations.get(stage)
        if observation is not None and observation[0] != "passed":
            detail = observation[1] or f"recorded status {observation[0]!r}"
            return 1, f"FAILED lifecycle at {stage}: {detail}"

    missing = [stage for stage in REQUIRED_STAGES if stage not in observations]
    if missing:
        return 1, f"INCOMPLETE lifecycle: missing stages: {', '.join(missing)}"
    return 0, "COMPLETE lifecycle: all required stages passed"


def main(*, argv: list[str] | None = None) -> int:
    """Check one JSONL lifecycle record and print its verdict."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("evidence", type=Path)
    args = parser.parse_args(argv)
    code, message = _verify_evidence(evidence=args.evidence)
    destination = sys.stdout if code == 0 else sys.stderr
    _ = destination.write(message + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
