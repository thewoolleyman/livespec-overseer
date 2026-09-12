"""The canonical, secret-free credential record and its ratified invariants.

SPECIFICATION/contracts.md states the provisionable record as EXACTLY twelve members —
`version`, the five immutable identity fields, `acquired_at`, nullable `expires_at` and
`last_validated`, one lifecycle `status`, nullable `value_generation`, nullable `value_ref`
and nullable `previous_value_ref` — and requires that once the metadata envelope has
parsed, a record with a missing or extra member, wrong field type or value, identity
conflict, lifecycle inconsistency or invalid generation/reference relation be INELIGIBLE
with a secret-free diagnostic, WITHOUT preventing another valid record from satisfying the
request.

That last clause is why a defect here is a `RecordDefect` rather than a manager error: one
corrupt record must not become a command-level failure that hides every healthy record
behind it. The caller decides what an ineligible record means for the request it is
serving.

THE RAW CREDENTIAL IS NOT IN THIS SHAPE, and that is the point. At rest within manager
stores raw credential bytes live behind `value_ref`; the record carries only the
REFERENCE. Serialization is therefore built from the declared field list rather than from
an arbitrary mapping, so there is no path by which a caller's extra key — a captured
token, a probe response — reaches a stored record, an audit entry or an output.

FRESHNESS BOUNDARIES ARE EXCLUSIVE OF SELECTION AND INCLUSIVE OF EXPIRY. A record is
age-stale when `last_validated` is null or the captured time is AT or after
`last_validated` plus the configured maximum age, and expired when `expires_at` is
non-null and the captured time is AT or after it. At either equality instant the record is
NOT selectable — the contract's own scenario pins exactly that pair of equalities, because
"just barely still valid" is the case a `>` would silently admit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_time import add_seconds, is_at_or_after, is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ACTIVE_STATUSES",
    "CREDENTIAL_STATUSES",
    "IDENTITY_FIELDS",
    "RECORD_MEMBERS",
    "RECORD_VERSION",
    "CredentialRecord",
    "RecordDefect",
    "credential_record_from_object",
    "identity_conflict",
    "is_age_stale",
    "is_expired",
    "is_selectable",
    "is_uuid4",
    "record_object",
]

RECORD_VERSION: Final = 1

CREDENTIAL_STATUSES: Final = (
    "acquiring",
    "valid",
    "suspect",
    "revalidating",
    "dead",
    "reacquiring",
)
ACTIVE_STATUSES: Final = ("acquiring", "reacquiring", "revalidating")
_VALUE_BEARING_STATUSES: Final = ("valid", "suspect", "revalidating")

IDENTITY_FIELDS: Final = ("record_id", "provider", "account_id", "kind", "purpose")
RECORD_MEMBERS: Final = (
    "version",
    "record_id",
    "provider",
    "account_id",
    "kind",
    "purpose",
    "status",
    "acquired_at",
    "expires_at",
    "last_validated",
    "value_generation",
    "value_ref",
    "previous_value_ref",
)

_UUID4 = re.compile(r"\A[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")


@dataclass(frozen=True, kw_only=True)
class RecordDefect:
    """A secret-free reason one record is ineligible; never a command-level failure."""

    reason: str


@dataclass(frozen=True, kw_only=True)
class CredentialRecord:
    """One provisionable credential record. Carries a REFERENCE, never a value."""

    record_id: str
    provider: str
    account_id: str
    kind: str
    purpose: str
    status: str
    acquired_at: str
    expires_at: str | None
    last_validated: str | None
    value_generation: str | None
    value_ref: str | None
    previous_value_ref: str | None


def is_uuid4(*, value: str) -> bool:
    """Whether `value` is a LOWERCASE RFC 4122 UUIDv4, the only accepted spelling."""
    return _UUID4.match(value) is not None


def record_object(*, record: CredentialRecord) -> dict[str, object]:
    """The exact canonical member mapping for `record`.

    Built from the declared member list, so a serialized record cannot acquire a
    thirteenth member from anywhere.
    """
    values: dict[str, object] = {"version": RECORD_VERSION}
    for member in RECORD_MEMBERS[1:]:
        values[member] = getattr(record, member)
    return values


def credential_record_from_object(*, parsed: object) -> Result[CredentialRecord, RecordDefect]:
    """Validate one decoded `record` value against every invariant this layer owns."""
    if not isinstance(parsed, dict):
        return Failure(RecordDefect(reason="credential record must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    membership = _membership_defect(source=source)
    if membership is not None:
        return Failure(membership)
    fields = _typed_defect(source=source)
    if fields is not None:
        return Failure(fields)
    record = CredentialRecord(
        record_id=str(source["record_id"]),
        provider=str(source["provider"]),
        account_id=str(source["account_id"]),
        kind=str(source["kind"]),
        purpose=str(source["purpose"]),
        status=str(source["status"]),
        acquired_at=str(source["acquired_at"]),
        expires_at=_optional_text(value=source["expires_at"]),
        last_validated=_optional_text(value=source["last_validated"]),
        value_generation=_optional_text(value=source["value_generation"]),
        value_ref=_optional_text(value=source["value_ref"]),
        previous_value_ref=_optional_text(value=source["previous_value_ref"]),
    )
    relation = _relation_defect(record=record)
    if relation is not None:
        return Failure(relation)
    return Success(record)


def identity_conflict(*, before: CredentialRecord, after: CredentialRecord) -> bool:
    """Whether `after` changes any of the five immutable identity fields of `before`.

    Identity is immutable for a given `record_id` across acquisition replacement AND
    lifecycle writes, so this is asked of every conditional replacement rather than only
    of the ones that look like they might move an account.
    """
    return any(getattr(before, field) != getattr(after, field) for field in IDENTITY_FIELDS)


def is_expired(*, record: CredentialRecord, now: str) -> bool:
    """Whether `now` is AT or after a non-null `expires_at`. Equality is expired."""
    if record.expires_at is None:
        return False
    return is_at_or_after(moment=now, limit=record.expires_at) is True


def is_age_stale(
    *, record: CredentialRecord, now: str, maximum_validation_age_seconds: int
) -> bool:
    """Whether `record` has no validation time, or one at or past the configured age."""
    if record.last_validated is None:
        return True
    limit = add_seconds(timestamp=record.last_validated, seconds=maximum_validation_age_seconds)
    if limit is None:
        return True
    return is_at_or_after(moment=now, limit=limit) is True


def is_selectable(
    *, record: CredentialRecord, now: str, maximum_validation_age_seconds: int
) -> bool:
    """Only a `valid` record that is neither age-stale nor expired may be selected."""
    if record.status != "valid":
        return False
    if is_expired(record=record, now=now):
        return False
    return not is_age_stale(
        record=record, now=now, maximum_validation_age_seconds=maximum_validation_age_seconds
    )


def _membership_defect(*, source: dict[str, object]) -> RecordDefect | None:
    missing = [member for member in RECORD_MEMBERS if member not in source]
    if missing:
        return RecordDefect(reason=f"credential record is missing {missing[0]}")
    extra = sorted(set(source) - set(RECORD_MEMBERS))
    if extra:
        return RecordDefect(reason=f"credential record has extra member {extra[0]}")
    version = source["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != RECORD_VERSION:
        return RecordDefect(reason="credential record version must be the integer 1")
    return None


def _typed_defect(*, source: dict[str, object]) -> RecordDefect | None:
    record_id = source["record_id"]
    if not isinstance(record_id, str) or not is_uuid4(value=record_id):
        return RecordDefect(reason="record_id must be a lowercase RFC 4122 UUIDv4")
    for member in IDENTITY_FIELDS[1:]:
        value = source[member]
        if not isinstance(value, str) or value == "":
            return RecordDefect(reason=f"{member} must be a non-empty string")
    if source["status"] not in CREDENTIAL_STATUSES:
        return RecordDefect(reason="status must be one ratified lifecycle status")
    return _time_and_reference_defect(source=source)


def _time_and_reference_defect(*, source: dict[str, object]) -> RecordDefect | None:
    acquired_at = source["acquired_at"]
    if not isinstance(acquired_at, str) or not is_canonical_timestamp(text=acquired_at):
        return RecordDefect(reason="acquired_at must be a UTC RFC 3339-second timestamp")
    for member in ("expires_at", "last_validated"):
        value = source[member]
        if value is not None and (
            not isinstance(value, str) or not is_canonical_timestamp(text=value)
        ):
            return RecordDefect(reason=f"{member} must be null or a UTC RFC 3339-second timestamp")
    generation = source["value_generation"]
    if generation is not None and (
        not isinstance(generation, str) or not is_uuid4(value=generation)
    ):
        return RecordDefect(reason="value_generation must be null or a lowercase UUIDv4")
    for member in ("value_ref", "previous_value_ref"):
        value = source[member]
        if value is not None and (not isinstance(value, str) or value == ""):
            return RecordDefect(reason=f"{member} must be null or a non-empty reference")
    return None


def _relation_defect(*, record: CredentialRecord) -> RecordDefect | None:
    paired = (record.value_generation is None) == (record.value_ref is None)
    if not paired:
        return RecordDefect(reason="value_generation and value_ref must both be null or both set")
    if record.status in _VALUE_BEARING_STATUSES and record.value_ref is None:
        return RecordDefect(reason=f"a {record.status} record must carry a value reference")
    if record.status == "valid" and record.last_validated is None:
        return RecordDefect(reason="a valid record must carry a non-null last_validated")
    if record.previous_value_ref is not None and record.value_ref is None:
        return RecordDefect(reason="previous_value_ref cannot outlive its value_ref")
    return None


def _optional_text(*, value: object) -> str | None:
    return None if value is None else str(value)
