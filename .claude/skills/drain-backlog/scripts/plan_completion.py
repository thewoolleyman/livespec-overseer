"""drain-backlog plan completion: a PLAN is a completable unit, not one more row.

`snapshot.py` freezes ROWS. A plan is not a row: it is a `plan/<slug>/` directory,
a subject epic, and that epic's children, and it is FINISHED once every one of
those children is closed — at which point the epic must be closed and the
directory archived through the plan's own gates (child disposition plus an
independent completeness review of the epic itself).

Four defects shaped this module, every one measured against livespec-dev-tooling
on 2026-09-08 (work-item `overseer-exz7`):

1. The old `stale_plans()` fired on "epic CLOSED and directory still live" — the
   INVERSE of the failure that actually occurs. Run over that whole tenant it
   flagged NOTHING, while `console-factory-build-cache` (epic `3u3gm2` at
   `backlog`, children `3u3gm2.1` and `.2` both CLOSED, directory live) sat
   finished-but-unarchived and unseen. `FINISHED_UNARCHIVED` is that state, and
   it is the one that carries a drive-to-completion action.
2. Membership keyed on `metadata.plan_slug` alone MISSES the plans that need
   attention: four of eight plan directories in that tenant had no epic carrying
   their slug. So slugs are collected from the DIRECTORY TREE as well as from the
   ledger, and the subject epic is resolved through the plan's own
   `associated_work_item_id` anchor file when no row carries the slug.
3. That same key OVER-COUNTS, because children INHERIT their epic's slug: 40 rows
   came back plan-bearing for 8 directories, `performance-improvements-01` eleven
   times (`yilyxr` plus `.1` through `.10`). Records are keyed by SLUG, exactly
   one per plan, and the subject epic is a ROOT id — never an inheriting child.
4. Archival used to be out of scope entirely, so a finished plan sat open
   indefinitely with nothing driving it. Every record now names its own next
   action, and `records_needing_action` is the queue.

The anchor file has no way to name a CROSS-TENANT epic, so a plan whose real
anchor lives in another tenant writes the sentinel `unassigned` rather than a
false local id (`mutation-testing-keystone`, whose anchor is `livespec-mutreal`
in the livespec tenant). That is a DECLARATION, not a missing link: it reports as
`CROSS_TENANT_ANCHOR` and never as `UNLINKED`, because a check that fires
permanently on a correctly-declared plan is a check that comes to be ignored.

This module is PURE — it reads the plan directory tree and already-parsed ledger
rows, and issues no ledger write of any kind. A drain never archives itself on a
status flip: the record NAMES the action; the operator runs it through the gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

Item = dict[str, Any]

__all__: list[str] = [
    "ACTIONABLE_STATES",
    "ACTIONS",
    "ANCHOR_FILENAME",
    "ARCHIVED",
    "ARCHIVE_DIRNAME",
    "CLOSED_STATUSES",
    "CROSS_TENANT_ANCHOR",
    "CROSS_TENANT_ANCHOR_SENTINEL",
    "EPIC_CLOSED_DIR_LIVE",
    "EPIC_OPEN_DIR_ARCHIVED",
    "FINISHED_UNARCHIVED",
    "IN_PROGRESS",
    "UNLINKED",
    "PlanRecord",
    "anchor_of",
    "children_of",
    "is_closed",
    "ledger_plan_slugs",
    "live_plan_slugs",
    "plan_records",
    "plan_slug_of",
    "plan_state",
    "record_json",
    "records_needing_action",
    "root_id_of",
    "status_of",
    "subject_epic",
]

# The anchor file a plan directory carries beside its research; the one place a
# cross-tenant plan can say so, and the second identification route when no
# ledger row carries the slug.
ANCHOR_FILENAME = "associated_work_item_id"
ARCHIVE_DIRNAME = "archive"
CROSS_TENANT_ANCHOR_SENTINEL = "unassigned"
# `done` is the beads-native terminal name; the lifecycle status is `closed`.
# Both are read here because this module READS a ledger it does not write.
CLOSED_STATUSES = frozenset({"closed", "done"})

ARCHIVED = "archived"
CROSS_TENANT_ANCHOR = "cross-tenant-anchor"
EPIC_CLOSED_DIR_LIVE = "epic-closed-directory-live"
EPIC_OPEN_DIR_ARCHIVED = "epic-open-directory-archived"
FINISHED_UNARCHIVED = "finished-unarchived"
IN_PROGRESS = "in-progress"
UNLINKED = "unlinked"

ACTIONS = {
    ARCHIVED: "none: the directory is archived and the epic is closed",
    CROSS_TENANT_ANCHOR: "none here: the anchor is DECLARED cross-tenant; "
    "completion belongs to the owning tenant",
    EPIC_CLOSED_DIR_LIVE: "archive plan/{slug}/ through the plan gates, or reopen the epic: "
    "the epic is closed while its directory is still live",
    EPIC_OPEN_DIR_ARCHIVED: "dispose every child, review the epic, then close it: "
    "plan/{slug}/ is already archived while the epic is still open",
    FINISHED_UNARCHIVED: "DRIVE TO COMPLETION: dispose every child, run an independent "
    "completeness review of the epic itself, close the epic, then archive plan/{slug}/",
    IN_PROGRESS: "none: work remains open under the epic",
    UNLINKED: "link plan/{slug}/ to its subject epic (metadata plan_slug, or the "
    "{anchor} anchor file), then re-read completion",
}

# The states a drain tick must act on. `IN_PROGRESS` and `ARCHIVED` are healthy,
# and `CROSS_TENANT_ANCHOR` is a correct declaration — reporting any of the three
# as work is how a completion check earns its way into being ignored.
ACTIONABLE_STATES = frozenset(
    {
        EPIC_CLOSED_DIR_LIVE,
        EPIC_OPEN_DIR_ARCHIVED,
        FINISHED_UNARCHIVED,
        UNLINKED,
    }
)


@dataclass(frozen=True, kw_only=True)
class PlanRecord:
    """One plan, keyed by slug — never one per inheriting child (defect 3)."""

    plan_slug: str
    state: str
    action: str
    epic: str | None
    epic_status: str | None
    anchor: str | None
    dir_live: bool
    child_count: int
    closed_child_count: int


def plan_slug_of(*, item: Item) -> str | None:
    """The row's `metadata.plan_slug`, or None. Children INHERIT this (defect 3)."""
    meta: Any = item.get("metadata") or {}
    slug: Any = meta.get("plan_slug") if isinstance(meta, dict) else None
    text = str(slug).strip() if slug else ""
    return text or None


