"""Identity-gated bounded validation and descriptor-only credential publication."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, cast

__all__: list[str] = [
    "CaptureCommitOutcome",
    "commit_validated_capture",
]


class IdentityInspector(Protocol):
    def __call__(self, *, account_id: str) -> str:
        """Return only matched, mismatched or unavailable."""
        ...


class CaptureValidator(Protocol):
    def __call__(self, *, capture_handle: str) -> str:
        """Return only success, rejected or inconclusive."""
        ...


class AcquisitionWriter(Protocol):
    def __call__(self, *, descriptor: int) -> str:
        """Consume a descriptor and return the value-creation acknowledgement."""
        ...


class MetadataPublisher(Protocol):
    def __call__(self, *, value_generation: int) -> None:
        """Publish metadata for one acknowledged immutable value generation."""
        ...


@dataclass(frozen=True, kw_only=True)
class CaptureCommitOutcome:
    """Secret-free terminal result of committing one service-private capture."""

    status: str
    failure_reason: str | None
    validation_attempts: int


def commit_validated_capture(
    *,
    capture: bytearray,
    capture_handle: str,
    account_id: str,
    value_generation: int,
    **ports: object,
) -> CaptureCommitOutcome:
    """Validate, descriptor-transfer, acknowledge, then publish without returning bytes."""
    inspect_identity = cast("IdentityInspector", ports["inspect_identity"])
    validate = cast("CaptureValidator", ports["validate"])
    acquisition_writer = cast("AcquisitionWriter", ports["acquisition_writer"])
    publish_metadata = cast("MetadataPublisher", ports["publish_metadata"])
    sleep = cast("Callable[[int], None]", ports["sleep"])
    attempts = 0
    try:
        identity = inspect_identity(account_id=account_id)
        identity_failure = {
            "mismatched": "provider-rejected",
            "unavailable": "flow-unavailable",
        }.get(identity)
        if identity_failure is not None:
            return _failure(reason=identity_failure, attempts=attempts)
        validation = "inconclusive"
        for delay in (0, 1, 2):
            if delay:
                sleep(delay)
            attempts += 1
            validation = validate(capture_handle=capture_handle)
            if validation != "inconclusive":
                break
        validation_failure = {
            "rejected": "provider-rejected",
            "inconclusive": "flow-unavailable",
        }.get(validation)
        if validation_failure is not None:
            return _failure(reason=validation_failure, attempts=attempts)
        acknowledgement = _write_through_pipe(
            capture=capture,
            acquisition_writer=acquisition_writer,
        )
        if acknowledgement != "committed":
            return _failure(reason="flow-unavailable", attempts=attempts)
        publish_metadata(value_generation=value_generation)
        return CaptureCommitOutcome(
            status="success",
            failure_reason=None,
            validation_attempts=attempts,
        )
    finally:
        capture.clear()


def _write_through_pipe(*, capture: bytearray, acquisition_writer: AcquisitionWriter) -> str:
    read_descriptor, write_descriptor = os.pipe()
    try:
        _ = os.write(write_descriptor, capture)
    finally:
        os.close(write_descriptor)
    try:
        return acquisition_writer(descriptor=read_descriptor)
    finally:
        os.close(read_descriptor)


def _failure(*, reason: str, attempts: int) -> CaptureCommitOutcome:
    return CaptureCommitOutcome(
        status="failed",
        failure_reason=reason,
        validation_attempts=attempts,
    )
