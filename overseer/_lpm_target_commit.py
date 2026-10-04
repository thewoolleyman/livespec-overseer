"""The durable record of one adapter target commit, and the instant it landed at.

SPECIFICATION/contracts.md requires `assignment-commit` to "record the adapter-supplied
target commit time", and it requires provision `start` to transition to `postcommit` AFTER a
committed target — which puts the commit instant across a PHASE BOUNDARY from the effect that
stores it in the assignment. `start`'s `target-write` learns it from the adapter; `postcommit`'s
`assignment-commit`, which may run in a different process after a crash, has to be able to
find it again.

SO THE INSTANT IS PERSISTED, AND THAT IS WHAT MAKES THE PHASE BOUNDARY SURVIVABLE. Without
this record the only way a recovered `postcommit` could obtain a commit time would be to
re-sample a clock, which would move `target_committed_at` on every replay — and with it the
assignment's own validity window, `normalized_close_time`, the tombstone's times and the
rollout-start minimum. Each of those is specified against a FIXED instant, so a re-sampled one
is not a smaller error than a wrong one; it is the same error arriving later.

IT IS ALSO `target-write`'S OWN POSTCONDITION. The destination bytes cannot answer "did THIS
operation's write commit?" — a byte-identical value could have been placed there by the
previous generation, and reading the destination back is not permitted to stand in for a
commit acknowledgement. The presence of this record for this reference, naming this run,
record and generation, is the authoritative answer, so a replay settles the position instead
of writing the credential a second time.

THE RECORD CARRIES A REFERENCE AND NEVER A VALUE, exactly as the assignment and the tombstone
do. `value_generation` identifies WHICH generation was placed; the bytes themselves live only
at the destination the adapter owns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_record import is_uuid4
from _lpm_results import ManagerError, store_unavailable
from _lpm_time import is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "TARGET_COMMIT_MEMBERS",
    "TARGET_COMMIT_VERSION",
    "TargetCommit",
    "target_commit_from_object",
    "target_commit_object",
]

TARGET_COMMIT_VERSION: Final = 1
TARGET_COMMIT_MEMBERS: Final = (
    "version",
    "target_ref",
    "consumer_run_id",
    "record_id",
    "value_generation",
    "committed_at",
)

_UUID_MEMBERS: Final = ("record_id", "value_generation")
_TEXT_MEMBERS: Final = ("target_ref", "consumer_run_id")


@dataclass(frozen=True, kw_only=True)
class TargetCommit:
    """One committed target write: which generation landed where, and when."""

    target_ref: str
    consumer_run_id: str
    record_id: str
    value_generation: str
    committed_at: str


def target_commit_object(*, commit: TargetCommit) -> dict[str, object]:
    """The exact six-member mapping, built from the declared member list."""
    values: dict[str, object] = {"version": TARGET_COMMIT_VERSION}
    for member in TARGET_COMMIT_MEMBERS[1:]:
        values[member] = getattr(commit, member)
    return values


def target_commit_from_object(*, parsed: object) -> Result[TargetCommit, ManagerError]:
    """Validate one decoded target-commit record; an unusable one is `store-unavailable`."""
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="a target commit must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    defect = _defect(source=source)
    if defect is not None:
        return Failure(store_unavailable(message=defect))
    return Success(
        TargetCommit(
            target_ref=str(source["target_ref"]),
            consumer_run_id=str(source["consumer_run_id"]),
            record_id=str(source["record_id"]),
            value_generation=str(source["value_generation"]),
            committed_at=str(source["committed_at"]),
        )
    )


def _defect(*, source: dict[str, object]) -> str | None:
    if sorted(source) != sorted(TARGET_COMMIT_MEMBERS):
        return f"a target commit must contain exactly {', '.join(TARGET_COMMIT_MEMBERS)}"
    version = source["version"]
    if isinstance(version, bool) or version != TARGET_COMMIT_VERSION:
        return "a target commit version must be the integer 1"
    for member in _TEXT_MEMBERS:
        value = source[member]
        if not isinstance(value, str) or value == "":
            return f"a target commit {member} must be a non-empty string"
    for member in _UUID_MEMBERS:
        value = source[member]
        if not isinstance(value, str) or not is_uuid4(value=value):
            return f"a target commit {member} must be a lowercase RFC 4122 UUIDv4"
    committed_at = source["committed_at"]
    if not isinstance(committed_at, str) or not is_canonical_timestamp(text=committed_at):
        return "a target commit committed_at must be a UTC RFC 3339-second timestamp"
    return None
