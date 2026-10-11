"""Closed input validation for final-provisioning and target-status roles."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, cast

from _lpm_onepassword import value_ref
from _lpm_record import is_uuid4
from _lpm_time import is_canonical_timestamp

__all__: list[str] = [
    "valid_target_role_request",
]

_FINAL_MEMBERS: Final = frozenset(
    {
        "version",
        "target_ref",
        "consumer_run_id",
        "record_id",
        "value_generation",
        "value_ref",
        "lease_expires_at",
        "external_call_timeout_seconds",
        "op_executable",
    }
)
_STATUS_MEMBERS: Final = frozenset({"version", "target_ref", "consumer_run_id", "value_generation"})


def valid_target_role_request(*, role_name: str, members: Mapping[str, object]) -> bool:
    """Validate the exact role shape and relations before any state access."""
    expected = {
        "final-provisioning": _FINAL_MEMBERS,
        "target-status": _STATUS_MEMBERS,
    }.get(role_name)
    if expected is None or frozenset(members) != expected:
        return False
    version = members["version"]
    if isinstance(version, bool) or version != 1:
        return False
    for name in ("target_ref", "consumer_run_id", "value_generation"):
        value = members[name]
        if not isinstance(value, str) or value == "":
            return False
    generation = cast("str", members["value_generation"])
    if not is_uuid4(value=generation):
        return False
    if role_name == "target-status":
        return True
    return _valid_final_members(members=members)


def _valid_final_members(*, members: Mapping[str, object]) -> bool:
    record_id = members["record_id"]
    value_generation = cast("str", members["value_generation"])
    reference = members["value_ref"]
    expires_at = members["lease_expires_at"]
    timeout = members["external_call_timeout_seconds"]
    executable = members["op_executable"]
    if not isinstance(record_id, str) or not is_uuid4(value=record_id):
        return False
    if not isinstance(reference, str) or reference != value_ref(
        record_id=record_id, value_generation=value_generation
    ):
        return False
    if not isinstance(expires_at, str) or not is_canonical_timestamp(text=expires_at):
        return False
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        return False
    return isinstance(executable, str) and executable != ""
