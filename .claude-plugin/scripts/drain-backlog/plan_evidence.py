"""drain-backlog plan evidence: the ledger's closed-set, and the scope a plan DECLARES.

`plan_completion` classifies a plan and names the act that would finish it. This
module supplies the two readings that classification is entitled to use, and
nothing else: whether an already-parsed ledger row is closed, and what scope the
plan itself DECLARED against how much of it the ledger shows drained.

The concern is separate because it is the POSITIVE-evidence half. Defect 5 in
`plan_completion`'s own record — `overseer-9gfh`, measured against
livespec-dev-tooling on 2026-09-08 — is what a classification does when it has no
such reading to consult: it infers completion from the ABSENCE of open children,
which is right for a plan whose scope IS its children and wrong for every plan
that tracks its work anywhere else. `PlanScope` is the reading that replaced that
inference, and `declared_scope`'s two refusals (an empty result is not a
declaration of an empty scope; an unparseable snapshot WITHDRAWS the declaration)
are the reason it can be trusted as evidence rather than as a hint.

Like `plan_completion` this module is PURE: it reads the plan directory tree and
already-parsed ledger rows, and issues no ledger write of any kind.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Item = dict[str, Any]

__all__: list[str] = [
    "CLOSED_STATUSES",
    "SCOPE_DOCUMENT_GLOB",
    "SCOPE_ID_LIST_KEYS",
    "Item",
    "PlanScope",
    "declared_scope",
    "is_closed",
    "plan_scope",
    "read_json_document",
    "scope_ids_of",
    "status_of",
]

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


@dataclass(frozen=True, kw_only=True)
class PlanScope:
    """A plan's DECLARED scope, and the part of it the ledger does not show closed.

    An EMPTY `ids` means the plan declares no scope this module can read, which is
    not the same as declaring an empty one — see `declared_scope`.
    """

    ids: tuple[str, ...]
    open_ids: tuple[str, ...]


def status_of(*, item: Item) -> str:
    value: Any = item.get("status")
    return value.strip().lower() if isinstance(value, str) else ""


def is_closed(*, item: Item) -> bool:
    return status_of(item=item) in CLOSED_STATUSES


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
