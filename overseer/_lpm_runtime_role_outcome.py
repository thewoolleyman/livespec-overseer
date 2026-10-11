"""Classify installed target-role outcomes into concrete runtime results."""

from __future__ import annotations

from typing import cast

from _lpm_results import ManagerError, retryable_exhaustion, store_unavailable
from _lpm_role_runner import RoleOutcome
from _lpm_target import IN_PROGRESS, CommitOutcome

from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = [
    "classify_role_outcome",
]


def classify_role_outcome(
    *, outcome: RoleOutcome, operation: str, cleanup_safe: bool
) -> Result[CommitOutcome, ManagerError]:
    """Keep definite pre-write refusals distinct from ambiguous target outcomes."""
    if outcome.refusal_reason is not None:
        if not outcome.launched:
            return Failure(
                store_unavailable(
                    message=f"{operation} was refused before launch",
                    cleanup_safe=cleanup_safe,
                )
            )
        return Failure(retryable_exhaustion(message=f"{operation} has an unknown target outcome"))
    if outcome.result_object["status"] == "store-unavailable":
        return Failure(
            store_unavailable(
                message=f"{operation} was unavailable before write",
                cleanup_safe=cleanup_safe,
            )
        )
    if outcome.result_object["status"] == IN_PROGRESS:
        return Failure(retryable_exhaustion(message=f"{operation} has an unknown target outcome"))
    return Success(
        CommitOutcome(
            status=str(outcome.result_object["status"]),
            committed_at=cast("str | None", outcome.result_object["committed_at"]),
        )
    )
