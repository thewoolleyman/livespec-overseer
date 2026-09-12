"""The append-only, idempotent, secret-free audit log.

SPECIFICATION/contracts.md requires that every provisionable-token SecretStore mutation
FIRST append a local audit entry naming the record, actor, attempted operation and time
WITHOUT a secret value; that the log be append-only, so an existing entry is never
rewritten or removed; and that a credential-store mutation be attempted only after its
required append SUCCEEDS. If the append fails, the store mutation MUST NOT be attempted.

The append itself is idempotent by `effect_id`: before appending, the writer scans the
validated file, and EXACTLY ONE existing entry whose `version`, `record_id`, `effect_id`,
`actor` and `operation` equal the pending append counts as the completed append without
adding a line — REGARDLESS of that first attempt's stored `attempted_at`. Ignoring the
stored time is the load-bearing detail: a retry after an unknown outcome cannot reproduce
the original attempt instant, so comparing it would make every retry append a second line
and turn the idempotency scan into a duplicate generator. A mismatching or duplicate
occurrence is `store-unavailable`.

WHAT THE LOG ATTESTS IS NARROWER THAN IT LOOKS, and the contract says so: audit entries
attest adapter calls that are ACTUALLY ATTEMPTED, while the provisionable-token store
remains authoritative for whether an attempt COMMITTED. So a reader must not infer a
committed mutation from an audit line, and a definitively-uncommitted mutation
deliberately LEAVES its entry behind — the log is append-only, and the attempt did happen.

The replacement is prefix-preserving: prior bytes, then one canonical line and one LF,
staged and renamed. A crash before the rename leaves the prior file byte-identical; a
crash after it exposes the whole new line, never a torn suffix.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import canonical_json_text, parse_canonical_json
from _lpm_localstate import read_local_text, write_local_text
from _lpm_results import ManagerError, internal_bug, store_unavailable
from _lpm_time import is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "AUDIT_ENTRY_MEMBERS",
    "AUDIT_VERSION",
    "AuditAppend",
    "AuditEntry",
    "append_audit_entry",
    "audit_entry_object",
    "read_audit_log",
]

AUDIT_VERSION: Final = 1
AUDIT_ENTRY_MEMBERS: Final = (
    "version",
    "record_id",
    "effect_id",
    "actor",
    "operation",
    "attempted_at",
)
_IDENTITY_MEMBERS: Final = ("version", "record_id", "effect_id", "actor", "operation")


@dataclass(frozen=True, kw_only=True)
class AuditAppend:
    """Whether the append added a line, or found its effect already recorded."""

    appended: bool


@dataclass(frozen=True, kw_only=True)
class AuditEntry:
    """One attempted provisionable-token mutation. Carries no value, ever."""

    record_id: str
    effect_id: str
    actor: str
    operation: str
    attempted_at: str


def audit_entry_object(*, entry: AuditEntry) -> dict[str, object]:
    """The exact six-member mapping; built from the declared list, so nothing leaks in."""
    values: dict[str, object] = {"version": AUDIT_VERSION}
    for member in AUDIT_ENTRY_MEMBERS[1:]:
        values[member] = getattr(entry, member)
    return values


def read_audit_log(*, path: Path, owner_uid: int) -> Result[tuple[AuditEntry, ...], ManagerError]:
    """Read and validate the whole log; an absent file is an empty history."""
    lines = _validated_lines(path=path, owner_uid=owner_uid)
    if isinstance(lines, Failure):
        return lines
    return Success(tuple(entry for entry, _ in lines.unwrap()))


def append_audit_entry(
    *, path: Path, entry: AuditEntry, owner_uid: int
) -> Result[AuditAppend, ManagerError]:
    """Append `entry` unless its effect is already recorded.

    `appended` is false when exactly one matching entry was already present — the
    completed-append case, which is a no-op rather than a failure.
    """
    prepared = _prepared_line(entry=entry)
    if isinstance(prepared, Failure):
        return prepared
    existing = _validated_lines(path=path, owner_uid=owner_uid)
    if isinstance(existing, Failure):
        return existing
    stored = existing.unwrap()
    completed = _completed_append(stored=stored, entry=entry)
    if isinstance(completed, Failure):
        return completed
    already = completed.unwrap()
    if already is not None:
        return Success(already)
    prefix = "".join(f"{line}\n" for _, line in stored)
    written = write_local_text(
        path=path, text=f"{prefix}{prepared.unwrap()}\n", owner_uid=owner_uid
    )
    if isinstance(written, Failure):
        return written
    return Success(AuditAppend(appended=True))


def _prepared_line(*, entry: AuditEntry) -> Result[str, ManagerError]:
    if not is_canonical_timestamp(text=entry.attempted_at):
        return Failure(internal_bug(message="attempted_at must be a UTC RFC 3339-second timestamp"))
    # Every member of the entry object is a string or the integer version, so the encoder
    # has no refusal to report here; an unwrap failure would be a bug in the encoder rather
    # than an operator-visible condition, and belongs on the bug rail.
    return Success(canonical_json_text(value=audit_entry_object(entry=entry)).unwrap())


def _completed_append(
    *, stored: list[tuple[AuditEntry, str]], entry: AuditEntry
) -> Result[AuditAppend | None, ManagerError]:
    matches = [recorded for recorded, _ in stored if _same_effect(left=recorded, right=entry)]
    if len(matches) > 1:
        return Failure(store_unavailable(message="audit log records this effect more than once"))
    if matches:
        return Success(AuditAppend(appended=False))
    conflicting = [recorded for recorded, _ in stored if recorded.effect_id == entry.effect_id]
    if conflicting:
        return Failure(store_unavailable(message="audit log records this effect_id differently"))
    return Success(None)


def _validated_lines(
    *, path: Path, owner_uid: int
) -> Result[list[tuple[AuditEntry, str]], ManagerError]:
    raw = read_local_text(path=path, owner_uid=owner_uid)
    if isinstance(raw, Failure):
        return raw
    text = raw.unwrap()
    if text is None:
        return Success([])
    entries: list[tuple[AuditEntry, str]] = []
    for line in text.splitlines():
        parsed = parse_canonical_json(text=line)
        if isinstance(parsed, Failure):
            return Failure(
                store_unavailable(message=f"audit log line is {parsed.failure().reason}")
            )
        entry = _entry_from_object(parsed=parsed.unwrap())
        if isinstance(entry, Failure):
            return entry
        entries.append((entry.unwrap(), line))
    return Success(entries)


def _entry_from_object(*, parsed: object) -> Result[AuditEntry, ManagerError]:
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="audit log line is not a JSON object"))
    source = cast("dict[str, object]", parsed)
    if sorted(source) != sorted(AUDIT_ENTRY_MEMBERS):
        return Failure(store_unavailable(message="audit log line has the wrong members"))
    version = source["version"]
    if isinstance(version, bool) or version != AUDIT_VERSION:
        return Failure(store_unavailable(message="audit log line version must be the integer 1"))
    values: dict[str, str] = {}
    for member in AUDIT_ENTRY_MEMBERS[1:]:
        value = source[member]
        if not isinstance(value, str) or value == "":
            return Failure(store_unavailable(message=f"audit log {member} must be non-empty"))
        values[member] = value
    return Success(
        AuditEntry(
            record_id=values["record_id"],
            effect_id=values["effect_id"],
            actor=values["actor"],
            operation=values["operation"],
            attempted_at=values["attempted_at"],
        )
    )


def _same_effect(*, left: AuditEntry, right: AuditEntry) -> bool:
    # `attempted_at` is deliberately excluded: a retry after an unknown outcome cannot
    # reproduce the original attempt instant, and comparing it would append a second line
    # for the same effect every time.
    return all(
        getattr(left, member) == getattr(right, member)
        for member in _IDENTITY_MEMBERS
        if member != "version"
    )
