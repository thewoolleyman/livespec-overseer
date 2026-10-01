"""The `target` command: issue one opaque reference bound to one consumer run, and persist it.

SPECIFICATION/contracts.md states the request and the work exactly: "A target request MUST
contain only `version` (the integer `1`), non-empty `consumer_run_id` and non-empty `adapter`.
Requiring that adapter to be registered and present in `enabled_target_adapters` is a
command-specific predicate in the exact pre-recovery validation order, after configuration and
object-shape validation but before recovery; an unregistered or registered-but-disabled adapter
MUST return `invalid-request` without recovery, adapter invocation or mutation. The manager
MUST invoke the enabled `ProvisioningTarget` adapter to issue an opaque, unguessable reference
bound to the run, persist the issuance record and return the reference plus its UTC RFC
3339-second `expires_at`."

THE REFERENCE IS MINTED BY THE HOST, NOT HERE, and `_lpm_target.new_issuance` says why in its
own docstring: "The reference's unguessability is the caller's to supply ... deriving one here
would put entropy policy inside the record shape." The real host mints from `secrets`; a test
mints a fixed string, which is the only reason a persisted issuance record can be asserted at
all.

THE CONSUMER NEVER NAMES A DESTINATION. It supplies a run identity, and `target_destination`
derives the path from a digest of the issued reference beneath the manager's own owner-only
state. That is how the adapter's "writable only within that run's isolated execution target,
and neither the host's live interactive-agent credential nor a destination issued to any other
run" requirement holds structurally rather than by validating a path the consumer proposed --
there is no such path to validate.

THE DESTINATION LOCK IS HELD ACROSS THE ISSUE, which the contract requires: "A target command
MUST hold its destination lock from before cross-run destination discovery through
authoritative `issuance-create` commit." Two concurrent target commands for the same
destination therefore serialize, and the one that cannot take the lock within
`external_call_timeout_seconds` reports `store-unavailable` with nothing written rather than
racing a half-written issuance.
"""

from __future__ import annotations

from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_command_host import (
    CommandOutcome,
    ManagerHost,
    error_outcome,
    establish_manager_state,
    manager_lock_path,
    read_command_object,
    success_outcome,
    target_destination,
)
from _lpm_localstate import write_local_record
from _lpm_locks import release_lock, take_lock
from _lpm_paths import local_record_path
from _lpm_registry import REGISTERED_TARGET_ADAPTERS
from _lpm_results import ManagerError, invalid_request
from _lpm_target import issuance_object, new_issuance

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "DESTINATION_LOCK_FAMILY",
    "ISSUANCE_FAMILY",
    "TARGET_OPERATION",
    "TARGET_REQUEST_MEMBERS",
    "TARGET_REQUEST_VERSION",
    "run_target_command",
]

TARGET_OPERATION: Final = "target"
TARGET_REQUEST_VERSION: Final = 1
TARGET_REQUEST_MEMBERS: Final = ("version", "consumer_run_id", "adapter")
ISSUANCE_FAMILY: Final = "issuance"
DESTINATION_LOCK_FAMILY: Final = "destination"


def run_target_command(*, source: str, host: ManagerHost) -> CommandOutcome:
    """Validate the request, then issue and persist exactly one reference for its run."""
    parsed = read_command_object(source=source, read_input=host.read_input, refuse=invalid_request)
    if isinstance(parsed, Failure):
        return error_outcome(error=parsed.failure())
    request = _target_request(parsed=parsed.unwrap(), host=host)
    if isinstance(request, Failure):
        return error_outcome(error=request.failure())
    consumer_run_id, adapter = request.unwrap()
    issued = _issue(consumer_run_id=consumer_run_id, adapter=adapter, host=host)
    if isinstance(issued, Failure):
        return error_outcome(error=issued.failure())
    reference, expires_at = issued.unwrap()
    return success_outcome(
        payload={
            "operation": TARGET_OPERATION,
            "target_ref": reference,
            "expires_at": expires_at,
        }
    )


def _target_request(*, parsed: object, host: ManagerHost) -> Result[tuple[str, str], ManagerError]:
    """Exact object shape first, then the enabled-adapter predicate — in the contract's order."""
    if not isinstance(parsed, dict):
        return Failure(invalid_request(message="a target request must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    defect = _shape_defect(source=source)
    if defect is not None:
        return Failure(defect)
    adapter = str(source["adapter"])
    enabled = _enabled_adapter_defect(adapter=adapter, host=host)
    if enabled is not None:
        return Failure(enabled)
    return Success((str(source["consumer_run_id"]), adapter))


def _shape_defect(*, source: dict[str, object]) -> ManagerError | None:
    if sorted(source) != sorted(TARGET_REQUEST_MEMBERS):
        return invalid_request(
            message=f"a target request carries only {', '.join(TARGET_REQUEST_MEMBERS)}"
        )
    version = source["version"]
    if isinstance(version, bool) or version != TARGET_REQUEST_VERSION:
        return invalid_request(message="target request version must be the integer 1")
    for member in TARGET_REQUEST_MEMBERS[1:]:
        value = source[member]
        if not isinstance(value, str) or value == "":
            return invalid_request(message=f"target request {member} must be a non-empty string")
    return None


def _enabled_adapter_defect(*, adapter: str, host: ManagerHost) -> ManagerError | None:
    """The command-specific predicate: registered AND enabled, both refused the same way."""
    if adapter not in REGISTERED_TARGET_ADAPTERS:
        return invalid_request(message="the requested target adapter is not registered")
    if adapter not in host.config.enabled_target_adapters:
        return invalid_request(message="the requested target adapter is not enabled")
    return None


def _issue(
    *, consumer_run_id: str, adapter: str, host: ManagerHost
) -> Result[tuple[str, str], ManagerError]:
    """Mint, serialize on the destination, and commit the issuance record under that lock."""
    established = establish_manager_state(state_dir=host.state_dir, owner_uid=host.owner_uid)
    if isinstance(established, Failure):
        return Failure(established.failure())
    reference = host.new_reference()
    destination = target_destination(state_dir=host.state_dir, reference=reference)
    held = take_lock(
        path=manager_lock_path(
            state_dir=host.state_dir,
            family=DESTINATION_LOCK_FAMILY,
            identity=[str(destination)],
        ),
        owner_uid=host.owner_uid,
        timeout_seconds=float(host.config.external_call_timeout_seconds),
        monotonic=host.monotonic,
        sleep=host.sleep,
    )
    if isinstance(held, Failure):
        return Failure(held.failure())
    try:
        return _committed_issuance(
            reference=reference,
            consumer_run_id=consumer_run_id,
            adapter=adapter,
            destination=str(destination),
            host=host,
        )
    finally:
        release_lock(held=held.unwrap())


def _committed_issuance(
    *, reference: str, consumer_run_id: str, adapter: str, destination: str, host: ManagerHost
) -> Result[tuple[str, str], ManagerError]:
    issuance = new_issuance(
        reference=reference,
        consumer_run_id=consumer_run_id,
        adapter=adapter,
        destination=destination,
        now=host.now,
    )
    if isinstance(issuance, Failure):
        return Failure(issuance.failure())
    issued = issuance.unwrap()
    path = local_record_path(state_dir=host.state_dir, family=ISSUANCE_FAMILY, identity=[reference])
    if isinstance(path, Failure):
        return Failure(path.failure())
    written = write_local_record(
        path=path.unwrap(),
        value=issuance_object(issuance=issued),
        owner_uid=host.owner_uid,
    )
    if isinstance(written, Failure):
        return Failure(written.failure())
    return Success((reference, issued.expires_at))