def status_of(*, item: Item) -> str:
    value: Any = item.get("status")
    return value.strip().lower() if isinstance(value, str) else ""


def is_closed(*, item: Item) -> bool:
    return status_of(item=item) in CLOSED_STATUSES


def root_id_of(*, identifier: str) -> str:
    """`livespec-dev-tooling-3u3gm2.1` -> `livespec-dev-tooling-3u3gm2`.

    The dotted-suffix convention `snapshot.py` already roots children by; a plan
    epic is the ROOT id, which is what keeps an inheriting child from being
    mistaken for its own plan's subject.
    """
    return identifier.split(".")[0]


def live_plan_slugs(*, repo: Path) -> tuple[str, ...]:
    """Every `plan/<slug>/` directory that is not the archive.

    This is the source the ledger cannot supply: a plan directory whose subject
    epic carries no `plan_slug` is invisible to a metadata-only membership key.
    """
    plan_dir = repo / "plan"
    if not plan_dir.is_dir():
        return ()
    return tuple(
        sorted(
            entry.name
            for entry in plan_dir.iterdir()
            if entry.is_dir() and entry.name != ARCHIVE_DIRNAME
        )
    )


def ledger_plan_slugs(*, items: list[Item]) -> tuple[str, ...]:
    """Every distinct slug any row carries — deduped, so inheritance cannot inflate it."""
    slugs = {slug for item in items if (slug := plan_slug_of(item=item)) is not None}
    return tuple(sorted(slugs))


