#!/usr/bin/env python3
"""Verify live plan directories have exactly one plan_slug metadata anchor."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OVERSEER_DIR = _REPO_ROOT / "overseer"
if str(_OVERSEER_DIR) not in sys.path:
    sys.path.insert(0, str(_OVERSEER_DIR))

from grooming_conformance_plan_anchors import plan_anchor_metadata_check  # noqa: E402

__all__: list[str] = ["main"]

_BD_LIST_COMMAND = ("bd", "list", "--type", "epic", "--status", "all", "--json")
_BD_TIMEOUT_SECONDS = 30
_STRICT_ENV_VAR = "LIVESPEC_STRICT_PLAN_ANCHOR_METADATA"


def main(*, argv: Sequence[str] | None = None) -> int:
    args = tuple(sys.argv[1:] if argv is None else argv)
    repo = Path(args[0]).resolve() if args else _REPO_ROOT
    if shutil.which("bd") is None:
        return _skip_or_fail(reason="bd not found")
    items = read_epic_items(repo=repo)
    if items is None:
        return _skip_or_fail(reason="bd read failed")
    check = plan_anchor_metadata_check(repo=repo, items=items)
    if check.breaching_item_ids == ():
        _ = sys.stdout.write(
            json.dumps(
                {
                    "check_id": check.key,
                    "status": "pass",
                    "scanned_plan_directories": check.scanned_item_count,
                },
                sort_keys=True,
            )
            + "\n"
        )
        return 0
    _ = sys.stderr.write(
        json.dumps(
            {
                "check_id": check.key,
                "status": "fail",
                "breaches": check.breaching_item_ids,
                "remediation": (
                    "each live plan directory must have exactly one same-tenant epic "
                    "with metadata plan_slug equal to the directory name"
                ),
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 1


def _skip_or_fail(*, reason: str) -> int:
    if os.environ.get(_STRICT_ENV_VAR) == "true":
        _ = sys.stderr.write(
            f"check-plan-anchor-metadata: {reason}; "
            f"{_STRICT_ENV_VAR}=true requires live check\n"
        )
        return 1
    _ = sys.stderr.write(
        f"check-plan-anchor-metadata: {reason}; "
        f"{_STRICT_ENV_VAR} unarmed; skipping live check\n"
    )
    return 0


def read_epic_items(*, repo: Path) -> Sequence[dict[str, object]] | None:
    try:
        completed = subprocess.run(  # noqa: S603 - fixed bd argv, no shell
            _BD_LIST_COMMAND,
            capture_output=True,
            check=False,
            cwd=repo,
            text=True,
            timeout=_BD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        _ = sys.stderr.write("check-plan-anchor-metadata: bd timed out\n")
        return None
    if completed.returncode != 0:
        _ = sys.stderr.write(f"check-plan-anchor-metadata: bd exited {completed.returncode}\n")
        return None
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError:
        _ = sys.stderr.write("check-plan-anchor-metadata: bd returned invalid json\n")
        return None
    if not isinstance(raw, list):
        _ = sys.stderr.write("check-plan-anchor-metadata: bd returned non-list json\n")
        return None
    return tuple(item for item in cast("list[object]", raw) if isinstance(item, dict))


if __name__ == "__main__":
    raise SystemExit(main())
