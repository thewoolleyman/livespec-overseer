"""drain-backlog plan completion: a PLAN is a completable unit, not one more row.

`snapshot.py` freezes ROWS. A plan is not a row: it is a `plan/<slug>/` directory,
a subject epic, and the SCOPE that plan declared — and it is FINISHED once that
declared scope is drained, at which point the epic must be closed and the
directory archived through the plan's own gates (child disposition plus an
independent completeness review of the epic itself). A plan's children are
EVIDENCE about it, never a substitute for the scope it declared; defect 5 below
is what that distinction cost.

Five defects shaped this module, every one measured against livespec-dev-tooling
on 2026-09-08. The first four are `overseer-exz7`'s:

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

The fifth is `overseer-9gfh`, found by RUNNING the code the first four produced:

5. Completion was inferred from the ABSENCE of open children rather than from
   POSITIVE evidence that the plan's declared scope is drained. That is right
   for a plan whose scope IS its children and WRONG for a plan that tracks its
   work anywhere else, and it needs exactly ONE closed incidental child to fire
   — the state every plan reaches the moment it files a mechanical child for
   itself. The first victim was the drain's OWN plan:
   `dev-tooling-backlog-drain` reported `finished-unarchived` at 114 of 258
   closed, because its one child was closed and its real scope is a frozen
   258-id snapshot; the action that record named would have closed the epic and
   archived the directory of a LIVE drive with 144 items still open. The second
   shape is quieter and was read as a TRUE positive twice, once by this module's
   own first regression test: `console-factory-build-cache` reads 2/2 children
   closed BECAUSE the second of the three requirement carriers its plan-scope
   event names was never filed as a child at all.

So `FINISHED_UNARCHIVED` now requires POSITIVE evidence: a scope the plan itself
DECLARES and this module can READ — a frozen `*snapshot*.json` under
`plan/<slug>/` — with every id in it closed. The declared scope DECIDES and the
child set does not, which follows from the skill's own §2 rule that nothing filed
after the freeze extends the plan. A plan whose every child is closed while it
declares no readable scope reports `SCOPE_UNDECLARED`: reported, and NOT
actionable, because unproven is not the same as finished.

The `EPIC_OPEN_DIR_ARCHIVED` action was reworded in the same pass, for the same
family of reason. On that run TEN of twelve queued records were that state and
several of their epics were nowhere near closeable (`8o8e` at 12 of 31 children
closed), while the action said "dispose every child, review the epic, then close
it" unconditionally. The act it names now is reconciling the DIRECTORY against
its open epic, and it carries the open-child count so a one-item tail is
distinguishable from a live 19-item epic. The CLASSIFICATION is unchanged.

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

import json
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
    "SCOPE_DOCUMENT_GLOB",
    "SCOPE_ID_LIST_KEYS",
    "SCOPE_UNDECLARED",
    "UNLINKED",
    "PlanRecord",
    "PlanScope",
    "anchor_of",
    "children_of",
    "declared_scope",
    "is_closed",
    "ledger_plan_slugs",
    "live_plan_slugs",
    "plan_records",
    "plan_scope",
    "plan_slug_of",
    "plan_state",
    "read_json_document",
    "record_json",
    "records_needing_action",
    "root_id_of",
    "scope_ids_of",
    "status_of",
    "subject_epic",
]

# The anchor file a plan directory carries beside its research; the one place a
# cross-tenant plan can say so, and the second identification route when no
# ledger row carries the slug.
ANCHOR_FILENAME = "associated_work_item_id"
ARCHIVE_DIRNAME = "archive"
CROSS_TENANT_ANCHOR_SENTINEL = "unassigned"
# How a plan DECLARES its scope: a frozen snapshot held anywhere beneath its own
# directory — the artefact `snapshot.py` writes, and the only per-plan statement
# of scope this module can read. The repo-wide `tmp/drain-backlog/snapshot.json`
# is deliberately NOT read here: it is the scope of whatever drain is running
# now, and attributing it to a plan slug would be a guess rather than a reading.
SCOPE_DOCUMENT_GLOB = "**/*snapshot*.json"
# The id-carrying keys `snapshot.py` writes, in the order they are trusted.
SCOPE_ID_LIST_KEYS = ("frozen_ids", "items")
# `done` is the beads-native terminal name; the lifecycle status is `closed`.
# Both are read here because this module READS a ledger it does not write.
CLOSED_STATUSES = frozenset({"closed", "done"})

ARCHIVED = "archived"
CROSS_TENANT_ANCHOR = "cross-tenant-anchor"
EPIC_CLOSED_DIR_LIVE = "epic-closed-directory-live"
EPIC_OPEN_DIR_ARCHIVED = "epic-open-directory-archived"
FINISHED_UNARCHIVED = "finished-unarchived"
IN_PROGRESS = "in-progress"
SCOPE_UNDECLARED = "scope-undeclared"
UNLINKED = "unlinked"

ACTIONS = {
    ARCHIVED: "none: the directory is archived and the epic is closed",
    CROSS_TENANT_ANCHOR: "none here: the anchor is DECLARED cross-tenant; "
    "completion belongs to the owning tenant",
    EPIC_CLOSED_DIR_LIVE: "archive plan/{slug}/ through the plan gates, or reopen the epic: "
    "the epic is closed while its directory is still live",
    EPIC_OPEN_DIR_ARCHIVED: "reconcile plan/{slug}/ against its still-OPEN epic — un-archive "
    "the directory, or drive the epic to closed and leave it archived "
    "(open children: {open_children})",
    FINISHED_UNARCHIVED: "DRIVE TO COMPLETION: dispose every child, run an independent "
    "completeness review of the epic itself, close the epic, then archive plan/{slug}/ "
    "(declared scope: {scope_size} ids, every one closed)",
    IN_PROGRESS: "none: declared-scope or child work is still open",
    SCOPE_UNDECLARED: "none from this queue, and NOT finished: every child is closed, but "
    "plan/{slug}/ declares no scope this drain can read, so exhaustion is UNPROVEN — "
    "declare it (a frozen *snapshot*.json) before any drive to completion",
    UNLINKED: "link plan/{slug}/ to its subject epic (metadata plan_slug, or the "
    "{anchor} anchor file), then re-read completion",
}

# The states a drain tick must act on. `IN_PROGRESS` and `ARCHIVED` are healthy,
# `CROSS_TENANT_ANCHOR` is a correct declaration, and `SCOPE_UNDECLARED` names a
# thing that is UNPROVEN rather than a thing to do — reporting any of the four as
# work is how a completion check earns its way into being ignored.
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
    scope_size: int
    scope_open_count: int


@dataclass(frozen=True, kw_only=True)
class PlanScope:
    """A plan's DECLARED scope, and the part of it the ledger does not show closed.

    An EMPTY `ids` means the plan declares no scope this module can read, which is
    not the same as declaring an empty one — see `declared_scope`.
    """

    ids: tuple[str, ...]
    open_ids: tuple[str, ...]


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


def read_json_document(*, path: Path) -> Any | None:
    """The parsed document, or None when it will not parse as JSON."""
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload


def _ids_in(*, entries: list[Any]) -> tuple[str, ...]:
    ids: list[str] = []
    for entry in entries:
        identifier: Any = entry.get("id") if isinstance(entry, dict) else entry
        if isinstance(identifier, str) and identifier.strip():
            ids.append(identifier.strip())
    return tuple(ids)


def scope_ids_of(*, payload: Any) -> tuple[str, ...]:
    """Every work-item id ONE parsed scope document declares.

    Three shapes, all of them things `snapshot.py` itself writes or a hand-written
    scope file plausibly holds: the `frozen_ids` list it freezes, the `items` rows
    it tiers, and a bare list of ids. Anything else declares nothing, which lands
    the plan in `SCOPE_UNDECLARED` rather than in a false `finished` — the safe
    direction for a reader that cannot know every shape it will meet.
    """
    if isinstance(payload, dict):
        for key in SCOPE_ID_LIST_KEYS:
            entries: Any = payload.get(key)
            if isinstance(entries, list):
                return _ids_in(entries=entries)
        return ()
    if isinstance(payload, list):
        return _ids_in(entries=payload)
    return ()


def declared_scope(*, repo: Path, slug: str) -> tuple[str, ...]:
    """The ids the plan's own frozen snapshots declare. EMPTY means it declares none.

    The UNION across every snapshot the plan holds: a plan that re-froze keeps the
    history beside it, and the superset is the safe direction — one extra open id
    costs a `finished` this module was not entitled to declare.

    An empty result is not a declaration of an empty scope. Treating it as one
    would make freezing an empty snapshot the shortest route to a false `finished`,
    which is the same vacuity the child set is already guarded against.

    A document NAMED a snapshot that will not parse WITHDRAWS the declaration
    outright rather than being skipped: a scope read from its siblings alone is
    missing exactly the ids the unreadable file held.
    """
    ids: set[str] = set()
    for document in sorted((repo / "plan" / slug).glob(SCOPE_DOCUMENT_GLOB)):
        payload = read_json_document(path=document)
        if payload is None:
            return ()
        ids.update(scope_ids_of(payload=payload))
    return tuple(sorted(ids))


def plan_scope(*, items: list[Item], repo: Path, slug: str) -> PlanScope:
    """The plan's declared scope, measured against the ledger.

    An id no ledger row carries at all is UNKNOWN, and unknown is never evidence
    of exhaustion, so it counts as OPEN.
    """
    ids = declared_scope(repo=repo, slug=slug)
    closed = {str(item.get("id")) for item in items if is_closed(item=item)}
    return PlanScope(ids=ids, open_ids=tuple(i for i in ids if i not in closed))


def _state_without_epic(*, dir_live: bool, anchor: str | None) -> str:
    if not dir_live:
        return ARCHIVED
    if anchor == CROSS_TENANT_ANCHOR_SENTINEL:
        return CROSS_TENANT_ANCHOR
    return UNLINKED


def _live_epic_state(*, children: tuple[Item, ...], scope: PlanScope) -> str:
    """Completion for a LIVE directory under an OPEN epic — the load-bearing arc.

    A declared scope DECIDES, and the child set does not: the skill's own §2 rule
    is that nothing filed after the freeze extends the plan, so a drained frozen
    scope is exhaustion even with a later-filed child still open — and the act
    that record names begins by disposing every child.

    Absent a declared scope there is no positive evidence at all, so a child set
    that is entirely closed reports UNPROVEN rather than finished. `children and`
    stays load-bearing for the reason it always was: "every child is closed" is
    VACUOUSLY true of an epic nobody has filed work under, which is unstarted.
    """
    if scope.ids:
        return IN_PROGRESS if scope.open_ids else FINISHED_UNARCHIVED
    if children and all(is_closed(item=child) for child in children):
        return SCOPE_UNDECLARED
    return IN_PROGRESS


def _state_with_epic(
    *, epic: Item, children: tuple[Item, ...], dir_live: bool, scope: PlanScope
) -> str:
    if is_closed(item=epic):
        return EPIC_CLOSED_DIR_LIVE if dir_live else ARCHIVED
    if not dir_live:
        return EPIC_OPEN_DIR_ARCHIVED
    return _live_epic_state(children=children, scope=scope)


def plan_state(
    *,
    epic: Item | None,
    children: tuple[Item, ...],
    dir_live: bool,
    anchor: str | None,
    scope: PlanScope,
) -> str:
    if epic is None:
        return _state_without_epic(dir_live=dir_live, anchor=anchor)
    return _state_with_epic(epic=epic, children=children, dir_live=dir_live, scope=scope)


def _record(*, items: list[Item], repo: Path, slug: str, live: frozenset[str]) -> PlanRecord:
    anchor = anchor_of(repo=repo, slug=slug)
    epic = subject_epic(items=items, slug=slug, anchor=anchor)
    epic_id = str(epic["id"]) if epic is not None else None
    children = () if epic_id is None else children_of(items=items, epic_id=epic_id)
    scope = plan_scope(items=items, repo=repo, slug=slug)
    dir_live = slug in live
    state = plan_state(epic=epic, children=children, dir_live=dir_live, anchor=anchor, scope=scope)
    closed_children = sum(1 for child in children if is_closed(item=child))
    return PlanRecord(
        plan_slug=slug,
        state=state,
        action=ACTIONS[state].format(
            slug=slug,
            anchor=ANCHOR_FILENAME,
            open_children=len(children) - closed_children,
            scope_size=len(scope.ids),
        ),
        epic=epic_id,
        epic_status=None if epic is None else status_of(item=epic),
        anchor=anchor,
        dir_live=dir_live,
        child_count=len(children),
        closed_child_count=closed_children,
        scope_size=len(scope.ids),
        scope_open_count=len(scope.open_ids),
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
