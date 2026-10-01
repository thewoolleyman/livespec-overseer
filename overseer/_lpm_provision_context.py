"""Assembling the `ProvisionContext`: resolve the reference, survey the leases, choose the account.

`_lpm_provision.provision` decides what a provisioning request DOES; it needs a context assembled
out of persisted state first, and assembling one is a distinct concern with its own failure modes.
Everything here runs BEFORE the first write, which is why a defect found at this stage leaves the
target byte-identical and the run identity unconsumed.

SELECTION HAPPENS EXACTLY ONCE, AND A RESUMED PROVISION DOES NOT DO IT AT ALL. `ProvisionContext`
takes ONE `lease_path`, keyed by provider and account, so an account must be chosen before the
context can be built. This module makes that choice and `_lpm_provision.provision_selected`
consumes it, which is why that selection-free seam exists: an earlier cut selected here for the
lease path and let `provision` select AGAIN for the credential, on the reasoning that the two runs
were deterministic. Deterministic is not the same as safe. When a prepared assignment already
exists the account is NOT a free choice -- the previous attempt's target write may already have
committed against it -- so `resumed_record` reads the account out of that record and no selection
runs.

`issuance_bound` FOLLOWS FROM THE SAME FACT. The contract keeps a reference resolvable "even after
its issuance `expires_at`" while a prepared assignment binds it, so a prepared record both names
the account and licenses the expired-reference resolution a recovery needs.

OBSERVATIONS COME FROM THE LEASE RECORDS, which is what makes the `account_lease_excludes`
eligibility axis mean anything. An empty observation map would silently hand two concurrent runs
the same account, and the only thing standing in the way would be the non-blocking lease try
inside `provision` -- a race the exclusion exists to avoid entering.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import Assignment
from _lpm_command_host import (
    LeaseSurvey,
    ManagerHost,
    eligibility_policy,
    lease_survey,
    manager_lock_path,
    selection_state_path,
)
from _lpm_eligibility import EligibilityPolicy, SelectionRequest, eligible_records
from _lpm_localstate import read_local_record
from _lpm_paths import local_record_path
from _lpm_provision import ProvisionContext, ProvisionRequest
from _lpm_record import CredentialRecord
from _lpm_results import ManagerError, internal_bug, invalid_request
from _lpm_selection_state import SelectionState, read_selection_state
from _lpm_strategy import select_record
from _lpm_target import TargetIssuance, TargetLock, issuance_from_object

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ISSUANCE_FAMILY",
    "TARGET_LOCK_FAMILY",
    "provision_context",
    "provision_issuance",
    "resumed_record",
]

ISSUANCE_FAMILY: Final = "issuance"
TARGET_LOCK_FAMILY: Final = "target"


def provision_issuance(
    *, target_ref: str, host: ManagerHost
) -> Result[TargetIssuance, ManagerError]:
    """The persisted issuance for this reference; an absent one is refused before selection."""
    path = local_record_path(
        state_dir=host.state_dir, family=ISSUANCE_FAMILY, identity=[target_ref]
    )
    if isinstance(path, Failure):
        return Failure(path.failure())
    stored = read_local_record(path=path.unwrap(), owner_uid=host.owner_uid)
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    parsed = stored.unwrap()
    if parsed is None:
        return Failure(invalid_request(message="target_ref names no issued reference"))
    return issuance_from_object(parsed=parsed)


def resumed_record(
    *, prepared: Assignment, records: Sequence[CredentialRecord]
) -> CredentialRecord | None:
    """The exact credential a prepared assignment names, or `None` when it is no longer stored.

    Identity is the record id AND the value generation together. A record whose generation has since
    been replaced is not the credential that assignment prepared, and writing the new one would
    silently hand the consumer a different secret than the receipt it is about to be given
    describes.
    """
    for record in records:
        if (
            record.record_id == prepared.record_id
            and record.value_generation == prepared.value_generation
        ):
            return record
    return None


def provision_context(
    *,
    request: ProvisionRequest,
    host: ManagerHost,
    issuance: TargetIssuance,
    records: tuple[CredentialRecord, ...],
    prepared: Assignment | None,
) -> Result[tuple[ProvisionContext, CredentialRecord | None], ManagerError]:
    state = read_selection_state(
        path=selection_state_path(state_dir=host.state_dir), owner_uid=host.owner_uid
    )
    if isinstance(state, Failure):
        return Failure(state.failure())
    surveyed = lease_survey(
        state_dir=host.state_dir,
        records=records,
        owner_uid=host.owner_uid,
        now=host.now,
        consumer_run_id=request.consumer_run_id,
    )
    if isinstance(surveyed, Failure):
        return Failure(surveyed.failure())
    survey = surveyed.unwrap()
    policy = eligibility_policy(config=host.config, now=host.now)
    chosen = _chosen(
        request=request,
        records=records,
        survey=survey,
        policy=policy,
        state=state.unwrap(),
        prepared=prepared,
    )
    if isinstance(chosen, Failure):
        return Failure(chosen.failure())
    record = chosen.unwrap()
    if record is not None and (record.value_generation is None or record.value_ref is None):
        return Failure(internal_bug(message="a selected record carries a value and a generation"))
    return Success(
        (
            ProvisionContext(
                records=records,
                state=state.unwrap(),
                issuance=issuance,
                issuance_bound=prepared is not None,
                observations=survey.observations,
                policy=policy,
                lease_path=survey.paths[_account(record=record, prepared=prepared)],
                target_lock=TargetLock(
                    path=manager_lock_path(
                        state_dir=host.state_dir,
                        family=TARGET_LOCK_FAMILY,
                        identity=[request.target_ref],
                    ),
                    timeout_seconds=float(host.config.external_call_timeout_seconds),
                    monotonic=host.monotonic,
                    sleep=host.sleep,
                ),
                owner_uid=host.owner_uid,
                now=host.now,
                read_value=host.read_value,
            ),
            record,
        )
    )


def _chosen(
    *,
    request: ProvisionRequest,
    records: tuple[CredentialRecord, ...],
    survey: LeaseSurvey,
    policy: EligibilityPolicy,
    state: SelectionState,
    prepared: Assignment | None,
) -> Result[CredentialRecord | None, ManagerError]:
    """The prepared record on a resume; otherwise one fresh selection over the eligible set."""
    if prepared is not None:
        return Success(resumed_record(prepared=prepared, records=records))
    selection = SelectionRequest(
        provider=request.provider, kind=request.kind, purpose=request.purpose
    )
    selected = select_record(
        strategy=request.strategy,
        request=selection,
        records=eligible_records(
            request=selection, records=records, observations=survey.observations, policy=policy
        ),
        state=state,
    )
    if isinstance(selected, Failure):
        return Failure(selected.failure())
    return Success(selected.unwrap())


def _account(*, record: CredentialRecord | None, prepared: Assignment | None) -> str:
    """Whose lease path the context carries: the resolved record's, else the prepared record's.

    A resume whose credential has vanished still needs a well-formed context to be returned so the
    caller can report that absence -- `survey.paths` is keyed by every surveyed account, and a
    prepared assignment's account is one of them whenever its record is still stored.
    """
    if record is not None:
        return record.account_id
    return "" if prepared is None else prepared.account_id
