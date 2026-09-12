"""The durable selection-state record: exact shape, exact order, exact initial value.

SPECIFICATION/contracts.md requires the manager to atomically maintain owner-only
`selection-state.json` containing exactly `version` (integer `1`), `incumbents` and
`last_assignments`; each incumbent entry to carry exactly `provider`, `kind`, `purpose`,
`record_id` and `target_committed_at`, be unique by the three-field key and appear in
LEXICAL ORDER by that tuple; each assignment entry to carry exactly `record_id` and
`assigned_at`, be unique by `record_id` and appear in lexical `record_id` order; an ABSENT
file to mean the initial object; and a malformed, non-regular, symlinked, incorrectly
owned or more broadly accessible file to return `store-unavailable` with exit `4` while
being NEITHER RESET NOR MUTATED.

The ordering requirement is not cosmetic. This file is the durable input to both selection
strategies: `consume-first` reads its incumbent and `spread` orders records by retained
assignment time. Stored in canonical order it has one byte representation per logical
state, so two managers writing the same logical state produce the same bytes and a
delayed post-commit recovery cannot present a re-ordered file as a different state.

The NO-RESET rule matters more here than anywhere else in this layer. Resetting an
unreadable selection state would silently re-open every account this manager has already
committed to a run — the exact overlap the lease rules exist to prevent — while looking
like a successful recovery.

This module owns the RECORD only. Which record a strategy chooses, and when an incumbent
moves, belong to the selection slice; nothing here consults a strategy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_localstate import read_local_record
from _lpm_record import is_uuid4
from _lpm_results import ManagerError, store_unavailable
from _lpm_time import is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "SELECTION_STATE_VERSION",
    "Incumbent",
    "LastAssignment",
    "SelectionState",
    "initial_selection_state",
    "read_selection_state",
    "selection_state_from_object",
    "selection_state_object",
]

SELECTION_STATE_VERSION: Final = 1

_INCUMBENT_MEMBERS: Final = ("provider", "kind", "purpose", "record_id", "target_committed_at")
_ASSIGNMENT_MEMBERS: Final = ("record_id", "assigned_at")


@dataclass(frozen=True, kw_only=True)
class Incumbent:
    """The retained `consume-first` choice for one provider, kind and purpose."""

    provider: str
    kind: str
    purpose: str
    record_id: str
    target_committed_at: str


@dataclass(frozen=True, kw_only=True)
class LastAssignment:
    """The retained assignment time `spread` orders by."""

    record_id: str
    assigned_at: str


@dataclass(frozen=True, kw_only=True)
class SelectionState:
    """The whole durable selection record, already validated and in canonical order."""

    incumbents: tuple[Incumbent, ...]
    last_assignments: tuple[LastAssignment, ...]


def initial_selection_state() -> SelectionState:
    """What an ABSENT file means: version 1, both arrays empty."""
    return SelectionState(incumbents=(), last_assignments=())


def selection_state_object(*, state: SelectionState) -> dict[str, object]:
    """The exact three-member mapping, with both arrays in their declared order."""
    return {
        "version": SELECTION_STATE_VERSION,
        "incumbents": [
            {member: getattr(entry, member) for member in _INCUMBENT_MEMBERS}
            for entry in sorted(
                state.incumbents, key=lambda entry: (entry.provider, entry.kind, entry.purpose)
            )
        ],
        "last_assignments": [
            {member: getattr(entry, member) for member in _ASSIGNMENT_MEMBERS}
            for entry in sorted(state.last_assignments, key=lambda entry: entry.record_id)
        ],
    }


def selection_state_from_object(*, parsed: object) -> Result[SelectionState, ManagerError]:
    """Validate one decoded selection-state value, including its declared ordering."""
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="selection state must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    if sorted(source) != ["incumbents", "last_assignments", "version"]:
        return Failure(store_unavailable(message="selection state has exactly three members"))
    version = source["version"]
    if isinstance(version, bool) or version != SELECTION_STATE_VERSION:
        return Failure(store_unavailable(message="selection state version must be the integer 1"))
    incumbents = _incumbents(value=source["incumbents"])
    if isinstance(incumbents, Failure):
        return incumbents
    assignments = _assignments(value=source["last_assignments"])
    if isinstance(assignments, Failure):
        return assignments
    return Success(
        SelectionState(incumbents=incumbents.unwrap(), last_assignments=assignments.unwrap())
    )


def read_selection_state(*, path: Path, owner_uid: int) -> Result[SelectionState, ManagerError]:
    """Read the selection state; an absent file is the initial object, never a defect."""
    stored = read_local_record(path=path, owner_uid=owner_uid)
    if isinstance(stored, Failure):
        return stored
    value = stored.unwrap()
    if value is None:
        return Success(initial_selection_state())
    return selection_state_from_object(parsed=value)


def _incumbents(*, value: object) -> Result[tuple[Incumbent, ...], ManagerError]:
    rows = _rows(value=value, members=_INCUMBENT_MEMBERS, label="incumbents")
    if isinstance(rows, Failure):
        return rows
    entries: list[Incumbent] = []
    for row in rows.unwrap():
        if not is_canonical_timestamp(text=row["target_committed_at"]):
            return Failure(
                store_unavailable(
                    message="incumbent target_committed_at is not a UTC RFC 3339-second timestamp"
                )
            )
        entries.append(
            Incumbent(
                provider=row["provider"],
                kind=row["kind"],
                purpose=row["purpose"],
                record_id=row["record_id"],
                target_committed_at=row["target_committed_at"],
            )
        )
    keys = [(entry.provider, entry.kind, entry.purpose) for entry in entries]
    if len(set(keys)) != len(keys):
        return Failure(
            store_unavailable(message="incumbents must be unique by provider, kind and purpose")
        )
    if keys != sorted(keys):
        return Failure(store_unavailable(message="incumbents must appear in lexical key order"))
    return Success(tuple(entries))


def _assignments(*, value: object) -> Result[tuple[LastAssignment, ...], ManagerError]:
    rows = _rows(value=value, members=_ASSIGNMENT_MEMBERS, label="last_assignments")
    if isinstance(rows, Failure):
        return rows
    entries = [
        LastAssignment(record_id=row["record_id"], assigned_at=row["assigned_at"])
        for row in rows.unwrap()
    ]
    for entry in entries:
        if not is_canonical_timestamp(text=entry.assigned_at):
            return Failure(
                store_unavailable(message="assigned_at is not a UTC RFC 3339-second timestamp")
            )
    identifiers = [entry.record_id for entry in entries]
    if len(set(identifiers)) != len(identifiers):
        return Failure(store_unavailable(message="last_assignments must be unique by record_id"))
    if identifiers != sorted(identifiers):
        return Failure(
            store_unavailable(message="last_assignments must appear in lexical record_id order")
        )
    return Success(tuple(entries))


def _rows(
    *, value: object, members: tuple[str, ...], label: str
) -> Result[list[dict[str, str]], ManagerError]:
    if not isinstance(value, list):
        return Failure(store_unavailable(message=f"{label} must be an array"))
    rows: list[dict[str, str]] = []
    for entry in cast("list[object]", value):
        if not isinstance(entry, dict):
            return Failure(store_unavailable(message=f"{label} entries must be objects"))
        row = cast("dict[str, object]", entry)
        if sorted(row) != sorted(members):
            return Failure(
                store_unavailable(message=f"{label} entries carry exactly {', '.join(members)}")
            )
        typed: dict[str, str] = {}
        for member in members:
            member_value = row[member]
            if not isinstance(member_value, str) or member_value == "":
                return Failure(
                    store_unavailable(message=f"{label} {member} must be a non-empty string")
                )
            typed[member] = member_value
        if not is_uuid4(value=typed["record_id"]):
            return Failure(
                store_unavailable(message=f"{label} record_id must be a lowercase UUIDv4")
            )
        rows.append(typed)
    return Success(rows)
