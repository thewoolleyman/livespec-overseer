"""Authoritative assignment reads for runtime commands."""

from __future__ import annotations

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import Assignment, assignment_from_object, assignment_path
from _lpm_localstate import read_local_record
from _lpm_results import ManagerError
from _lpm_runtime_base import RuntimeHost

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "read_runtime_assignment",
]


def read_runtime_assignment(
    *, host: RuntimeHost, consumer_run_id: str
) -> Result[Assignment | None, ManagerError]:
    """Read and validate one run's live assignment."""
    path = assignment_path(state_dir=host.state_dir, consumer_run_id=consumer_run_id)
    if isinstance(path, Failure):
        return Failure(path.failure())
    stored = read_local_record(path=path.unwrap(), owner_uid=host.owner_uid)
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    if stored.unwrap() is None:
        return Success(None)
    return assignment_from_object(parsed=stored.unwrap())
