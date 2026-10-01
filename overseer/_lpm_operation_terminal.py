"""The exact terminal-result shapes a worker phase may carry.

SPECIFICATION/contracts.md states `terminal_result` as NULL outside a worker `terminal` or
`recovery` phase, and inside one as a closed object whose membership differs by command: an
acquire or reacquire terminal result carries exactly `outcome`, nullable canonical
`validated_at`, `published_at` and `expires_at` and a nullable `failure_reason`, while a
revalidate terminal result carries exactly `outcome`, nullable canonical `validated_at` and
a nullable `failure_kind`.

THE SUCCESS AND FAILURE FORMS ARE DISJOINT, which is the whole reason this is validated
rather than merely typed. A success MUST carry its timestamps and NO failure reason; a
failure MUST carry no timestamp at all and exactly one reason from its command's closed
set. A record that carried both would describe a credential that was simultaneously
published and rejected, and every later recovery decision reads exactly this object to
decide whether a worker's outcome is already fixed.

THE RECOVERY PHASE IS NARROWER STILL, and deliberately so. The contract fixes acquisition
and reacquisition recovery at `failure_reason` `flow-unavailable` and fenced revalidation
recovery at `failure_kind` `inconclusive` — the latter because `inconclusive` makes the
durable target state `suspect` while `rejected` would make it `dead`. Recovery runs when
nobody can say what the provider decided, so it must never write down the definitive
answer.

The ORDERING relations are inclusive where the contract says "no earlier than" and
exclusive where it says "later than": `published_at` may EQUAL `validated_at`, while a
non-null `expires_at` must be strictly later than `published_at`.
"""

from __future__ import annotations

from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_time import is_at_or_after, is_canonical_timestamp

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ACQUIRE_FAILURE_REASONS",
    "ACQUIRE_TERMINAL_MEMBERS",
    "RECOVERY_FAILURE_KIND",
    "RECOVERY_FAILURE_REASON",
    "REVALIDATE_FAILURE_KINDS",
    "REVALIDATE_TERMINAL_MEMBERS",
    "TERMINAL_OUTCOMES",
    "WORKER_RESULT_PHASES",
    "recovery_terminal_result",
    "terminal_result_defect",
]

TERMINAL_OUTCOMES: Final = ("success", "failure")
WORKER_RESULT_PHASES: Final = ("terminal", "recovery")

ACQUIRE_TERMINAL_MEMBERS: Final = (
    "outcome",
    "validated_at",
    "published_at",
    "expires_at",
    "failure_reason",
)
REVALIDATE_TERMINAL_MEMBERS: Final = (
    "outcome",
    "validated_at",
    "failure_kind",
)

ACQUIRE_FAILURE_REASONS: Final = ("provider-rejected", "flow-unavailable", "step-limit")
REVALIDATE_FAILURE_KINDS: Final = ("rejected", "inconclusive")

RECOVERY_FAILURE_REASON: Final = "flow-unavailable"
RECOVERY_FAILURE_KIND: Final = "inconclusive"

_OUTSIDE_WORKER_PHASE: Final = (
    "terminal_result must be null outside a worker terminal or recovery phase"
)


def recovery_terminal_result(*, command: str) -> dict[str, object]:
    """The one failure form a `recovery` phase of `command` may carry.

    Built here rather than at each call site so the recovery rewrite cannot install a
    shape its own validator would then reject.
    """
    if command == "revalidate":
        return {"outcome": "failure", "validated_at": None, "failure_kind": RECOVERY_FAILURE_KIND}
    return {
        "outcome": "failure",
        "validated_at": None,
        "published_at": None,
        "expires_at": None,
        "failure_reason": RECOVERY_FAILURE_REASON,
    }


