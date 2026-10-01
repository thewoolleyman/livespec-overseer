"""The coexistence-proof record's shape, and the one standalone relation every reader needs.

SPECIFICATION/contracts.md states the proof record at `<manager-state>/coexistence-proof.json` as
containing EXACTLY `version`, nullable `rollout_started_at`, `successful_consumer_dates`,
`completion_markers`, nullable `soak_started_at`, nullable `simultaneous_spread`, nullable
`production_success`, nullable `legacy_pool_absence_success` and nullable `last_auth_failure_at`;
fixes the initial object an ABSENT file means; and requires that when `rollout_started_at` is null
every other nullable field be null and both arrays be empty.

THE ABSENT-FILE DEFAULT IS A VALUE, NOT AN ERROR, and that is load-bearing in the one direction
that matters. Absence means the rollout has not started, so every governance Boolean derived from
this record is false — which is the SAFE answer. A reader that treated absence as unreadable would
block provisioning on a file that is legitimately not there yet; a reader that treated an
unreadable file as absent would report "rollout not started" about a record it could not read, and
`deprecation_ready` is computed from exactly these fields. The two are kept apart here.

RECORD VALIDITY MUST NOT DEPEND ON THE READER'S CURRENT CLOCK, which the contract states outright:
a later BACKWARD wall-clock step must not make previously accepted evidence malformed. So nothing
in this module compares a stored instant against `now`, and the relations it does enforce are
internal — between stored fields only.

WHAT THIS MODULE DELIBERATELY DOES NOT DERIVE. The dated-soak progression, `simultaneous_spread`
eligibility and the seven-day completion rule are the SEPARATE plan child this work item names
("browser acquisition and seven-day proof remain separate plan children"). Their fields are
validated STRUCTURALLY here so a record carrying them round-trips and so the run-scoped effects can
merge beside them without destroying them — but the rules that WRITE them are not implemented, and
no caller should read this module as asserting they are.
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
    "COMPLETION_MARKER_MEMBERS",
    "PROOF_MEMBERS",
    "PROOF_VERSION",
    "CompletionMarker",
    "ProofRecord",
    "initial_proof_record",
    "proof_from_object",
    "proof_object",
    "read_proof_record",
]

PROOF_VERSION: Final = 1

PROOF_MEMBERS: Final = (
    "version",
    "rollout_started_at",
    "successful_consumer_dates",
    "completion_markers",
    "soak_started_at",
    "simultaneous_spread",
    "production_success",
    "legacy_pool_absence_success",
    "last_auth_failure_at",
)
COMPLETION_MARKER_MEMBERS: Final = ("consumer_run_id", "record_id", "completed_at")

_NULLABLE_TIMES: Final = ("rollout_started_at", "soak_started_at", "last_auth_failure_at")
_NULLABLE_OBJECTS: Final = (
    "simultaneous_spread",
    "production_success",
    "legacy_pool_absence_success",
)
_DATE_LENGTH: Final = 10


@dataclass(frozen=True, kw_only=True)
class CompletionMarker:
    """One qualifying completion's contribution identity and the instant it completed."""

    consumer_run_id: str
    record_id: str
    completed_at: str


@dataclass(frozen=True, kw_only=True)
class ProofRecord:
    """The coexistence-proof record. Carries no credential and no diagnostic, ever."""

    rollout_started_at: str | None
    successful_consumer_dates: tuple[str, ...] = ()
    completion_markers: tuple[CompletionMarker, ...] = ()
    soak_started_at: str | None = None
    simultaneous_spread: dict[str, object] | None = None
    production_success: dict[str, object] | None = None
    legacy_pool_absence_success: dict[str, object] | None = None
    last_auth_failure_at: str | None = None


def initial_proof_record() -> ProofRecord:
    """The object an ABSENT proof file MEANS: a rollout that has not started."""
    return ProofRecord(rollout_started_at=None)


def proof_object(*, proof: ProofRecord) -> dict[str, object]:
    """The exact nine-member mapping, built from the declared member list."""
    values: dict[str, object] = {"version": PROOF_VERSION}
    for member in PROOF_MEMBERS[1:]:
        values[member] = getattr(proof, member)
    values["successful_consumer_dates"] = list(proof.successful_consumer_dates)
    values["completion_markers"] = [
        {
            "consumer_run_id": marker.consumer_run_id,
            "record_id": marker.record_id,
            "completed_at": marker.completed_at,
        }
        for marker in proof.completion_markers
    ]
    return values


def read_proof_record(*, path: Path, owner_uid: int) -> Result[ProofRecord, ManagerError]:
    """Read the proof record; an ABSENT file is the initial object, not a refusal.

    An unreadable file is a refusal, though — and never the initial object. Reporting "rollout not
    started" about a record nobody could read would answer a governance question from an absence of
    evidence rather than from evidence of absence.
    """
    stored = read_local_record(path=path, owner_uid=owner_uid)
    if isinstance(stored, Failure):
        return stored
    parsed = stored.unwrap()
    if parsed is None:
        return Success(initial_proof_record())
    return proof_from_object(parsed=parsed)


