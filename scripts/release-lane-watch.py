#!/usr/bin/env python3
"""Report whether a release workflow's lane is persistently failing.

The forge query lives HERE, in the caller, never in the enforcement aggregate:
`just check` runs on every commit and push, and a network dependency inside it
would make the gate fail for reasons unrelated to the tree. Work-item
overseer-hgq4wi.15.

Exit 1 when the lane is failing, so a scheduled job goes red and is visible on
the forge's own workflow list without needing anywhere else to look.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overseer.release_lane_watch import lane_state, notice_text

# Deliberately far wider than any observed block. The real 123-cut outage reads
# as 4 cuts at limit 20 and 84 at limit 100 -- a limit is a measurement boundary,
# so this asks for far more history than it expects to need and lets the detector
# report truncation if even that is not enough.
_LIMIT = 400


def main() -> int:
    workflow = sys.argv[1] if len(sys.argv) > 1 else "release-tag.yml"
    proc = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "gh",
            "run",
            "list",
            "--workflow",
            workflow,
            "--limit",
            str(_LIMIT),
            "--json",
            "conclusion,createdAt",
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        _ = sys.stderr.write(f"release-lane-watch: forge query failed: {proc.stderr.strip()}\n")
        return 2

    runs = [
        {"conclusion": r.get("conclusion", ""), "created_at": r.get("createdAt", "")}
        for r in json.loads(proc.stdout)
    ]
    state = lane_state(runs=runs)
    text = notice_text(workflow=workflow, state=state)
    if not text:
        considered = state["runs_considered"]
        _ = sys.stdout.write(
            f"release-lane-watch: {workflow} healthy ({considered} runs considered)\n"
        )
        return 0
    _ = sys.stdout.write(f"{text}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