def anchor_of(*, repo: Path, slug: str) -> str | None:
    """The plan's declared anchor: the first non-empty line of its anchor file."""
    path = repo / "plan" / slug / ANCHOR_FILENAME
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def subject_epic(*, items: list[Item], slug: str, anchor: str | None) -> Item | None:
    """The one row a plan is ABOUT — resolved by anchor first, then by slug.

    The anchor wins because it is the plan's own declaration and reaches epics the
    slug cannot (defect 2). The sentinel is not an id, so it never resolves here;
    it is read later, where its absence of a local epic is a DECLARATION rather
    than a missing link. The slug fallback admits only ROOT ids, so the eleven
    inheriting children of `performance-improvements-01` cannot become its subject.
    """
    if anchor is not None and anchor != CROSS_TENANT_ANCHOR_SENTINEL:
        for item in items:
            if str(item.get("id")) == anchor:
                return item
    tagged = [
        item for item in items if plan_slug_of(item=item) == slug and "." not in str(item.get("id"))
    ]
    epics = [item for item in tagged if item.get("issue_type") == "epic"]
    candidates = sorted(epics or tagged, key=lambda item: str(item.get("id")))
    return candidates[0] if candidates else None


def children_of(*, items: list[Item], epic_id: str) -> tuple[Item, ...]:
    return tuple(
        item
        for item in items
        if str(item.get("id")) != epic_id and root_id_of(identifier=str(item.get("id"))) == epic_id
    )


def _state_without_epic(*, dir_live: bool, anchor: str | None) -> str:
    if not dir_live:
        return ARCHIVED
    if anchor == CROSS_TENANT_ANCHOR_SENTINEL:
        return CROSS_TENANT_ANCHOR
    return UNLINKED


def _state_with_epic(*, epic: Item, children: tuple[Item, ...], dir_live: bool) -> str:
    if is_closed(item=epic):
        return EPIC_CLOSED_DIR_LIVE if dir_live else ARCHIVED
    if not dir_live:
        return EPIC_OPEN_DIR_ARCHIVED
    # `children and` is load-bearing: "every child is closed" is VACUOUSLY true of
    # an epic with no children at all, and an epic nobody has filed work under is
    # not finished — it is unstarted. Without this guard the drive-to-completion
    # action would fire on every childless epic in the tenant.
    if children and all(is_closed(item=child) for child in children):
        return FINISHED_UNARCHIVED
    return IN_PROGRESS


def plan_state(
    *,
    epic: Item | None,
    children: tuple[Item, ...],
    dir_live: bool,
    anchor: str | None,
) -> str:
    if epic is None:
        return _state_without_epic(dir_live=dir_live, anchor=anchor)
    return _state_with_epic(epic=epic, children=children, dir_live=dir_live)


def _record(*, items: list[Item], repo: Path, slug: str, live: frozenset[str]) -> PlanRecord:
    anchor = anchor_of(repo=repo, slug=slug)
    epic = subject_epic(items=items, slug=slug, anchor=anchor)
    epic_id = str(epic["id"]) if epic is not None else None
    children = () if epic_id is None else children_of(items=items, epic_id=epic_id)
    dir_live = slug in live
    state = plan_state(epic=epic, children=children, dir_live=dir_live, anchor=anchor)
    return PlanRecord(
        plan_slug=slug,
        state=state,
        action=ACTIONS[state].format(slug=slug, anchor=ANCHOR_FILENAME),
        epic=epic_id,
        epic_status=None if epic is None else status_of(item=epic),
        anchor=anchor,
        dir_live=dir_live,
        child_count=len(children),
        closed_child_count=sum(1 for child in children if is_closed(item=child)),
    )


def plan_records(*, items: list[Item], repo: Path) -> tuple[PlanRecord, ...]:
    """One record per PLAN, from BOTH identification routes, deduped by slug."""
    live = frozenset(live_plan_slugs(repo=repo))
    slugs = sorted(live.union(ledger_plan_slugs(items=items)))
    return tuple(_record(items=items, repo=repo, slug=slug, live=live) for slug in slugs)


def records_needing_action(*, records: tuple[PlanRecord, ...]) -> tuple[PlanRecord, ...]:
    return tuple(record for record in records if record.state in ACTIONABLE_STATES)


def record_json(*, record: PlanRecord) -> dict[str, Any]:
    return asdict(record)
