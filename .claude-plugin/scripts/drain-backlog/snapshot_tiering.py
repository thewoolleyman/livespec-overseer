"""drain-backlog tiering: the HEURISTIC that orders the triage proposal.

`snapshot.py` freezes the scope and persists it; this module decides what ORDER
that scope is proposed in, and says so per item. The tiering is a heuristic over
title, labels and priority — it orders, it does not rule, and every row carries
its own `tier_reason` so the session can read a mis-tiered item's own text and
move it (the operating contract's section 2).

The four tiers are worked in order because a false green poisons the evidence of
everything after it: factory-path defects first (the factory cannot fix the path
it runs on), then enforcement-suite correctness, then P0/P1 epics and their
children, then the long tail by priority and age.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

Item = dict[str, Any]

__all__: list[str] = [
    "EXEMPT_PREFIX",
    "NOT_TIER1_RE",
    "P01_MAX_PRIORITY",
    "REFER_RE",
    "TIER1_MAX_PRIORITY",
    "TIER1_RE",
    "TIER2_RE",
    "UNKNOWN_PRIORITY",
    "Item",
    "labels_of",
    "plan_slug_of",
    "prio",
    "row_of",
    "tier_of",
    "title_of",
]

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
