"""Write-side validation for the durable mapping store.

SPECIFICATION/contracts.md states mapping-store validation as a predicate on the
WRITE — the row as it stands before, together with the row as it would stand
after — and NOT on the resulting row alone. That framing is load-bearing rather
than stylistic: a rewrite that STRIPS a recorded ``epic`` yields a row
indistinguishable from a conforming never-assigned one, so a row-only predicate
cannot refuse it and the rule would protect nothing.

Three consequences shape everything below.

The predicate judges only the row a write INTRODUCES OR CHANGES, and only for a
non-conformance that write itself introduces. A row carried along unchanged is
never judged, so a pre-existing non-conforming row can never block unrelated
maintenance of the store; such a row is SURFACED instead of being silently
rewritten or silently dropped.

An ABSENT ``epic`` CONFORMS, and a write introducing such a row is accepted: the
REQUIRED-for-restart sentence in the durable-key contract is a precondition for
RESTARTING a track, never for WRITING its row. A row carrying a persisted
read-time placeholder is treated exactly as a row with no recorded ``epic``, per
the same contract, so it is neither an epic to remove nor one to replace — and,
for the same reason, a write may not INTRODUCE one: the placeholder is a read-time
projection, and absent and recorded are the only two persisted states.

Removing a ROW ENTIRELY is not removing its ``epic``, so the garbage collection
of rows whose plan has been archived or deleted is never refused on that ground.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

import jsonio
from _registry_core import norm
from _registry_store_rows import validated_row
from _registry_track_variants import epic_is_resolved

__all__: list[str] = [
    "MappingWriteRefusal",
    "MappingWriteVerdict",
    "is_ledger_epic_id",
    "persisted_projection",
    "recorded_epic",
    "store_rows_before_write",
    "validate_mapping_write",
]

RowIdentity: TypeAlias = tuple[str, str]

# The ledger epic id shape this package already recognises when it reads a plan's
# write-once anchor (`_registry_epic._LEDGER_ANCHOR`), widened only to the mixed
# case an operator can type on `overseer add --epic`. It admits no path
# separator, whitespace, or colon, so neither a path-shaped legacy locator nor a
# persisted read-time placeholder can pass for an id.
_LEDGER_EPIC_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*(?:\.[0-9]+)*")
_MISSING_PREFIX = "missing_"
_PROJECTION_REASON = (
    "a write may not persist the read-time placeholder substituted for an absent "
    "epic; absent and recorded are the only two persisted states"
)


@dataclass(frozen=True, kw_only=True)
class MappingWriteRefusal:
    repo: str
    topic: str
    key: str
    reason: str

    @property
    def message(self) -> str:
        return (
            f"refusing mapping-store write for {self.repo}::{self.topic}: "
            f"offending key {self.key}: {self.reason}"
        )


@dataclass(frozen=True, kw_only=True)
class MappingWriteVerdict:
    refusal: MappingWriteRefusal | None
    carried_warnings: tuple[str, ...]


def is_ledger_epic_id(*, value: str) -> bool:
    """Whether ``value`` has the shape of a plan's ledger epic id."""
    return _LEDGER_EPIC_ID.fullmatch(value) is not None


def persisted_projection(*, row: dict[str, object]) -> bool:
    """Whether the row's stored ``epic`` is a persisted read-time placeholder.

    That state is not a third persisted state the store may hold: a write must not
    introduce it, and a row already carrying one has no recorded epic at all.
    """
    value = row.get("epic")
    return isinstance(value, str) and bool(value) and not epic_is_resolved(epic=value)


def recorded_epic(*, row: dict[str, object]) -> str | None:
    """The row's RECORDED epic, or None when it has none.

    A persisted read-time placeholder is NOT a recorded epic: the durable-key
    contract requires a row already carrying one to be treated exactly as a row
    with no recorded ``epic``, so a write can neither remove nor replace it.
    """
    value = row.get("epic")
    if not isinstance(value, str) or not value:
        return None
    return value if epic_is_resolved(epic=value) else None


