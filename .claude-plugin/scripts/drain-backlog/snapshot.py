#!/usr/bin/env python3
"""drain-backlog snapshot: freeze the open backlog, tier it, persist it, report progress.

    snapshot.py --repo <path>            # first freeze (refuses to overwrite a snapshot)
    snapshot.py --repo <path> --update   # re-prioritise everything open; keep frozen_ids
    snapshot.py --repo <path> --status   # closed-of-frozen progress from a fresh ledger read
    snapshot.py --repo <path> --json     # machine output instead of Markdown

Run under the repo's credential wrapper (with-livespec-env.sh) so `bd` reaches the tenant.
State: <repo>/tmp/drain-backlog/snapshot.json (+ snapshot-<UTC>.json history on --update).

The tiering is a HEURISTIC over title, labels and priority. It orders the triage
proposal; it does not rule. The session reads tier-1/2 candidates' own text before
ruling (the operating contract's section 2). It lives beside this module in
`snapshot_tiering`; the Markdown the snapshot is READ as lives in `snapshot_report`.

The report has TWO units. Rows are the frozen work-item scope, tiered above. PLANS
are the second, computed by `plan_completion` from the `plan/` tree AND the ledger,
one record per slug, each carrying whether that plan's DECLARED scope is drained
and the act that would drive it to epic-closed and directory-archived. Both
`--status` and the Markdown report cover both units, because a drain that closes
every item and leaves its finished plans open has not finished either.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import plan_completion
from snapshot_report import markdown
from snapshot_tiering import P01_MAX_PRIORITY, prio, row_of

Item = dict[str, Any]


def out(text: str) -> None:
    _ = sys.stdout.write(text + "\n")


def err(text: str) -> None:
    _ = sys.stderr.write(text + "\n")


def read_ledger(repo: Path) -> list[Item]:
    argv = ["bd", "list", "--all", "--limit", "0", "--json"]
    # argv list, no shell; `bd` resolves through the credential wrapper's PATH.
    done = subprocess.run(argv, cwd=str(repo), capture_output=True, text=True, check=True)  # noqa: S603
    parsed: Any = json.loads(done.stdout or "[]")
    return [i for i in parsed if isinstance(i, dict)]


def build(items: list[Item], repo: Path, frozen_ids: list[str] | None) -> Item:
    open_items = [i for i in items if i.get("status") != "closed"]
    epics_p01 = {
        str(i["id"])
        for i in open_items
        if i.get("issue_type") == "epic" and prio(i) <= P01_MAX_PRIORITY
    }
    rows = [row_of(i, epics_p01, repo) for i in open_items]
    rows.sort(key=lambda r: (r["tier"], r["priority"], r["created_at"] or ""))
    for n, r in enumerate(rows, 1):
        r["order"] = n
    ids = [str(r["id"]) for r in rows]
    frozen = frozen_ids if frozen_ids is not None else ids
    frozen_set = set(frozen)
    for r in rows:
        r["admitted_after_snapshot"] = r["id"] not in frozen_set
    # PLANS ARE A SECOND UNIT, computed from EVERY item (not just the open rows)
    # and from the `plan/` tree, so a plan whose subject epic carries no
    # `plan_slug` is still reported and an inheriting child cannot double-count
    # its own plan. See `plan_completion` for the four defects this replaced.
    records = plan_completion.plan_records(items=items, repo=repo)
    return {
        "taken_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": str(repo),
        "frozen_ids": frozen,
        "open_count": len(rows),
        "items": rows,
        "plans": [plan_completion.record_json(record=r) for r in records],
    }


def status(items: list[Item], snap: Item, repo: Path) -> Item:
    by_id = {str(i["id"]): i for i in items}
    frozen: list[str] = snap["frozen_ids"]
    counts: dict[str, int] = {}
    for fid in frozen:
        st = str(by_id.get(fid, {}).get("status", "MISSING"))
        counts[st] = counts.get(st, 0) + 1
    closed = counts.get("closed", 0)
    # Plans are re-read here, not carried from the snapshot file: the exit gate
    # (the operating contract's section 9) now requires every plan closed-and-archived
    # as well as every frozen id closed, and a status a file records is a shadow ledger.
    records = plan_completion.plan_records(items=items, repo=repo)
    pending = plan_completion.records_needing_action(records=records)
    return {
        "frozen": len(frozen),
        "closed": closed,
        "remaining": len(frozen) - closed,
        "by_status": counts,
        "plans": len(records),
        "plans_needing_action": [plan_completion.record_json(record=r) for r in pending],
        "taken_at": snap["taken_at"],
    }


def report_status(items: list[Item], snap_path: Path, repo: Path, *, as_json: bool) -> int:
    if not snap_path.exists():
        err("no snapshot yet: run without --status to freeze one")
        return 2
    s = status(items, json.loads(snap_path.read_text()), repo)
    if as_json:
        out(json.dumps(s, indent=1))
    else:
        out(
            f"frozen {s['frozen']}: closed {s['closed']}, remaining {s['remaining']} "
            f"{s['by_status']} (snapshot {s['taken_at']})"
        )
        out(
            f"plans {s['plans']}: {len(s['plans_needing_action'])} need an act "
            + ", ".join(f"{p['plan_slug']}={p['state']}" for p in s["plans_needing_action"])
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    _ = ap.add_argument("--repo", default=".")
    _ = ap.add_argument("--update", action="store_true", help="re-prioritise; keep frozen_ids")
    _ = ap.add_argument("--status", action="store_true", help="closed-of-frozen progress")
    _ = ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    repo = Path(str(a.repo)).resolve()
    state = repo / "tmp" / "drain-backlog"
    state.mkdir(parents=True, exist_ok=True)
    snap_path = state / "snapshot.json"
    items = read_ledger(repo)
    if a.status:
        return report_status(items, snap_path, repo, as_json=bool(a.json))

    frozen_ids: list[str] | None = None
    if snap_path.exists():
        if not a.update:
            err(f"{snap_path} exists; pass --update to re-prioritise or --status for progress")
            return 2
        previous: Item = json.loads(snap_path.read_text())
        frozen_ids = [str(x) for x in previous.get("frozen_ids", [])]
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        _ = (state / f"snapshot-{stamp}.json").write_text(snap_path.read_text())
    snap = build(items, repo, frozen_ids)
    _ = snap_path.write_text(json.dumps(snap, indent=1) + "\n")
    out(json.dumps(snap, indent=1) if a.json else markdown(snap))
    err(f"[written {snap_path}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
