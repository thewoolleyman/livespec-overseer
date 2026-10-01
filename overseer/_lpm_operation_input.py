"""The exact `normalized_input` each command's write-ahead record may carry.

SPECIFICATION/contracts.md states `normalized_input` as "the command's exact validated input
with provisioning defaults materialized" and then fixes each command's membership LITERALLY:
acquire adds its generated `record_id` and `next_value_generation`; reacquire contains exactly
`record_id` and `next_value_generation`; revalidate contains exactly `record_id`; report
contains exactly `version`, `consumer_run_id`, `record_id`, `occurred_at` and `classification`
WHILE OMITTING `diagnostic`; and expire contains exactly `consumer_run_id` and `record_id`.
Target, provision, complete and release carry their consumer request objects, with provision's
two optional members already materialized.

MEMBERSHIP IS NOT A DETAIL HERE, IT IS THE REPLAY CONTRACT. A resuming process re-derives what
to do from this object alone — which lease to take, which record to transition, which target to
write — so an input that is merely "a JSON object" would let a recovery replay a command whose
inputs it cannot actually reconstruct. Two of the rules are sharper than they look: `report`
MUST OMIT `diagnostic`, because the diagnostic is validated and then discarded and a stored copy
would put consumer-supplied prose into a durable record; and provision's defaults MUST be
materialized, because the stored object is what an "identical request" is compared against, and
a request with an absent `strategy` must compare equal to one that spelled the default out.

THE THREE INTERNAL COMMANDS CARRY NO `version`. Reacquire, revalidate and expire are never
invoked by a consumer and have no request envelope to version; the contract lists their members
without one, and adding it "for consistency" would make every stored record of those commands
fail its own validator.

Every field's rule is one total predicate with no branches of its own, dispatched from a closed
field-kind table. That keeps the per-field rules enumerable in one place rather than spread
through a validator, so a new member cannot be added without declaring what makes it valid.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_leases import MAXIMUM_LEASE_SECONDS, MINIMUM_LEASE_SECONDS
from _lpm_record import is_uuid4
from _lpm_signal import REPORT_CLASSIFICATIONS
from _lpm_strategy import SELECTION_STRATEGIES
from _lpm_time import is_canonical_timestamp

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "CONSUMER_CLASSES",
    "NORMALIZED_INPUT_MEMBERS",
    "NORMALIZED_INPUT_VERSION",
    "normalized_input_defect",
]

NORMALIZED_INPUT_VERSION: Final = 1
CONSUMER_CLASSES: Final = ("test", "production")

NORMALIZED_INPUT_MEMBERS: Final[dict[str, tuple[str, ...]]] = {
    "acquire": (
        "version",
        "provider",
        "account_id",
        "kind",
        "purpose",
        "record_id",
        "next_value_generation",
    ),
    "reacquire": ("record_id", "next_value_generation"),
    "revalidate": ("record_id",),
    "target": ("version", "consumer_run_id", "adapter"),
    "provision": (
        "version",
        "provider",
        "kind",
        "purpose",
        "consumer_run_id",
        "target_ref",
        "strategy",
        "lease_seconds",
    ),
    "report": ("version", "consumer_run_id", "record_id", "occurred_at", "classification"),
    "complete": (
        "version",
        "consumer_run_id",
        "record_id",
        "completed_at",
        "consumer_class",
        "provider_authenticated",
        "alternate_credential_used",
        "legacy_pool_absent",
    ),
    "release": ("version", "consumer_run_id", "record_id"),
    "expire": ("consumer_run_id", "record_id"),
}


def _is_version(*, value: object) -> bool:
    return not isinstance(value, bool) and value == NORMALIZED_INPUT_VERSION


def _is_text(*, value: object) -> bool:
    return isinstance(value, str) and value != ""


def _is_uuid(*, value: object) -> bool:
    return isinstance(value, str) and is_uuid4(value=value)


def _is_timestamp(*, value: object) -> bool:
    return isinstance(value, str) and is_canonical_timestamp(text=value)


def _is_classification(*, value: object) -> bool:
    return value in REPORT_CLASSIFICATIONS


def _is_strategy(*, value: object) -> bool:
    return value in SELECTION_STRATEGIES


def _is_lease_seconds(*, value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, int)
        and MINIMUM_LEASE_SECONDS <= value <= MAXIMUM_LEASE_SECONDS
    )


def _is_consumer_class(*, value: object) -> bool:
    return value in CONSUMER_CLASSES


def _is_boolean(*, value: object) -> bool:
    return isinstance(value, bool)


_FIELD_KINDS: Final[dict[str, str]] = {
    "version": "version",
    "provider": "text",
    "account_id": "text",
    "kind": "text",
    "purpose": "text",
    "consumer_run_id": "text",
    "adapter": "text",
    "target_ref": "text",
    "record_id": "uuid",
    "next_value_generation": "uuid",
    "occurred_at": "timestamp",
    "completed_at": "timestamp",
    "classification": "classification",
    "strategy": "strategy",
    "lease_seconds": "lease_seconds",
    "consumer_class": "consumer_class",
    "provider_authenticated": "boolean",
    "alternate_credential_used": "boolean",
    "legacy_pool_absent": "boolean",
}

_PREDICATES: Final[dict[str, Callable[..., bool]]] = {
    "version": _is_version,
    "text": _is_text,
    "uuid": _is_uuid,
    "timestamp": _is_timestamp,
    "classification": _is_classification,
    "strategy": _is_strategy,
    "lease_seconds": _is_lease_seconds,
    "consumer_class": _is_consumer_class,
    "boolean": _is_boolean,
}

_REASONS: Final[dict[str, str]] = {
    "version": "must be the integer 1",
    "text": "must be a non-empty string",
    "uuid": "must be a lowercase RFC 4122 UUIDv4",
    "timestamp": "must be a UTC RFC 3339-second timestamp",
    "classification": f"must be one of: {', '.join(REPORT_CLASSIFICATIONS)}",
    "strategy": f"must be one of: {', '.join(SELECTION_STRATEGIES)}",
    "lease_seconds": (
        f"must be an integer from {MINIMUM_LEASE_SECONDS} through {MAXIMUM_LEASE_SECONDS}"
    ),
    "consumer_class": f"must be one of: {', '.join(CONSUMER_CLASSES)}",
    "boolean": "must be a Boolean",
}


def normalized_input_defect(*, command: str, normalized_input: object) -> str | None:
    """A reason `normalized_input` is not `command`'s exact validated input.

    The membership comparison is EXACT in both directions: a missing member makes a replay
    impossible, and an extra one is how a `diagnostic` or an un-normalized optional would
    reach a durable record.
    """
    members = NORMALIZED_INPUT_MEMBERS.get(command)
    if members is None:
        return f"unregistered operation command: {command}"
    if not isinstance(normalized_input, dict):
        return "normalized_input must be a JSON object"
    source = cast("dict[str, object]", normalized_input)
    if sorted(source) != sorted(members):
        return f"{command} normalized_input must contain exactly {', '.join(members)}"
    for field in members:
        kind = _FIELD_KINDS[field]
        if not _PREDICATES[kind](value=source[field]):
            return f"normalized_input {field} {_REASONS[kind]}"
    return None
