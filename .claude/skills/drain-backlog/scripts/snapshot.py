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
ruling (SKILL.md section 2).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

Item = dict[str, Any]

TIER1_RE = re.compile(
    r"hook|gate[- ]|pre-push|pre-commit|red[_-]green|amend|dispatcher|sandbox|fabro|"
    r"commit-refuse|worktree pack|lefthook|release-please|uv\.lock|uv (dev-dep )?install|"
    r"master (is |goes |reads )?red|reds every|blocks? (every|unrelated) (commit|pr|push)|"
    r"cannot (commit|push)|refuse[sd]? (every|all) push|adapter|app token|"
    r"workflows? permission",
    re.IGNORECASE,
)
TIER2_RE = re.compile(
    r"vacuous|false green|passes? (vacuously|when|on a|by construction)|half-pair|"
    r"convicts?|true.positive|false.positive|never (reads?|resolves?|verif|asks?|checks?)|"
    r"reports? (pass|nothing|zero|a confident)|silently|exits? 0|returncode|"
    r"enforce[sd]? (by )?nothing|inspects? nothing|check[- _]|conformance|"
    r"heading[_-]coverage|coverage",
    re.IGNORECASE,
)
REFER_RE = re.compile(
    r"^livespec core|livespec core:|\bcore'?s\b|livespec-driver-|livespec-orchestrator|"
    r"orchestrator tenant|livespec-runtime|livespec-console|referred",
    re.IGNORECASE,
)
NOT_TIER1_RE = re.compile(
    r"^spec:|^\[gate|ROP arming child|^document|^docs?:|fan-?out|arming", re.IGNORECASE
)
EXEMPT_PREFIX = "factory-exempt:"
TIER1_MAX_PRIORITY = 2
P01_MAX_PRIORITY = 1
UNKNOWN_PRIORITY = 9
TITLE_WIDTH = 90
TIER_NAMES = {
    1: "Tier 1 - factory-path defects (first, by hand where the factory cannot)",
    2: "Tier 2 - enforcement-suite correctness (false greens, half-pairs, true-positive fails)",
    3: "Tier 3 - P0/P1 epics and their children",
    4: "Tier 4 - the long tail",
}


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


def prio(item: Item) -> int:
    p: Any = item.get("priority")
    try:
        return int(str(p).lstrip("Pp"))
    except (TypeError, ValueError):
        return UNKNOWN_PRIORITY


def labels_of(item: Item) -> list[str]:
    raw: Any = item.get("labels") or []
    return [str(x) for x in raw]


def title_of(item: Item) -> str:
    return str(item.get("title") or "")


def plan_slug_of(item: Item) -> str | None:
    meta: Any = item.get("metadata") or {}
    slug: Any = meta.get("plan_slug") if isinstance(meta, dict) else None
    return str(slug) if slug else None


def tier_of(item: Item, epics_p01: set[str]) -> tuple[int, str]:
    title = title_of(item)
    if any(lbl.startswith(EXEMPT_PREFIX) for lbl in labels_of(item)):
        return 1, "carries a factory-exempt label"
    if (
        TIER1_RE.search(title)
        and not NOT_TIER1_RE.search(title)
        and prio(item) <= TIER1_MAX_PRIORITY
    ):
        return 1, "title names the factory path (hooks, gates, dispatcher, sandbox, CI/pin drift)"
    if TIER2_RE.search(title):
        return 2, "check passes vacuously or on a half-pair, or convicts a true positive"
    if item.get("issue_type") == "epic" and prio(item) <= P01_MAX_PRIORITY:
        return 3, "P0/P1 epic"
    root = str(item["id"]).split(".")[0]
    if root in epics_p01:
        return 3, f"child of P0/P1 epic {root}"
    return 4, "long tail by priority then age"


def row_of(item: Item, epics_p01: set[str], repo: Path) -> Item:
    tier, reason = tier_of(item, epics_p01)
    labels = labels_of(item)
    row: Item = {
        "id": item["id"],
        "status": item.get("status"),
        "type": item.get("issue_type"),
        "priority": prio(item),
        "title": title_of(item),
        "tier": tier,
        "tier_reason": reason,
        "created_at": item.get("created_at"),
        "labels": labels,
        "valve": item.get("status") == "blocked" and any("needs-human" in lbl for lbl in labels),
        "refer_candidate": bool(REFER_RE.search(title_of(item))),
        "has_acceptance": bool(str(item.get("acceptance_criteria") or "").strip()),
    }
    slug = plan_slug_of(item)
    if slug:
        row["plan_slug"] = slug
        row["plan_dir_live"] = (repo / "plan" / slug).is_dir()
    return row


