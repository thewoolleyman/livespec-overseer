"""Legacy `CLAUDE_CODE_OAUTH_TOKEN` migration: enumerate, validate, record, report the gap.

SPECIFICATION/spec.md defines the LEGACY CREDENTIAL POOL as the manually maintained
`CLAUDE_CODE_OAUTH_TOKEN*` entries in the factory consumer's credential environment, and
makes its documented ABSENCE — attested by a production consumer — one of the four proofs
that must complete before `caam-anthropic-loop` may be deprecated. Bringing that pool under
manager control is what makes such an attestation possible at all, so this module reads the
legacy slots, validates each through the registered Anthropic probe, and writes a schema
record for every candidate the provider actually accepts.

ENUMERATION IS INJECTED, AND THAT IS THE HERMETIC BOUNDARY. Nothing here reads the process
environment, a 1Password vault or any other live store. A `LegacyTokenSource` supplies the
slot names, the account each slot is believed to hold and the value — so a test drives the
whole migration from fabricated slots, and the real source is a separately-reviewed adapter.
A module that reached for `os.environ` itself would be untestable for exactly the cases that
matter and would read real credentials during a routine test run.

IT DELETES NOTHING. A migration that removed a legacy entry as it wrote the replacement
would destroy the only surviving copy the moment a later step failed, and the legacy-pool
absence proof is an attestation the CONSUMER makes about its own environment rather than
something this tooling may manufacture by deletion. Retiring the pool is a separate act.

NO TOKEN VALUE CROSSES THE REPORT BOUNDARY. Slots are reported by NAME and accounts by
IDENTITY; a rejected or inconclusive candidate names its slot and says nothing else. This is
the discipline `_lpm_results` fixes for failures, applied to a tool whose entire input is
secrets — the report is designed so printing it in full is always safe.

THE FIVE DISPOSITIONS ARE NOT FOUR WITH A REMAINDER, AND THE LAST TWO ARE THE POINT. A slot
the provider REFUSED and a slot whose probe was INCONCLUSIVE differ exactly as spec.md says
they do: one is evidence about the credential, the other is evidence about nothing. A slot
nobody can attribute to an account cannot be written at all, and a slot that validated but
did not commit is a store problem standing between a good credential and its record. Merging
any pair of those would report a migration as more complete than it is.

A MISSING ACCOUNT IS A FINDING, NOT A FAILURE. The expected roster minus the accounts that
produced a record IS the gap, and surfacing it is the point of running this. A gap is closed
by MINTING, which is a different act with a different authorization and lives next door in
`_lpm_acquisition_handoff`, re-exported here so this tooling's surface still offers it. That
module only ever DESCRIBES the mint and refuses outright without separate authorization, so
no migration run can acquire a credential as a side effect of reporting that one is missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_acquisition_handoff import AcquisitionHandoff, acquisition_handoff
from _lpm_anthropic import DEFINITIVE_REJECTION, INFERENCE_CAPABLE_OUTCOME, ValidationProbe
from _lpm_anthropic import validate_credential as probe_credential
from _lpm_canonical import canonical_json_text, length_prefixed_digest
from _lpm_onepassword import value_ref
from _lpm_record import CredentialRecord, record_object
from _lpm_results import ManagerError, internal_bug, invalid_request, store_unavailable
from _lpm_store import ConditionalSet, SecretStore

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "INCONCLUSIVE_SLOT",
    "LEGACY_KIND",
    "LEGACY_PROVIDER",
    "LEGACY_VARIABLE_PREFIX",
    "MIGRATION_OPERATION",
    "REJECTED_SLOT",
    "SLOT_DISPOSITIONS",
    "UNATTRIBUTED_SLOT",
    "UNWRITTEN_SLOT",
    "WRITTEN_SLOT",
    "AcquisitionHandoff",
    "LegacyTokenSource",
    "MigrationPlan",
    "MigrationReport",
    "RecordIdentity",
    "SlotOutcome",
    "acquisition_handoff",
    "legacy_slot_names",
    "migrate_legacy_tokens",
    "migrated_slot",
]

LEGACY_VARIABLE_PREFIX: Final = "CLAUDE_CODE_OAUTH_TOKEN"

LEGACY_PROVIDER: Final = "anthropic"
LEGACY_KIND: Final = "claude-code-oauth"

MIGRATION_OPERATION: Final = "legacy-token-migration"

WRITTEN_SLOT: Final = "written"
REJECTED_SLOT: Final = "rejected"
INCONCLUSIVE_SLOT: Final = "inconclusive"
UNATTRIBUTED_SLOT: Final = "unattributed"
UNWRITTEN_SLOT: Final = "unwritten"

SLOT_DISPOSITIONS: Final = (
    WRITTEN_SLOT,
    REJECTED_SLOT,
    INCONCLUSIVE_SLOT,
    UNATTRIBUTED_SLOT,
    UNWRITTEN_SLOT,
)


class LegacyTokenSource(Protocol):
    """The injected view of the legacy pool: which slots exist, whose, and their values."""

    def slot_names(self) -> tuple[str, ...]:
        """Every credential-environment name this source can see, migrated or not."""
        ...

    def account_for(self, *, name: str) -> str | None:
        """The account identity `name` is believed to hold, or None when unknown."""
        ...

    def value_for(self, *, name: str) -> str | None:
        """The raw token in `name`, or None when the slot is empty or unreadable."""
        ...


@dataclass(frozen=True, kw_only=True)
class RecordIdentity:
    """The pre-minted identity one migrated account's record is written under."""

    record_id: str
    value_generation: str