def proof_from_object(*, parsed: object) -> Result[ProofRecord, ManagerError]:
    """Validate one decoded proof record against its shape and its internal relations."""
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="the proof record must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    for inspect in (_membership_defect, _typed_defect, _rollout_defect):
        reason = inspect(source=source)
        if reason is not None:
            return Failure(store_unavailable(message=reason))
    markers = _markers(source=source)
    if isinstance(markers, Failure):
        return markers
    return Success(
        ProofRecord(
            rollout_started_at=_optional_text(value=source["rollout_started_at"]),
            successful_consumer_dates=tuple(
                str(date) for date in cast("list[object]", source["successful_consumer_dates"])
            ),
            completion_markers=markers.unwrap(),
            soak_started_at=_optional_text(value=source["soak_started_at"]),
            simultaneous_spread=_optional_object(value=source["simultaneous_spread"]),
            production_success=_optional_object(value=source["production_success"]),
            legacy_pool_absence_success=_optional_object(
                value=source["legacy_pool_absence_success"]
            ),
            last_auth_failure_at=_optional_text(value=source["last_auth_failure_at"]),
        )
    )


def _membership_defect(*, source: dict[str, object]) -> str | None:
    missing = [member for member in PROOF_MEMBERS if member not in source]
    if missing:
        return f"the proof record is missing {missing[0]}"
    extra = sorted(set(source) - set(PROOF_MEMBERS))
    if extra:
        return f"the proof record has extra member {extra[0]}"
    version = source["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != PROOF_VERSION:
        return "the proof record version must be the integer 1"
    return None


def _typed_defect(*, source: dict[str, object]) -> str | None:
    for member in _NULLABLE_TIMES:
        value = source[member]
        if value is not None and (
            not isinstance(value, str) or not is_canonical_timestamp(text=value)
        ):
            return f"a proof {member} must be null or a UTC RFC 3339-second timestamp"
    for member in _NULLABLE_OBJECTS:
        value = source[member]
        if value is not None and not isinstance(value, dict):
            return f"a proof {member} must be null or a JSON object"
    dates = source["successful_consumer_dates"]
    if not isinstance(dates, list):
        return "proof successful_consumer_dates must be an array"
    for date in cast("list[object]", dates):
        if not isinstance(date, str) or len(date) != _DATE_LENGTH:
            return "each proof successful_consumer_date must be a YYYY-MM-DD string"
    if not isinstance(source["completion_markers"], list):
        return "proof completion_markers must be an array"
    return None


def _rollout_defect(*, source: dict[str, object]) -> str | None:
    if source["rollout_started_at"] is not None:
        return None
    for member in PROOF_MEMBERS[4:]:
        if source[member] is not None:
            return f"a proof record with no rollout must have a null {member}"
    if cast("list[object]", source["successful_consumer_dates"]) != []:
        return "a proof record with no rollout must have empty successful_consumer_dates"
    if cast("list[object]", source["completion_markers"]) != []:
        return "a proof record with no rollout must have empty completion_markers"
    return None


def _markers(*, source: dict[str, object]) -> Result[tuple[CompletionMarker, ...], ManagerError]:
    collected: list[CompletionMarker] = []
    for entry in cast("list[object]", source["completion_markers"]):
        marker = _marker_from_object(parsed=entry)
        if isinstance(marker, Failure):
            return marker
        identity = (marker.unwrap().consumer_run_id, marker.unwrap().record_id)
        if identity in [(held.consumer_run_id, held.record_id) for held in collected]:
            return Failure(
                store_unavailable(message="proof completion_markers must be unique by identity")
            )
        collected.append(marker.unwrap())
    return Success(tuple(collected))


def _marker_from_object(*, parsed: object) -> Result[CompletionMarker, ManagerError]:
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="a completion marker must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    if sorted(source) != sorted(COMPLETION_MARKER_MEMBERS):
        return Failure(
            store_unavailable(
                message=(
                    "a completion marker must contain exactly "
                    f"{', '.join(COMPLETION_MARKER_MEMBERS)}"
                )
            )
        )
    run_id = source["consumer_run_id"]
    if not isinstance(run_id, str) or run_id == "":
        return Failure(
            store_unavailable(message="a completion marker consumer_run_id must be non-empty")
        )
    record_id = source["record_id"]
    if not isinstance(record_id, str) or not is_uuid4(value=record_id):
        return Failure(
            store_unavailable(message="a completion marker record_id must be a lowercase UUIDv4")
        )
    completed_at = source["completed_at"]
    if not isinstance(completed_at, str) or not is_canonical_timestamp(text=completed_at):
        return Failure(
            store_unavailable(message="a completion marker completed_at must be canonical")
        )
    return Success(
        CompletionMarker(consumer_run_id=run_id, record_id=record_id, completed_at=completed_at)
    )


def _optional_text(*, value: object) -> str | None:
    return None if value is None else str(value)


def _optional_object(*, value: object) -> dict[str, object] | None:
    return None if value is None else cast("dict[str, object]", value)
