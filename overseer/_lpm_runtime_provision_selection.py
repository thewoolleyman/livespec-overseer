"""Reconstruct the exact selection retained by an interrupted provision."""

from __future__ import annotations

from collections.abc import Callable

from _lpm_assignment import Assignment
from _lpm_engine_context import SelectedCredential
from _lpm_operation import OperationRecord
from _lpm_results import ManagerError

from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = [
    "cleanup_selection",
    "fresh_selection",
    "recovered_selection",
]


def fresh_selection(
    *,
    first_now: str,
    select_at: Callable[[str], Result[SelectedCredential, ManagerError]],
    create_operation: Callable[[], Result[OperationRecord, ManagerError]],
) -> Result[tuple[OperationRecord, SelectedCredential], ManagerError]:
    """Select at the operation's durable acceptance instant."""
    selected = select_at(first_now)
    if isinstance(selected, Failure):
        return selected
    created = create_operation()
    if isinstance(created, Failure):
        return created
    operation = created.unwrap()
    if operation.accepted_at == first_now:
        return Success((operation, selected.unwrap()))
    return select_at(operation.accepted_at).map(lambda current: (operation, current))


def cleanup_selection(
    *,
    assignment: Assignment | None,
    assignment_selection: Callable[[Assignment], SelectedCredential],
    retained_selection: Callable[[], Result[SelectedCredential, ManagerError]],
) -> Result[SelectedCredential, ManagerError]:
    """Retain the prepared assignment or recover the exact committed lease."""
    if assignment is not None:
        return Success(assignment_selection(assignment))
    return retained_selection()


def recovered_selection(
    *,
    assignment: Assignment | None,
    completed_step: int,
    assignment_selection: Callable[[Assignment], SelectedCredential],
    fresh_selection: Callable[[], Result[SelectedCredential, ManagerError]],
    retained_selection: Callable[[], Result[SelectedCredential, ManagerError]],
) -> Result[SelectedCredential, ManagerError]:
    """Use only state that could have committed at the interrupted step."""
    if assignment is not None:
        return Success(assignment_selection(assignment))
    if completed_step < 0:
        return fresh_selection()
    return retained_selection()