@dataclass(frozen=True, kw_only=True)
class MigrationPlan:
    """The deterministic inputs one migration run is bound to."""

    purpose: str
    expected_accounts: tuple[str, ...]
    identities: dict[str, RecordIdentity]
    now: str


@dataclass(frozen=True, kw_only=True)
class SlotOutcome:
    """What became of one legacy slot, named without its value."""

    name: str
    disposition: str
    account_id: str | None


@dataclass(frozen=True, kw_only=True)
class MigrationReport:
    """The complete, secret-free outcome of one migration run."""

    outcomes: tuple[SlotOutcome, ...]
    written: tuple[str, ...]
    missing_accounts: tuple[str, ...]


def legacy_slot_names(*, names: tuple[str, ...]) -> tuple[str, ...]:
    """The `CLAUDE_CODE_OAUTH_TOKEN` family among `names`, in lexical order.

    The family is the bare name and every suffixed sibling, which is how the pool was
    maintained by hand. Matching on the prefix rather than on a numbered pattern keeps a
    one-off `CLAUDE_CODE_OAUTH_TOKEN_SPARE` inside the migration, instead of leaving it
    behind as the one credential nobody moved.
    """
    return tuple(sorted(name for name in names if name.startswith(LEGACY_VARIABLE_PREFIX)))


def migrate_legacy_tokens(
    *, source: LegacyTokenSource, probe: ValidationProbe, store: SecretStore, plan: MigrationPlan
) -> Result[MigrationReport, ManagerError]:
    """Validate every legacy slot and write a record for each the provider accepts."""
    if plan.purpose == "":
        return Failure(invalid_request(message="migration purpose must be a non-empty string"))
    outcomes: list[SlotOutcome] = []
    for name in legacy_slot_names(names=source.slot_names()):
        outcome = migrated_slot(name=name, source=source, probe=probe, store=store, plan=plan)
        if isinstance(outcome, Failure):
            return Failure(outcome.failure())
        outcomes.append(outcome.unwrap())
    return Success(_reported(outcomes=tuple(outcomes), plan=plan))


def migrated_slot(
    *,
    name: str,
    source: LegacyTokenSource,
    probe: ValidationProbe,
    store: SecretStore,
    plan: MigrationPlan,
) -> Result[SlotOutcome, ManagerError]:
    """Validate one slot and, when the provider accepts it, write its record."""
    account_id = source.account_for(name=name)
    value = source.value_for(name=name)
    if account_id is None or account_id == "" or value is None or value == "":
        return Success(SlotOutcome(name=name, disposition=UNATTRIBUTED_SLOT, account_id=None))
    identity = plan.identities.get(account_id)
    if identity is None:
        return Failure(invalid_request(message=f"the plan declares no identity for {account_id}"))
    outcome = probe_credential(credential=value, probe=probe)
    if outcome == DEFINITIVE_REJECTION:
        return Success(SlotOutcome(name=name, disposition=REJECTED_SLOT, account_id=account_id))
    if outcome != INFERENCE_CAPABLE_OUTCOME:
        return Success(SlotOutcome(name=name, disposition=INCONCLUSIVE_SLOT, account_id=account_id))
    return _written_slot(
        name=name, account_id=account_id, identity=identity, store=store, plan=plan
    )


def _written_slot(
    *,
    name: str,
    account_id: str,
    identity: RecordIdentity,
    store: SecretStore,
    plan: MigrationPlan,
) -> Result[SlotOutcome, ManagerError]:
    record = CredentialRecord(
        record_id=identity.record_id,
        provider=LEGACY_PROVIDER,
        account_id=account_id,
        kind=LEGACY_KIND,
        purpose=plan.purpose,
        status="valid",
        acquired_at=plan.now,
        expires_at=None,
        last_validated=plan.now,
        value_generation=identity.value_generation,
        value_ref=value_ref(
            record_id=identity.record_id, value_generation=identity.value_generation
        ),
        previous_value_ref=None,
    )
    desired = canonical_json_text(value=record_object(record=record))
    if isinstance(desired, Failure):
        return Failure(internal_bug(message=f"migrated record is {desired.failure().reason}"))
    return _committed(
        name=name, account_id=account_id, identity=identity, store=store, desired=desired.unwrap()
    )


def _committed(
    *, name: str, account_id: str, identity: RecordIdentity, store: SecretStore, desired: str
) -> Result[SlotOutcome, ManagerError]:
    status = store.credential_conditional_set(
        request=ConditionalSet(
            record_id=identity.record_id,
            effect_id=length_prefixed_digest(
                values=(MIGRATION_OPERATION, identity.record_id, identity.value_generation)
            ),
            expected_record=None,
            desired_record=desired,
        )
    ).get("status")
    if status == "unavailable":
        return Failure(store_unavailable(message=f"the secret store did not accept {name}"))
    if status != "committed":
        return Success(SlotOutcome(name=name, disposition=UNWRITTEN_SLOT, account_id=account_id))
    return Success(SlotOutcome(name=name, disposition=WRITTEN_SLOT, account_id=account_id))


def _reported(*, outcomes: tuple[SlotOutcome, ...], plan: MigrationPlan) -> MigrationReport:
    written = tuple(outcome.name for outcome in outcomes if outcome.disposition == WRITTEN_SLOT)
    covered = {outcome.account_id for outcome in outcomes if outcome.disposition == WRITTEN_SLOT}
    return MigrationReport(
        outcomes=outcomes,
        written=written,
        missing_accounts=tuple(
            account for account in plan.expected_accounts if account not in covered
        ),
    )
