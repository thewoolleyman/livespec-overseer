#!/usr/bin/env python3
"""Report whether a release workflow's lane is persistently failing.

The forge query lives HERE, in the caller, never in the enforcement aggregate:
`just check` runs on every commit and push, and a network dependency inside it
would make the gate fail for reasons unrelated to the tree. Work-item
overseer-hgq4wi.15.

IT TALKS TO THE REST API THROUGH THE STDLIB, NOT THROUGH `gh`. The first version
shelled out to `gh run list` and died with FileNotFoundError on the self-hosted
runner, where `gh` is not installed — the watcher for a lane nobody was watching
could not itself run. urllib is always present, which is the same stdlib-only
posture the rest of this package holds.

EXIT CODES ARE THREE-VALUED ON PURPOSE:
    0  the lane is healthy (or failing below the transient threshold)
    1  the lane is FAILING — this is the finding
    2  CANNOT MEASURE — the forge was unreachable, unauthorized, or unparsable
A watcher that cannot measure must never report healthy. Collapsing 2 into 0
would make an unreachable forge look like a green lane, which is the vacuous-pass
defect this thread exists to remove; collapsing it into 1 would cry wolf and get
the job muted. So the caller can tell all three apart.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overseer.release_lane_watch import lane_state, notice_text

# Deliberately far wider than any observed block. The real 123-cut outage reads
# as 4 cuts at limit 20 and 84 at limit 100 -- a limit is a measurement boundary,
# so this asks for far more history than it expects to need and lets the detector
# report truncation if even that is not enough.
_PER_PAGE = 100
_PAGES = 4
_TIMEOUT_S = 30
_SLUG_PARTS = 2


def repo_slug() -> str | None:
    """Prefer the runner's own answer; fall back to the checkout's remote."""
    slug = os.environ.get("GITHUB_REPOSITORY")
    if slug:
        return slug
    proc = subprocess.run(  # noqa: S603
        ["git", "remote", "get-url", "origin"],  # noqa: S607
        capture_output=True,
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        return None
    url = proc.stdout.strip().removesuffix(".git")
    parts = url.replace(":", "/").split("/")
    return "/".join(parts[-_SLUG_PARTS:]) if len(parts) >= _SLUG_PARTS else None


def fetch_runs(*, slug: str, workflow: str, token: str) -> list[dict[str, str]] | None:
    """Return decided runs newest-first, or None when the lane cannot be measured."""
    collected: list[dict[str, str]] = []
    for page in range(1, _PAGES + 1):
        url = (
            f"https://api.github.com/repos/{slug}/actions/workflows/{workflow}"
            f"/runs?per_page={_PER_PAGE}&page={page}"
        )
        request = urllib.request.Request(url)  # noqa: S310
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            return None
        runs = payload.get("workflow_runs")
        if not isinstance(runs, list):
            return None
        collected.extend(
            {
                "conclusion": str(r.get("conclusion") or ""),
                "created_at": str(r.get("created_at") or ""),
            }
            for r in runs
        )
        if len(runs) < _PER_PAGE:
            break
    return collected


def main() -> int:
    workflow = sys.argv[1] if len(sys.argv) > 1 else "release-tag.yml"
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    slug = repo_slug()
    if not token or not slug:
        _ = sys.stderr.write(
            f"release-lane-watch: CANNOT MEASURE {workflow} — "
            f"{'no token' if not token else 'no repository slug'}\n"
        )
        return 2

    runs = fetch_runs(slug=slug, workflow=workflow, token=token)
    if runs is None:
        _ = sys.stderr.write(
            f"release-lane-watch: CANNOT MEASURE {workflow} — forge unreachable or unparsable\n"
        )
        return 2

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
