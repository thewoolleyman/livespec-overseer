"""The closed credential lifecycle: six states and the ONLY events that move them.

SPECIFICATION/spec.md states that each credential record MUST be in exactly one of `acquiring`,
`valid`, `suspect`, `revalidating`, `dead` or `reacquiring`, and that **only** the events in its
table MAY change that state. This module is that table, transcribed as data, plus the two derived
rules the prose states separately: which lifecycle state each run-scoped operation matches, and
how a run of consecutive inconclusive validation attempts resolves.

THE TABLE IS DATA BECAUSE ITS CLOSEDNESS IS THE CONTRACT. A hand-written cascade of `if`
branches expresses the same moves while quietly admitting a move nobody ratified — an
`else` that falls through to "leave it alone" reads as safe and is how a `suspect` record
becomes selectable again without a revalidation. Asking a mapping means an unlisted
`(status, event)` pair has NO answer, and the caller must decide whether that absence is a
contract no-op (a report against an already-`suspect` record) or a refusal.

THE ONE ROUTE OUT OF `suspect` TOWARD `valid` RUNS THROUGH `revalidating`. There is
deliberately no `(suspect, revalidation-succeeds)` row: a suspect credential returns to
`valid` only after a revalidation has STARTED and then succeeded, so a consumer failure
report cannot be undone by anything short of a fresh provider validation.

REVALIDATION IS SINGLE-ATTEMPT, which is why both inconclusive events land a
`revalidating` record on `suspect`. Acquisition and reacquisition get two retries and die
on the third; revalidation has no attempt ordinal to spend, so the ordinal is irrelevant
there rather than absent, and both spellings are listed so one caller cannot discover a
hole by asking with the "wrong" one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from _lpm_record import ACTIVE_STATUSES

__all__: list[str] = [
    "ACTIVE_STATE_BY_OPERATION",
    "INCONCLUSIVE_FINAL_ATTEMPT",
    "INCONCLUSIVE_FINAL_EVENT",
    "INCONCLUSIVE_RETRY_EVENT",
    "LIFECYCLE_EVENTS",
    "LIFECYCLE_TRANSITIONS",
    "NO_RECORD",
    "REPORT_EVENT",
    "REVALIDATION_STARTS_EVENT",
    "REVALIDATION_SUCCEEDS_EVENT",
    "LifecycleMove",
    "active_state_for",
    "admitted_move",
    "inconclusive_event",
    "is_active_status",
]

NO_RECORD: Final = "no-record"

REPORT_EVENT: Final = "consumer-failure-report"
REVALIDATION_STARTS_EVENT: Final = "revalidation-starts"
REVALIDATION_SUCCEEDS_EVENT: Final = "revalidation-succeeds"
INCONCLUSIVE_RETRY_EVENT: Final = "validation-inconclusive-retry"
INCONCLUSIVE_FINAL_EVENT: Final = "validation-inconclusive-final"

INCONCLUSIVE_FINAL_ATTEMPT: Final = 3

LIFECYCLE_EVENTS: Final = (
    "acquisition-starts",
    "acquisition-succeeds",
    "acquisition-fails",
    "acquisition-worker-lost",
    "acquisition-fence-recovery",
    INCONCLUSIVE_RETRY_EVENT,
    INCONCLUSIVE_FINAL_EVENT,
    REPORT_EVENT,
    REVALIDATION_STARTS_EVENT,
    REVALIDATION_SUCCEEDS_EVENT,
    "revalidation-rejects",
    "revalidation-worker-lost",
    "revalidation-fence-recovery",
    "credential-expires",
    "operator-reacquires",
    "replacement-starts",
)

LIFECYCLE_TRANSITIONS: Final[dict[tuple[str, str], str]] = {
    (NO_RECORD, "acquisition-starts"): "acquiring",
    ("acquiring", "acquisition-succeeds"): "valid",
    ("acquiring", "acquisition-fails"): "dead",
    ("acquiring", "acquisition-worker-lost"): "dead",
    ("acquiring", INCONCLUSIVE_RETRY_EVENT): "acquiring",
    ("acquiring", INCONCLUSIVE_FINAL_EVENT): "dead",
    ("valid", REPORT_EVENT): "suspect",
    ("valid", REVALIDATION_STARTS_EVENT): "revalidating",
    ("valid", "credential-expires"): "dead",
    ("valid", "acquisition-fence-recovery"): "dead",
    ("valid", "revalidation-fence-recovery"): "suspect",
    ("suspect", REVALIDATION_STARTS_EVENT): "revalidating",
    ("suspect", "operator-reacquires"): "reacquiring",
    ("suspect", "credential-expires"): "dead",
    ("revalidating", REPORT_EVENT): "suspect",
    ("revalidating", REVALIDATION_SUCCEEDS_EVENT): "valid",
    ("revalidating", "revalidation-rejects"): "dead",
    ("revalidating", "revalidation-worker-lost"): "suspect",
    ("revalidating", "credential-expires"): "dead",
    ("revalidating", INCONCLUSIVE_RETRY_EVENT): "suspect",
    ("revalidating", INCONCLUSIVE_FINAL_EVENT): "suspect",
    ("dead", "replacement-starts"): "reacquiring",
    ("reacquiring", "acquisition-succeeds"): "valid",
    ("reacquiring", "acquisition-fails"): "dead",
    ("reacquiring", "acquisition-worker-lost"): "dead",
    ("reacquiring", INCONCLUSIVE_RETRY_EVENT): "reacquiring",
    ("reacquiring", INCONCLUSIVE_FINAL_EVENT): "dead",
}

ACTIVE_STATE_BY_OPERATION: Final[dict[str, str]] = {
    "acquire": "acquiring",
    "reacquire": "reacquiring",
    "revalidate": "revalidating",
}


@dataclass(frozen=True, kw_only=True)
class LifecycleMove:
    """One ratified move: the state it starts in, what happened, where it lands."""

    status: str
    event: str
    next_status: str


def admitted_move(*, status: str, event: str) -> LifecycleMove | None:
    """The ratified move for this pair, or None when the table admits none.

    None is NOT "nothing happened". It says this event does not change that state, and
    the caller owns what that means: a consumer report against an already-`suspect`
    record is a contract no-op, while an acquisition success against a `dead` record is a
    condition no branch admits.
    """
    landing = LIFECYCLE_TRANSITIONS.get((status, event))
    if landing is None:
        return None
    return LifecycleMove(status=status, event=event, next_status=landing)


def inconclusive_event(*, consecutive_attempts: int) -> str:
    """Which inconclusive event a run of `consecutive_attempts` raises.

    The contract counts CONSECUTIVE inconclusive validation attempts and kills an
    acquisition on the third; the count lives with its caller, and the mapping from count
    to event lives here so the third-attempt boundary is spelled once.
    """
    if consecutive_attempts >= INCONCLUSIVE_FINAL_ATTEMPT:
        return INCONCLUSIVE_FINAL_EVENT
    return INCONCLUSIVE_RETRY_EVENT


def is_active_status(*, status: str) -> bool:
    """Whether `status` is one of the three ACTIVE lifecycle states."""
    return status in ACTIVE_STATUSES


def active_state_for(*, operation: str) -> str | None:
    """The lifecycle state matching one run-scoped operation, or None when unregistered."""
    return ACTIVE_STATE_BY_OPERATION.get(operation)
