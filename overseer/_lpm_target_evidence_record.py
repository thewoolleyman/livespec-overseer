"""Closed target-evidence record decoding, separate from filesystem reconciliation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, cast

from _lpm_record import is_uuid4
from _lpm_results import ManagerError, store_unavailable
from _lpm_time import is_at_or_after, is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = [
    "TARGET_EVIDENCE_MEMBERS",
    "TargetEvidence",
    "target_evidence_from_object",
]

TARGET_EVIDENCE_MEMBERS: Final = (
    "version",
    "status",
    "target_ref",
    "consumer_run_id",
    "value_generation",
    "target_sha256",
    "prepared_at",
    "committed_at",
)
_STATUSES: Final = ("prepared", "armed", "committed")
_SHA256_PATTERN: Final = re.compile(r"\A[0-9a-f]{64}\Z")


@dataclass(frozen=True, kw_only=True)
class TargetEvidence:
    status: str
    target_ref: str
    consumer_run_id: str
    value_generation: str
    target_sha256: str
    prepared_at: str
    committed_at: str | None


def target_evidence_from_object(*, parsed: object) -> Result[TargetEvidence, ManagerError]:
    """Decode one exact target-evidence object without weakening its member boundary."""
    is_object = isinstance(parsed, dict)
    source = cast("dict[str, object]", parsed) if is_object else {}
    if not is_object or set(source) != set(TARGET_EVIDENCE_MEMBERS):
        messages = {
            False: "target evidence is not an object",
            True: "target evidence has the wrong shape",
        }
        return Failure(store_unavailable(message=messages[is_object]))
    defect = _evidence_defect(source=source)
    if defect is not None:
        return Failure(store_unavailable(message=defect))
    return Success(
        TargetEvidence(
            status=str(source["status"]),
            target_ref=str(source["target_ref"]),
            consumer_run_id=str(source["consumer_run_id"]),
            value_generation=str(source["value_generation"]),
            target_sha256=str(source["target_sha256"]),
            prepared_at=str(source["prepared_at"]),
            committed_at=cast("str | None", source["committed_at"]),
        )
    )


def _evidence_defect(*, source: dict[str, object]) -> str | None:
    for inspect in (
        _evidence_header_defect,
        _evidence_binding_defect,
        _evidence_time_defect,
    ):
        defect = inspect(source=source)
        if defect is not None:
            return defect
    return None


def _evidence_header_defect(*, source: dict[str, object]) -> str | None:
    version = source["version"]
    if isinstance(version, bool) or version != 1:
        return "target evidence version must be the integer 1"
    status_value = source["status"]
    if not isinstance(status_value, str) or status_value not in _STATUSES:
        return "target evidence status is invalid"
    return None


def _evidence_binding_defect(*, source: dict[str, object]) -> str | None:
    for member in ("target_ref", "consumer_run_id"):
        value = source[member]
        if not isinstance(value, str) or value == "":
            return f"target evidence {member} must be a non-empty string"
    generation = source["value_generation"]
    if not isinstance(generation, str) or not is_uuid4(value=generation):
        return "target evidence value_generation must be a lowercase UUIDv4"
    digest = source["target_sha256"]
    if not isinstance(digest, str) or _SHA256_PATTERN.match(digest) is None:
        return "target evidence target_sha256 must be a lowercase SHA-256 digest"
    return None


def _evidence_time_defect(*, source: dict[str, object]) -> str | None:
    prepared_at = source["prepared_at"]
    if not isinstance(prepared_at, str) or not is_canonical_timestamp(text=prepared_at):
        return "target evidence prepared_at must be a UTC RFC 3339-second timestamp"
    committed_at = source["committed_at"]
    if source["status"] == "prepared":
        if committed_at is not None:
            return "prepared target evidence must not carry committed_at"
        return None
    if (
        not isinstance(committed_at, str)
        or not is_canonical_timestamp(text=committed_at)
        or is_at_or_after(moment=committed_at, limit=prepared_at) is not True
    ):
        return "armed or committed evidence needs an ordered committed_at"
    return None