def stale_plans(items: list[Item], repo: Path) -> list[Item]:
    stale: list[Item] = []
    for item in items:
        slug = plan_slug_of(item)
        if item.get("status") == "closed" and slug and (repo / "plan" / slug).is_dir():
            stale.append(
                {
                    "epic": item["id"],
                    "plan_slug": slug,
                    "status": "closed",
                    "dir_live": True,
                    "note": "epic closed but plan directory still live: archive it through "
                    "the plan gates, or reopen",
                }
            )
    return stale


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
    plans: list[Item] = [
        {
            "epic": r["id"],
            "plan_slug": r["plan_slug"],
            "status": r["status"],
            "dir_live": r["plan_dir_live"],
            "tier": r["tier"],
            "order": r["order"],
        }
        for r in rows
        if r.get("plan_slug")
    ]
    plans += stale_plans(items, repo)
    return {
        "taken_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": str(repo),
        "frozen_ids": frozen,
        "open_count": len(rows),
        "items": rows,
        "plans": plans,
    }


def flags_of(r: Item) -> list[str]:
    flags: list[str] = []
    if r["refer_candidate"]:
        flags.append("refer?")
    if r.get("plan_slug"):
        suffix = "" if r.get("plan_dir_live") else " (dir missing)"
        flags.append(f"plan:{r['plan_slug']}{suffix}")
    if r["admitted_after_snapshot"]:
        flags.append("after-freeze")
    if not r["has_acceptance"]:
        flags.append("no-criteria")
    return flags


def tier_table(rows: list[Item]) -> list[str]:
    lines = ["| # | id | P | status | title | why here |", "|---|---|---|---|---|---|"]
    for r in rows:
        flags = flags_of(r)
        short = str(r["id"]).split("-")[-1]
        why = r["tier_reason"] + ("; " + ", ".join(flags) if flags else "")
        title = str(r["title"])[:TITLE_WIDTH]
        lines.append(
            f"| {r['order']} | `{short}` | P{r['priority']} | {r['status']} | {title} | {why} |"
        )
    return lines


def markdown(snap: Item) -> str:
    rows: list[Item] = snap["items"]
    after = sum(1 for r in rows if r["admitted_after_snapshot"])
    lines = [
        f"# drain-backlog snapshot - {snap['repo']} - {snap['taken_at']}",
        "",
        f"{snap['open_count']} open items; {len(snap['frozen_ids'])} frozen ids; "
        f"{after} admitted after the freeze.",
    ]
    for t in (1, 2, 3, 4):
        tier_rows = [r for r in rows if r["tier"] == t and not r["valve"]]
        lines += ["", f"## {TIER_NAMES[t]} ({len(tier_rows)})", "", *tier_table(tier_rows)]
    valves = [r for r in rows if r["valve"]]
    lines += ["", f"## Valves - blocked needs-human, decided as findings ({len(valves)})", ""]
    lines += [f"- `{r['id']}` P{r['priority']}: {str(r['title'])[:110]}" for r in valves]
    stale = [p for p in snap["plans"] if p.get("note")]
    if stale:
        lines += ["", "## Plans whose epic is closed but whose directory is live", ""]
        lines += [f"- `{p['epic']}` plan/{p['plan_slug']}/ - {p['note']}" for p in stale]
    lines += [
        "",
        "Tiering is a heuristic; read each tier-1/2 item's own text before ruling. "
        "Status is read from the ledger; this file never records it.",
    ]
    return "\n".join(lines)


def status(items: list[Item], snap: Item) -> Item:
    by_id = {str(i["id"]): i for i in items}
    frozen: list[str] = snap["frozen_ids"]
    counts: dict[str, int] = {}
    for fid in frozen:
        st = str(by_id.get(fid, {}).get("status", "MISSING"))
        counts[st] = counts.get(st, 0) + 1
    closed = counts.get("closed", 0)
    return {
        "frozen": len(frozen),
        "closed": closed,
        "remaining": len(frozen) - closed,
        "by_status": counts,
        "taken_at": snap["taken_at"],
    }


def report_status(items: list[Item], snap_path: Path, *, as_json: bool) -> int:
    if not snap_path.exists():
        err("no snapshot yet: run without --status to freeze one")
        return 2
    s = status(items, json.loads(snap_path.read_text()))
    if as_json:
        out(json.dumps(s, indent=1))
    else:
        out(
            f"frozen {s['frozen']}: closed {s['closed']}, remaining {s['remaining']} "
            f"{s['by_status']} (snapshot {s['taken_at']})"
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
        return report_status(items, snap_path, as_json=bool(a.json))

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
