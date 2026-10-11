"""Metadata-only credential selection for concrete provisioning."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import Assignment
from _lpm_canonical import parse_canonical_json
from _lpm_eligibility import (
    AccountObservation,
    EligibilityPolicy,
    SelectionRequest,
    eligible_records,
)
from _lpm_engine_context import SelectedCredential
from _lpm_leases import AccountLease, lease_is_live, read_lease
from _lpm_paths import SELECTION_STATE_NAME, local_record_path
from _lpm_provision_request import ProvisionRequest
from _lpm_record import CredentialRecord, credential_record_from_object
from _lpm_results import ManagerError, store_unavailable
from _lpm_runtime_base import RuntimeHost
from _lpm_runtime_recovery_selection import (
    recoverable_selection,
)
from _lpm_selection_state import read_selection_state
from _lpm_strategy import select_record
from _lpm_time import add_seconds

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "selected_for_cleanup",
    "selected_for_recovery",
    "selected_for_request",
    "selected_from_assignment",
]


def selected_for_request(
    *, host: RuntimeHost, request: ProvisionRequest, now: str
) -> Result[SelectedCredential, ManagerError]:
    """Choose one eligible record using metadata, leases and durable ordering state."""
    records = _metadata_records(host=host)
    if isinstance(records, Failure):
        return Failure(records.failure())
    observations = _lease_observations(
        host=host,
        records=records.unwrap(),
        consumer_run_id=request.consumer_run_id,
        now=now,
    )
    if isinstance(observations, Failure):
        return Failure(observations.failure())
    state = read_selection_state(
        path=host.state_dir / SELECTION_STATE_NAME, owner_uid=host.owner_uid
    )
    if isinstance(state, Failure):
        return Failure(state.failure())
    wanted = SelectionRequest(provider=request.provider, kind=request.kind, purpose=request.purpose)
    eligible = eligible_records(
        request=wanted,
        records=records.unwrap(),
        observations=observations.unwrap(),
        policy=EligibilityPolicy(
            now=now,
            maximum_validation_age_seconds=host.config.maximum_validation_age_seconds,
            health_strategy=host.config.health_strategy,
            health_floor_percent=host.config.health_floor_percent,
            account_reservations=host.config.account_reservations,
        ),
    )
    selected = select_record(
        strategy=request.strategy, request=wanted, records=eligible, state=state.unwrap()
    )
    if isinstance(selected, Failure):
        return Failure(selected.failure())
    return _selected(record=selected.unwrap(), request=request, now=now)


def selected_from_assignment(*, assignment: Assignment) -> SelectedCredential:
    """Reconstruct the exact prepared selection without consulting the store again."""
    return SelectedCredential(
        account_id=assignment.account_id,
        record_id=assignment.record_id,
        value_generation=assignment.value_generation,
        value_ref=assignment.value_ref,
        receipt=dict(assignment.receipt),
    )


def selected_for_recovery(
    *,
    host: RuntimeHost,
    request: ProvisionRequest,
    lease_started_at: str,
) -> Result[SelectedCredential, ManagerError]:
    """Recover the exact selection named by a lease whose create effect already committed."""
    return selected_for_cleanup(
        host=host,
        request=request,
        lease_started_at=lease_started_at,
        fallback=lambda: Failure(
            store_unavailable(message="the committed lease selection could not be recovered")
        ),
    )


def selected_for_cleanup(
    *,
    host: RuntimeHost,
    request: ProvisionRequest,
    lease_started_at: str,
    fallback: Callable[[], Result[SelectedCredential, ManagerError]],
) -> Result[SelectedCredential, ManagerError]:
    """Keep a committed lease, falling back only when no such lease exists."""
    recovered = recoverable_selection(
        records=_metadata_records(host=host),
        lease_for=lambda record: _lease_for_record(host=host, record=record),
        request=request,
        lease_started_at=lease_started_at,
    )
    if isinstance(recovered, Failure):
        return recovered
    selected = recovered.unwrap()
    return Success(selected) if selected is not None else fallback()


def _metadata_records(*, host: RuntimeHost) -> Result[tuple[CredentialRecord, ...], ManagerError]:
    listed = host.store.metadata_list()
    if listed.get("status") != "ok":
        return Failure(store_unavailable(message="credential metadata could not be listed"))
    raw_items = listed.get("items")
    if not isinstance(raw_items, list):
        return Failure(store_unavailable(message="credential metadata list is malformed"))
    records: list[CredentialRecord] = []
    for item in cast("list[object]", raw_items):
        if not isinstance(item, dict):
            continue
        raw_record = cast("dict[str, object]", item).get("record")
        if isinstance(raw_record, str):
            parsed = parse_canonical_json(text=raw_record)
            if isinstance(parsed, Failure):
                continue
            record_object = parsed.unwrap()
        else:
            record_object = raw_record
        validated = credential_record_from_object(parsed=record_object)
        if isinstance(validated, Success):
            records.append(validated.unwrap())
    return Success(tuple(records))


def _lease_observations(
    *,
    host: RuntimeHost,
    records: tuple[CredentialRecord, ...],
    consumer_run_id: str,
    now: str,
) -> Result[dict[str, AccountObservation], ManagerError]:
    observations: dict[str, AccountObservation] = {}
    for record in records:
        path = local_record_path(
            state_dir=host.state_dir,
            family="lease",
            identity=(record.provider, record.account_id),
        )
        if isinstance(path, Failure):
            return Failure(path.failure())
        lease = read_lease(path=path.unwrap(), owner_uid=host.owner_uid)
        if isinstance(lease, Failure):
            return Failure(lease.failure())
        held = lease.unwrap()
        observations[record.account_id] = AccountObservation(
            leased=(
                held is not None
                and held.consumer_run_id != consumer_run_id
                and lease_is_live(lease=held, now=now)
            )
        )
    return Success(observations)


def _lease_for_record(
    *, host: RuntimeHost, record: CredentialRecord
) -> Result[AccountLease | None, ManagerError]:
    path = local_record_path(
        state_dir=host.state_dir,
        family="lease",
        identity=(record.provider, record.account_id),
    )
    if isinstance(path, Failure):
        return path
    return read_lease(path=path.unwrap(), owner_uid=host.owner_uid)


def _selected(
    *, record: CredentialRecord, request: ProvisionRequest, now: str
) -> Result[SelectedCredential, ManagerError]:
    expires_at = add_seconds(timestamp=now, seconds=request.lease_seconds)
    if (
        expires_at is None
        or record.last_validated is None
        or record.value_generation is None
        or record.value_ref is None
    ):
        return Failure(store_unavailable(message="the selected credential metadata is incomplete"))
    return Success(
        SelectedCredential(
            account_id=record.account_id,
            record_id=record.record_id,
            value_generation=record.value_generation,
            value_ref=record.value_ref,
            receipt={
                "record_id": record.record_id,
                "account_id": record.account_id,
                "purpose": record.purpose,
                "validated_at": record.last_validated,
                "lease_expires_at": expires_at,
            },
        )
    )
