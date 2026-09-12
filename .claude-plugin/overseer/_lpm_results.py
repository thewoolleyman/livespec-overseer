"""The closed manager result vocabulary for `llm-provider-manager`.

SPECIFICATION/contracts.md closes both the
`error_type` set and its exit-status mapping: a failure emits exactly
``{"version":1,"status":"error","error_type":"<type>","message":"<redacted>"}`` with no
additional field, and exit `0` means success, `2` `invalid-request` or `invalid-report`,
`3` `retryable-exhaustion`, `4` `store-unavailable`, `5` `provisioning-failed` and `70`
`internal-bug`.

Both halves live HERE, once, because the contract's pre-access rules are stated as
"return <type> with exit <n> BEFORE the first dependent action". A caller that spells the
pair itself can drift on either half, and a drifted exit status is invisible to a test
that only inspects the JSON object — the consumer contract reads the status, not the
body. Every refusal in this operation therefore carries a `ManagerError` and asks this
module for its exit status.

`message` is a REDACTED, secret-free diagnostic by construction of every caller: no raw
credential, login, mailbox or backend token value may reach a manager result. This module
cannot enforce that (it receives an already-built string), so it deliberately does not
pretend to — it carries the value and fixes the SHAPE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__: list[str] = [
    "ERROR_STATUS",
    "EXIT_STATUS_BY_ERROR_TYPE",
    "INTERNAL_BUG",
    "INVALID_REPORT",
    "INVALID_REQUEST",
    "PROVISIONING_FAILED",
    "RESULT_VERSION",
    "RETRYABLE_EXHAUSTION",
    "STORE_UNAVAILABLE",
    "SUCCESS_EXIT_STATUS",
    "ManagerError",
    "error_object",
    "exit_status_for",
    "internal_bug",
    "invalid_request",
    "store_unavailable",
]

RESULT_VERSION: Final = 1
ERROR_STATUS: Final = "error"

INVALID_REQUEST: Final = "invalid-request"
INVALID_REPORT: Final = "invalid-report"
RETRYABLE_EXHAUSTION: Final = "retryable-exhaustion"
STORE_UNAVAILABLE: Final = "store-unavailable"
PROVISIONING_FAILED: Final = "provisioning-failed"
INTERNAL_BUG: Final = "internal-bug"

SUCCESS_EXIT_STATUS: Final = 0

EXIT_STATUS_BY_ERROR_TYPE: Final[dict[str, int]] = {
    INVALID_REQUEST: 2,
    INVALID_REPORT: 2,
    RETRYABLE_EXHAUSTION: 3,
    STORE_UNAVAILABLE: 4,
    PROVISIONING_FAILED: 5,
    INTERNAL_BUG: 70,
}


@dataclass(frozen=True, kw_only=True)
class ManagerError:
    """One typed, secret-free manager failure: its closed `error_type` and message."""

    error_type: str
    message: str


def exit_status_for(*, error_type: str) -> int:
    """The contract's exit status for `error_type`.

    An unregistered spelling maps to `internal-bug`'s `70` rather than to a plausible
    neighbour. A type this table does not know is a BUG in the caller, and `70` is the
    contract's own name for that; returning `2` would let a bug present itself to a
    consumer as an ordinary invalid request and be retried forever.
    """
    return EXIT_STATUS_BY_ERROR_TYPE.get(error_type, EXIT_STATUS_BY_ERROR_TYPE[INTERNAL_BUG])


def error_object(*, error: ManagerError) -> dict[str, object]:
    """The exact four-member failure object; no additional field is permitted."""
    return {
        "version": RESULT_VERSION,
        "status": ERROR_STATUS,
        "error_type": error.error_type,
        "message": error.message,
    }


def invalid_request(*, message: str) -> ManagerError:
    """The pre-access refusal every configuration, registry and input check returns."""
    return ManagerError(error_type=INVALID_REQUEST, message=message)


def store_unavailable(*, message: str) -> ManagerError:
    """The fail-closed refusal for an unsafe local record or an unusable backend."""
    return ManagerError(error_type=STORE_UNAVAILABLE, message=message)


def internal_bug(*, message: str) -> ManagerError:
    """The refusal for a condition no contract branch admits."""
    return ManagerError(error_type=INTERNAL_BUG, message=message)