def store_rows_before_write(*, path: Path) -> list[dict[str, object]]:
    """The store's current object rows, read SILENTLY as the write's pre-image.

    Deliberately quiet where :func:`_registry_rows_io.read_row_records` warns: the
    read-side rule and this write-side rule govern different failures, and the
    caller has already read (and named) any malformed line. An unparseable line is
    not a row, so it is neither a pre-image for a write nor a row a write removes.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):  # absent store, unreadable store, non-UTF-8 store
        return []
    rows: list[dict[str, object]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        record = jsonio.as_object(value=obj)
        if record is not None:
            rows.append(record)
    return rows


def _identity(*, row: dict[str, object]) -> RowIdentity | None:
    repo = row.get("repo")
    topic = row.get("topic")
    if not isinstance(repo, str) or not isinstance(topic, str):
        return None
    return (norm(repo=repo), topic)


def _by_identity(
    *, rows: list[dict[str, object]]
) -> dict[RowIdentity | None, list[dict[str, object]]]:
    grouped: dict[RowIdentity | None, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(_identity(row=row), []).append(row)
    return grouped


def _labels(*, row: dict[str, object]) -> tuple[str, str]:
    repo = row.get("repo")
    topic = row.get("topic")
    return (
        repo if isinstance(repo, str) else "?",
        topic if isinstance(topic, str) else "?",
    )


def _offending_key(*, reason: str) -> str:
    """Name the durable key a row-parse ValueError is about.

    Every reason ``track_from_mapping_row`` raises is either ``missing_<key>`` or
    ``unknown_kind:<kind>``, so the two arms are exhaustive over its vocabulary.
    """
    if reason.startswith(_MISSING_PREFIX):
        return reason[len(_MISSING_PREFIX) :]
    return "kind"


def _row_violations(*, row: dict[str, object]) -> frozenset[str]:
    """Durable-key contract violations of one row, named by offending key."""
    violations: set[str] = set()
    try:
        _ = validated_row(row=row)
    except ValueError as exc:
        violations.add(_offending_key(reason=str(exc)))
    if persisted_projection(row=row):
        violations.add("epic")
    epic = recorded_epic(row=row)
    if epic is not None and not is_ledger_epic_id(value=epic):
        violations.add("epic")
    return frozenset(violations)


def _introduced_reason(*, row: dict[str, object], key: str) -> str:
    if key == "epic" and persisted_projection(row=row):
        return _PROJECTION_REASON
    return f"the written row does not satisfy the durable-key contract for {key}"


def _epic_transition_refusal(
    *, before: dict[str, object], after: dict[str, object], repo: str, topic: str
) -> MappingWriteRefusal | None:
    was = recorded_epic(row=before)
    if was is None:
        return None
    now = recorded_epic(row=after)
    if now == was:
        return None
    reason = (
        f"a write may not remove the recorded epic {was!r}"
        if now is None
        else f"a write may not replace the recorded epic {was!r} with {now!r}"
    )
    return MappingWriteRefusal(repo=repo, topic=topic, key="epic", reason=reason)


def _refuse_row(
    *,
    row: dict[str, object],
    identity: RowIdentity | None,
    candidates: list[dict[str, object]],
) -> MappingWriteRefusal | None:
    """Refuse a row this write INTRODUCES or CHANGES, or return None to allow it."""
    pre_image = candidates[0] if identity is not None and candidates else None
    already: frozenset[str] = (
        _row_violations(row=pre_image) if pre_image is not None else frozenset()
    )
    introduced = sorted(_row_violations(row=row) - already)
    repo, topic = _labels(row=row)
    if introduced:
        key = introduced[0]
        return MappingWriteRefusal(
            repo=repo,
            topic=topic,
            key=key,
            reason=_introduced_reason(row=row, key=key),
        )
    if pre_image is None:
        return None
    return _epic_transition_refusal(before=pre_image, after=row, repo=repo, topic=topic)


def _carried_warning(*, row: dict[str, object]) -> str | None:
    violations = sorted(_row_violations(row=row))
    if not violations:
        return None
    repo, topic = _labels(row=row)
    return (
        f"carrying non-conforming mapping row {repo}::{topic} unchanged; "
        f"offending key(s) {', '.join(violations)}"
    )


def validate_mapping_write(
    *,
    before: list[dict[str, object]],
    after: list[dict[str, object]],
) -> MappingWriteVerdict:
    """Judge a whole store write: what it introduces, changes, and carries along."""
    prior = _by_identity(rows=before)
    refusals: list[MappingWriteRefusal] = []
    carried: list[str] = []
    for row in after:
        identity = _identity(row=row)
        candidates = prior.get(identity, [])
        if row in candidates:
            warning = _carried_warning(row=row)
            if warning is not None:
                carried.append(warning)
            continue
        refusal = _refuse_row(row=row, identity=identity, candidates=candidates)
        if refusal is not None:
            refusals.append(refusal)
    return MappingWriteVerdict(
        refusal=refusals[0] if refusals else None,
        carried_warnings=tuple(carried),
    )
