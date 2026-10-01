"""Assembling the `ProvisionContext`: resolve the reference, survey the leases, choose the account.

`_lpm_provision.provision` decides what a provisioning request DOES; it needs a context assembled
out of persisted state first, and assembling one is a distinct concern with its own failure modes.
Everything here runs BEFORE the first write, which is why a defect found at this stage leaves the
target byte-identical and the run identity unconsumed.

THE AUTHORITATIVE SELECTION IS `provision`'S, NOT THIS MODULE'S -- and this module nonetheless
selects first, which deserves an explanation rather than a reader's suspicion. `ProvisionContext`
takes ONE `lease_path`, and a lease path is keyed by provider and account: it cannot be known until
an account has been chosen. So the account is resolved here, using the same public
`eligible_records` + `select_record` over the same inputs, purely to derive that path; `provision`
then re-runs the identical selection and its answer is the one that governs. The duplication is
deterministic -- same records, same observations, same policy, same state -- and it is a consequence
of the ratified context shape, not a second policy. A `ProvisionContext` taking a lease-path
FUNCTION would remove it, and that is a change to a ratified module rather than something to work
around silently.

OBSERVATIONS COME FROM THE LEASE RECORDS, which is what makes the `account_lease_excludes`
eligibility axis mean anything. An empty observation map would silently hand two concurrent runs the
same account, and the only thing standing in the way would be the non-blocking lease try inside
`provision` -- a race the exclusion exists to avoid entering.
"""

from __future__ import annotations

from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_command_host import (
    ManagerHost,
    eligibility_policy,
    lease_survey,
    manager_lock_path,
    selection_state_path,
)
from _lpm_eligibility import SelectionRequest, eligible_records
from _lpm_localstate import read_local_record
from _lpm_paths import local_record_path
from _lpm_provision import ProvisionContext, ProvisionRequest
from _lpm_record import CredentialRecord
from _lpm_results import ManagerError, internal_bug, invalid_request
from _lpm_selection_state import read_selection_state
from _lpm_strategy import select_record
from _lpm_target import TargetIssuance, TargetLock, issuance_from_object

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ISSUANCE_FAMILY",
    "TARGET_LOCK_FAMILY",
    "provision_context",
    "provision_issuance",
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


def provision_context(
    *,
    request: ProvisionRequest,
    host: ManagerHost,
    issuance: TargetIssuance,
    records: tuple[CredentialRecord, ...],
) -> Result[tuple[ProvisionContext, CredentialRecord], ManagerError]:
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
    selection = SelectionRequest(
        provider=request.provider, kind=request.kind, purpose=request.purpose
    )
    selected = select_record(
        strategy=request.strategy,
        request=selection,
        records=eligible_records(
            request=selection,
            records=records,
            observations=survey.observations,
            policy=policy,
        ),
        state=state.unwrap(),
    )
    if isinstance(selected, Failure):
        return Failure(selected.failure())
    record = selected.unwrap()
    if record.value_generation is None or record.value_ref is None:
        return Failure(internal_bug(message="a selected record carries a value and a generation"))
    return Success(
        (
            ProvisionContext(
                records=records,
                state=state.unwrap(),
                issuance=issuance,
                issuance_bound=False,
                observations=survey.observations,
                policy=policy,
                lease_path=survey.paths[record.account_id],
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
