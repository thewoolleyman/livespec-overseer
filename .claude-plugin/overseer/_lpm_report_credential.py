"""The authoritative read a report's credential effect and its paired audit both decide from.

SPECIFICATION/contracts.md makes a report's lifecycle move "a compare-and-set conditioned on the
matching assignment or tombstone's stored `value_generation` still equaling the record's current
`value_generation`, including when resumed from a write-ahead record", transitions a current
`valid` or `revalidating` record to `suspect` when that comparison succeeds, and makes BOTH
`audit-append` and `credential-conditional-set` completed no-ops for an already `suspect`, `dead`
or `reacquiring` record, for a differing value generation, and for the `unknown` classification.

ONE DECISION SERVES BOTH POSITIONS, WHICH IS WHY IT LIVES HERE RATHER THAN IN EITHER EXECUTOR.
The contract pairs them: "The credential effect and its paired audit MUST be completed no-ops"
for the same three conditions. Two executors computing that independently is how an audit line
comes to attest an adapter call nobody made — or how a credential transition lands with no
attempt evidence in front of it, which the append-only audit can never be made to show
afterwards.

THE DECISION IS TAKEN FROM AUTHORITATIVE STATE, NOT FROM AN INPUT. Both the stored generation
and the current lifecycle status are read at the moment the position runs: the assignment or
tombstone supplies the generation this run was bound to, the store supplies the record's current
revision, and `report_effects` is the ratified table over that pair. A composition that handed
the verdict in could not express "the credential was replaced between accepting the report and
replaying this position", which is the case the compare-and-set exists for.

THE STORED MARKERS ARE PASSED IN DELIBERATELY. A report whose exact `(occurred_at,
classification)` pair is ALREADY recorded is the contract's duplicate, and "the stored-marker
duplicate rule prevents every one of those effects from running again" — so a replay that
arrives after `report-marker-update` committed settles both audited positions instead of
re-attempting them. Passing an empty array would hide exactly that case.

THE REVISION NUMBER COMES FROM THE ENVELOPE'S OWN TITLE. A fenced create must name revision
`n + 1`, and `n` is carried nowhere else: the record's fields do not hold it. An envelope whose
title names no revision of this record is therefore unreadable state rather than a readable
record at an unknown position — the in-memory backend cannot produce one, but a replaceable
backend can, and guessing a revision would make the fence unable to recognize its own commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import parse_canonical_json
from _lpm_closing_records import closing_record
from _lpm_engine_context import EffectContext
from _lpm_fence_recovery import stored_terminal_outcome
from _lpm_operation_plan import writer_role_for
from _lpm_record import CredentialRecord, credential_record_from_object, record_object
from _lpm_reports import FailureReport, report_effects, report_from_object
from _lpm_results import ManagerError, store_unavailable
from _lpm_revisions import revision_of_title
from _lpm_store import SecretStore

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "AuthoritativeRecord",
    "ReportTransition",
    "audited_actor",
    "authoritative_record",
    "report_transition",
]


@dataclass(frozen=True, kw_only=True)
class AuthoritativeRecord:
    """One credential's current logical revision, as the store itself can be read to hold it."""

    record: dict[str, object]
    status: str
    value_generation: str | None
    revision: int


@dataclass(frozen=True, kw_only=True)
class ReportTransition:
    """The one fenced revision a report's credential effect is authorized to append."""

    record_id: str
    expected_record: dict[str, object]
    desired_record: dict[str, object]
    revision: int


def audited_actor(*, context: EffectContext) -> Result[str, ManagerError]:
    """The semantic audit actor that owns this position's audited credential effect."""
    return writer_role_for(
        command=context.operation.command,
        phase=context.operation.phase,
        effect=context.position.effect,
        outcome=stored_terminal_outcome(operation=context.operation),
    )


def authoritative_record(
    *, store: SecretStore, record_id: str
) -> Result[AuthoritativeRecord | None, ManagerError]:
    """Reread `record_id`'s complete revision chain, bypassing every cache by construction."""
    result = store.metadata_get(record_id=record_id)
    if result.get("status") != "ok":
        return Failure(
            store_unavailable(
                message="this credential's authoritative revision chain is unreadable"
            )
        )
    item = result.get("item")
    if item is None:
        return Success(None)
    envelope = cast("dict[str, object]", item) if isinstance(item, dict) else {}
    revision = revision_of_title(record_id=record_id, title=_text(value=envelope.get("item_id")))
    if revision is None:
        return Failure(
            store_unavailable(message="the authoritative envelope names no revision of this record")
        )
    parsed = parse_canonical_json(text=_text(value=envelope.get("record")))
    if isinstance(parsed, Failure):
        return Failure(
            store_unavailable(message=f"the authoritative record is {parsed.failure().reason}")
        )
    validated = credential_record_from_object(parsed=parsed.unwrap())
    if isinstance(validated, Failure):
        return Failure(
            store_unavailable(
                message=f"the authoritative record is invalid: {validated.failure().reason}"
            )
        )
    return Success(_authoritative(record=validated.unwrap(), revision=revision))


def report_transition(*, context: EffectContext) -> Result[ReportTransition | None, ManagerError]:
    """The revision this report may append, or None for the contract's completed no-op."""
    bound = closing_record(context=context)
    if isinstance(bound, Failure):
        return bound
    reported = report_from_object(parsed=context.operation.normalized_input)
    if isinstance(reported, Failure):
        return reported
    current = _current(context=context, report=reported.unwrap())
    if isinstance(current, Failure):
        return current
    held = current.unwrap()
    effects = report_effects(
        report=reported.unwrap(),
        status=held.status,
        markers=bound.unwrap().report_markers,
        generation_matches=held.value_generation == bound.unwrap().value_generation,
    )
    if isinstance(effects, Failure):
        return effects
    applied = effects.unwrap()
    if applied.duplicate or applied.next_status is None:
        return Success(None)
    return Success(
        ReportTransition(
            record_id=reported.unwrap().record_id,
            expected_record=held.record,
            desired_record={**held.record, "status": applied.next_status},
            revision=held.revision + 1,
        )
    )


def _current(
    *, context: EffectContext, report: FailureReport
) -> Result[AuthoritativeRecord, ManagerError]:
    found = authoritative_record(store=context.engine.store, record_id=report.record_id)
    if isinstance(found, Failure):
        return Failure(found.failure())
    held = found.unwrap()
    if held is None:
        return Failure(
            store_unavailable(message="no authoritative credential record stands for this report")
        )
    return Success(held)


def _authoritative(*, record: CredentialRecord, revision: int) -> AuthoritativeRecord:
    return AuthoritativeRecord(
        record=record_object(record=record),
        status=record.status,
        value_generation=record.value_generation,
        revision=revision,
    )


def _text(*, value: object) -> str:
    return value if isinstance(value, str) else ""
