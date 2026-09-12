"""Selection eligibility as SEVEN INDEPENDENT AXES, each asked the same question.

SPECIFICATION/spec.md states that a stored record matches a provisioning request exactly when its
`provider`, `kind` and `purpose` equal the request's; that purpose reservation is an ADDITIONAL
eligibility filter over matching records rather than part of matching; that only a `valid` record
neither age-stale nor expired is selectable; that a live run-scoped lease makes an account
ineligible under BOTH strategies; and that under `remaining-percent` an unreadable or below-floor
shared-usage observation makes the account ineligible rather than consume a reservation blindly,
while the default `none` strategy requires no observation and applies NO health-based exclusion.

THE AXES ARE SEPARATE BECAUSE THE CONTRACT COMPOSES THEM SEPARATELY. Purpose is a policy
partition, not a capability claim: two credential kinds on one account do NOT have
independent quota, a purpose name restricts no registered kind, and a reservation narrows
an account without changing what MATCHES. Collapsing any pair into one predicate — "is this
record usable" — is how a reservation starts reading as a match rule, or a health floor
starts silently excluding under `none`.

SO EACH AXIS IS A PREDICATE OVER ONE SHARED INPUT RECORD, held in a table. Every axis
answers exactly one question, "do I exclude this candidate", and is independently callable
and independently testable. `excluding_axis` walks the table in its declared order and
names the FIRST axis that excludes, so a diagnostic says WHICH concern rejected a candidate
rather than that something did.

THE ORDER IS CHEAP-AND-STRUCTURAL FIRST, OBSERVED LAST, and that is load-bearing rather
than tidy: the shared-usage axis is the only one whose input costs a provider call, so
nothing reaches it that a byte comparison, a freshness boundary, a configured reservation
or a lease file could already have refused. Under `none` it is inert by construction — it
reads no observation at all — which is exactly the contract's "MUST NOT invoke a provider
health adapter and MUST apply no health-based exclusion".

AN ABSENT OBSERVATION IS NOT A PASS. Under `remaining-percent` a candidate whose account
supplied no remainder is ineligible, which is the same answer an unavailable or malformed
one gets. The floor itself is INCLUSIVE: a remainder equal to it remains eligible.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from _lpm_record import CredentialRecord, is_selectable
from _lpm_reservations import REMAINING_PERCENT_STRATEGY, AccountReservations

__all__: list[str] = [
    "ELIGIBILITY_AXES",
    "EXCLUSION_BY_AXIS",
    "AccountObservation",
    "AxisInputs",
    "AxisPredicate",
    "EligibilityPolicy",
    "SelectionRequest",
    "account_lease_excludes",
    "credential_kind_excludes",
    "eligible_records",
    "excluding_axis",
    "provider_excludes",
    "purpose_excludes",
    "purpose_reservation_excludes",
    "shared_account_usage_excludes",
    "validation_state_excludes",
]


@dataclass(frozen=True, kw_only=True)
class SelectionRequest:
    """The three fields a stored record must equal byte-for-byte to MATCH a request."""

    provider: str
    kind: str
    purpose: str


@dataclass(frozen=True, kw_only=True)
class AccountObservation:
    """One account's independently-supplied axis inputs, keyed elsewhere by `account_id`.

    Both defaults are the conservative reading of "nobody told me": no lease is known to be
    held, and no shared-usage remainder was obtained — which under `remaining-percent`
    excludes the account rather than admitting it.
    """

    leased: bool = False
    shared_usage_remaining: int | None = None


@dataclass(frozen=True, kw_only=True)
class EligibilityPolicy:
    """The captured instant and configured policy every axis decides against."""

    now: str
    maximum_validation_age_seconds: int
    health_strategy: str
    health_floor_percent: int
    account_reservations: AccountReservations


@dataclass(frozen=True, kw_only=True)
class AxisInputs:
    """Everything any one axis may read, so every axis has the same signature."""

    request: SelectionRequest
    record: CredentialRecord
    observation: AccountObservation
    policy: EligibilityPolicy


class AxisPredicate(Protocol):
    """One eligibility axis: does it exclude this candidate?"""

    def __call__(self, *, inputs: AxisInputs) -> bool:
        """Whether this axis alone makes the candidate ineligible."""
        ...


def provider_excludes(*, inputs: AxisInputs) -> bool:
    """The provider axis: matching is byte-exact, never a family or alias."""
    return inputs.record.provider != inputs.request.provider


def credential_kind_excludes(*, inputs: AxisInputs) -> bool:
    """The credential-capability axis: a kind's adapters are per-kind, so there is no fallback."""
    return inputs.record.kind != inputs.request.kind