def terminal_result_defect(*, command: str, phase: str, terminal_result: object) -> str | None:
    """A secret-free reason `terminal_result` is not `command`'s form for `phase`.

    Only the three worker commands have a `terminal` or `recovery` phase at all, so the
    phase name alone decides whether a result is permitted; the command decides which of
    the two membership lists applies.
    """
    if phase not in WORKER_RESULT_PHASES:
        return None if terminal_result is None else _OUTSIDE_WORKER_PHASE
    if not isinstance(terminal_result, dict):
        return f"a {phase} phase must carry its command's terminal-result object"
    source = cast("dict[str, object]", terminal_result)
    membership = _membership_defect(command=command, source=source)
    if membership is not None:
        return membership
    shape = _outcome_defect(command=command, phase=phase, source=source)
    if shape is not None:
        return shape
    return _recovery_reason_defect(command=command, phase=phase, source=source)


def _membership_defect(*, command: str, source: dict[str, object]) -> str | None:
    members = REVALIDATE_TERMINAL_MEMBERS if command == "revalidate" else ACQUIRE_TERMINAL_MEMBERS
    if sorted(source) != sorted(members):
        return f"terminal_result must contain exactly {', '.join(members)}"
    return None


def _outcome_defect(*, command: str, phase: str, source: dict[str, object]) -> str | None:
    outcome = source["outcome"]
    if outcome not in TERMINAL_OUTCOMES:
        return "outcome must be success or failure"
    if phase == "recovery" and outcome != "failure":
        return "a recovery phase must carry its command's failure terminal result"
    if command == "revalidate":
        return _revalidate_defect(source=source, outcome=outcome)
    return _acquire_defect(source=source, outcome=outcome)


def _acquire_defect(*, source: dict[str, object], outcome: object) -> str | None:
    if outcome == "success":
        return _acquire_success_defect(source=source)
    for member in ("validated_at", "published_at", "expires_at"):
        if source[member] is not None:
            return f"a failure terminal result must have null {member}"
    if source["failure_reason"] not in ACQUIRE_FAILURE_REASONS:
        return f"failure_reason must be one of {', '.join(ACQUIRE_FAILURE_REASONS)}"
    return None


def _acquire_success_defect(*, source: dict[str, object]) -> str | None:
    for member in ("validated_at", "published_at"):
        if not _is_canonical(value=source[member]):
            return f"{member} must be a UTC RFC 3339-second timestamp on success"
    if source["failure_reason"] is not None:
        return "a success terminal result carries no failure_reason"
    published_at = str(source["published_at"])
    if is_at_or_after(moment=published_at, limit=str(source["validated_at"])) is not True:
        return "published_at must be no earlier than validated_at"
    return _expiry_defect(published_at=published_at, expires_at=source["expires_at"])


def _expiry_defect(*, published_at: str, expires_at: object) -> str | None:
    if expires_at is None:
        return None
    if not _is_canonical(value=expires_at):
        return "expires_at must be null or a UTC RFC 3339-second timestamp"
    if is_at_or_after(moment=published_at, limit=str(expires_at)) is not False:
        return "expires_at must be later than published_at"
    return None


def _revalidate_defect(*, source: dict[str, object], outcome: object) -> str | None:
    if outcome == "success":
        if not _is_canonical(value=source["validated_at"]):
            return "validated_at must be a UTC RFC 3339-second timestamp on success"
        if source["failure_kind"] is not None:
            return "a success terminal result carries no failure_kind"
        return None
    if source["validated_at"] is not None:
        return "a failure terminal result must have null validated_at"
    if source["failure_kind"] not in REVALIDATE_FAILURE_KINDS:
        return f"failure_kind must be one of {', '.join(REVALIDATE_FAILURE_KINDS)}"
    return None


def _recovery_reason_defect(*, command: str, phase: str, source: dict[str, object]) -> str | None:
    if phase != "recovery":
        return None
    if command == "revalidate":
        if source["failure_kind"] != RECOVERY_FAILURE_KIND:
            return f"revalidate recovery must use failure_kind {RECOVERY_FAILURE_KIND}"
        return None
    if source["failure_reason"] != RECOVERY_FAILURE_REASON:
        return f"{command} recovery must use failure_reason {RECOVERY_FAILURE_REASON}"
    return None


def _is_canonical(*, value: object) -> bool:
    return isinstance(value, str) and is_canonical_timestamp(text=value)
