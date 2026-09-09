"""drain-backlog report: the Markdown a frozen snapshot is READ as.

`snapshot.py` owns the freeze and the persisted JSON; this module owns the only
thing an operator actually reads. The report has TWO units and both are rendered
here, because a drain that closes every item and leaves its finished plans open
has not finished either: the tiered work-item rows, and the plan records
`plan_completion` computes.

Nothing here decides anything. Every judgement — the tier, the plan state, the
act a plan needs — arrives already made in the snapshot document; this module
only lays it out so the judgement is legible.
"""

from __future__ import annotations

from typing import Any

import plan_completion

Item = dict[str, Any]

__all__: list[str] = [
    "TIER_NAMES",
    "TITLE_WIDTH",
    "Item",
    "flags_of",
    "markdown",
    "plan_sections",
    "plan_table",
    "tier_table",
]

TITLE_WIDTH = 90
TIER_NAMES = {
    1: "Tier 1 - factory-path defects (first, by hand where the factory cannot)",
    2: "Tier 2 - enforcement-suite correctness (false greens, half-pairs, true-positive fails)",
    3: "Tier 3 - P0/P1 epics and their children",
    4: "Tier 4 - the long tail",
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


def plan_table(plans: list[Item]) -> list[str]:
    # The DECLARED-SCOPE column is what makes a state legible: a plan can sit at
    # 1/1 children closed and still be `in-progress` because its own frozen
    # snapshot holds 144 open ids, and a reader seeing only the child count would
    # read that as a bug. `-` means the plan declares no scope this drain can read.
    lines = [
        "| plan | state | subject epic | children closed | scope closed | next action |",
        "|---|---|---|---|---|---|",
    ]
    for p in plans:
        epic = p["epic"] or "-"
        size = p["scope_size"]
        scope = f"{size - p['scope_open_count']}/{size}" if size else "-"
        lines.append(
            f"| `{p['plan_slug']}` | {p['state']} | `{epic}` | "
            f"{p['closed_child_count']}/{p['child_count']} | {scope} | {p['action']} |"
        )
    return lines


def plan_sections(snap: Item) -> list[str]:
    """The plan half of the report: every plan, then the ones a tick must act on.

    The predecessor printed ONE anomaly line, for "epic closed but directory
    live" — the inverse of the failure that actually occurs — so a finished plan
    produced no output at all and sat open indefinitely. Every plan is listed
    now, and the finished-but-unarchived ones are called out separately because
    they are the ones the drain drives to closed-and-archived.
    """
    plans: list[Item] = snap["plans"]
    lines = ["", f"## Plans as completable units ({len(plans)})", "", *plan_table(plans)]
    finished = [p for p in plans if p["state"] == plan_completion.FINISHED_UNARCHIVED]
    if finished:
        lines += ["", "## FINISHED but not archived - drive each to epic-closed + archived", ""]
        lines += [f"- `{p['plan_slug']}` (epic `{p['epic']}`): {p['action']}" for p in finished]
    acting = [p for p in plans if p["state"] in plan_completion.ACTIONABLE_STATES]
    other = [p for p in acting if p["state"] != plan_completion.FINISHED_UNARCHIVED]
    if other:
        lines += ["", "## Other plans needing an operator act", ""]
        lines += [f"- `{p['plan_slug']}` ({p['state']}): {p['action']}" for p in other]
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
    lines += plan_sections(snap)
    lines += [
        "",
        "Tiering is a heuristic; read each tier-1/2 item's own text before ruling. "
        "Status is read from the ledger; this file never records it.",
    ]
    return "\n".join(lines)
