"""Authoritative issuance reads shared by target and provision commands."""

from __future__ import annotations

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_localstate import read_local_record
from _lpm_paths import local_record_path
from _lpm_provision_request import ProvisionRequest
from _lpm_results import ManagerError, invalid_request, store_unavailable
from _lpm_runtime_base import RuntimeHost
from _lpm_target import TargetIssuance, issuance_from_object, resolve_issuance
from _lpm_time import is_at_or_after

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "existing_issuance_payload",
    "issuance_for_run",
    "read_runtime_issuance",
    "refuse_destination_conflict",
    "resolved_runtime_issuance",
]


def resolved_runtime_issuance(
    *, host: RuntimeHost, request: ProvisionRequest, bound: bool, now: str | None = None
) -> Result[TargetIssuance, ManagerError]:
    """Resolve a persisted issuance for its exact run, reference and expiry state."""
    stored = read_runtime_issuance(host=host, reference=request.target_ref)
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    issuance = stored.unwrap()
    if issuance is None:
        return Failure(invalid_request(message="target_ref does not name an issuance"))
    resolved = resolve_issuance(
        issuance=issuance,
        target_ref=request.target_ref,
        consumer_run_id=request.consumer_run_id,
        now=host.capture_time() if now is None else now,
        bound=bound,
    )
    if isinstance(resolved, Failure):
        return Failure(resolved.failure())
    return Success(issuance)


def read_runtime_issuance(
    *, host: RuntimeHost, reference: str
) -> Result[TargetIssuance | None, ManagerError]:
    """Read and validate one issuance by its opaque reference."""
    path = local_record_path(state_dir=host.state_dir, family="issuance", identity=(reference,))
    if isinstance(path, Failure):
        return Failure(path.failure())
    stored = read_local_record(path=path.unwrap(), owner_uid=host.owner_uid)
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    if stored.unwrap() is None:
        return Success(None)
    parsed = issuance_from_object(parsed=stored.unwrap())
    if isinstance(parsed, Failure):
        return Failure(store_unavailable(message="the retained issuance is malformed"))
    return parsed


def issuance_for_run(
    *, host: RuntimeHost, consumer_run_id: str
) -> Result[TargetIssuance | None, ManagerError]:
    """Find the sole retained issuance for a run, refusing ambiguous local state."""
    inventory = _issuance_inventory(host=host)
    if isinstance(inventory, Failure):
        return Failure(inventory.failure())
    matches = [
        issuance for issuance in inventory.unwrap() if issuance.consumer_run_id == consumer_run_id
    ]
    if len(matches) > 1:
        return Failure(store_unavailable(message="more than one issuance names this consumer run"))
    return Success(matches[0] if matches else None)


def refuse_destination_conflict(
    *, host: RuntimeHost, consumer_run_id: str, destination: str
) -> Result[None, ManagerError]:
    """Refuse a canonical destination already issued to another consumer run."""
    inventory = _issuance_inventory(host=host)
    if isinstance(inventory, Failure):
        return Failure(inventory.failure())
    conflict = any(
        issuance.destination == destination and issuance.consumer_run_id != consumer_run_id
        for issuance in inventory.unwrap()
    )
    if conflict:
        return Failure(invalid_request(message="target destination is issued to another run"))
    return Success(None)


def _issuance_inventory(*, host: RuntimeHost) -> Result[tuple[TargetIssuance, ...], ManagerError]:
    """Read every retained issuance from the one authoritative local directory."""
    directory = host.state_dir / "issuances"
    if not directory.exists():
        return Success(())
    try:
        paths = sorted(directory.iterdir())
    except OSError:
        return Failure(store_unavailable(message="the issuance directory is unreadable"))
    issuances: list[TargetIssuance] = []
    for path in paths:
        stored = read_local_record(path=path, owner_uid=host.owner_uid)
        if isinstance(stored, Failure):
            return Failure(stored.failure())
        if stored.unwrap() is None:
            continue
        parsed = issuance_from_object(parsed=stored.unwrap())
        if isinstance(parsed, Failure):
            return Failure(store_unavailable(message="a retained issuance is malformed"))
        issuances.append(parsed.unwrap())
    return Success(tuple(issuances))


def existing_issuance_payload(
    *, host: RuntimeHost, issuance: TargetIssuance, requested_adapter: str
) -> Result[dict[str, object], ManagerError]:
    """Return an unexpired identical target retry, or its typed refusal."""
    incompatible = issuance.adapter != requested_adapter
    expired = is_at_or_after(moment=host.capture_time(), limit=issuance.expires_at) is not False
    if incompatible or expired:
        return Failure(
            invalid_request(message="this run's target retry is incompatible or expired")
        )
    return Success(
        {
            "operation": "target",
            "target_ref": issuance.reference,
            "expires_at": issuance.expires_at,
        }
    )