def purpose_excludes(*, inputs: AxisInputs) -> bool:
    """The purpose axis: a differently-purposed record does not match, reservations aside."""
    return inputs.record.purpose != inputs.request.purpose


def validation_state_excludes(*, inputs: AxisInputs) -> bool:
    """The validation-state axis: only a fresh, unexpired `valid` record survives it.

    This is also what keeps a `suspect` record out of selection until a successful
    revalidation returns it to `valid` — the lifecycle table has no other route back.
    """
    return not is_selectable(
        record=inputs.record,
        now=inputs.policy.now,
        maximum_validation_age_seconds=inputs.policy.maximum_validation_age_seconds,
    )


def purpose_reservation_excludes(*, inputs: AxisInputs) -> bool:
    """The reservation axis: a reserved account permits ONLY its listed purposes.

    An account absent from its provider's object is unreserved, and a well-shaped key with
    no matching record reserves nothing — both fall through as permitted.
    """
    accounts = inputs.policy.account_reservations.get(inputs.record.provider)
    if accounts is None:
        return False
    permitted = accounts.get(inputs.record.account_id)
    if permitted is None:
        return False
    return inputs.record.purpose not in permitted


def account_lease_excludes(*, inputs: AxisInputs) -> bool:
    """The lease axis: a live run-scoped lease hides the account from every other request."""
    return inputs.observation.leased


def shared_account_usage_excludes(*, inputs: AxisInputs) -> bool:
    """The shared-usage axis: inert under `none`, floor-enforcing under `remaining-percent`."""
    if inputs.policy.health_strategy != REMAINING_PERCENT_STRATEGY:
        return False
    remaining = inputs.observation.shared_usage_remaining
    if remaining is None:
        return True
    return remaining < inputs.policy.health_floor_percent


EXCLUSION_BY_AXIS: Final[dict[str, AxisPredicate]] = {
    "provider": provider_excludes,
    "credential-kind": credential_kind_excludes,
    "purpose": purpose_excludes,
    "validation-state": validation_state_excludes,
    "purpose-reservation": purpose_reservation_excludes,
    "account-lease": account_lease_excludes,
    "shared-account-usage": shared_account_usage_excludes,
}

ELIGIBILITY_AXES: Final = tuple(EXCLUSION_BY_AXIS)


def excluding_axis(*, inputs: AxisInputs) -> str | None:
    """The FIRST axis that excludes this candidate, or None when every axis admits it."""
    for axis in ELIGIBILITY_AXES:
        if EXCLUSION_BY_AXIS[axis](inputs=inputs):
            return axis
    return None


def eligible_records(
    *,
    request: SelectionRequest,
    records: tuple[CredentialRecord, ...],
    observations: Mapping[str, AccountObservation],
    policy: EligibilityPolicy,
) -> tuple[CredentialRecord, ...]:
    """Every candidate in `records` that no axis excludes, in the order given.

    `observations` is keyed by `account_id`; an account with no entry is treated as
    unobserved rather than as observed-healthy. Ordering is left to the strategy: this
    function answers WHICH records are eligible, never which one to take.
    """
    admitted: list[CredentialRecord] = []
    for record in records:
        inputs = AxisInputs(
            request=request,
            record=record,
            observation=observations.get(record.account_id, AccountObservation()),
            policy=policy,
        )
        if excluding_axis(inputs=inputs) is None:
            admitted.append(record)
    return tuple(admitted)
