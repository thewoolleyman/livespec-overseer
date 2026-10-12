"""Identity-gated bounded validation and descriptor-only credential publication."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Protocol, cast

__all__: list[str] = [
    "CaptureCommitOutcome",
    "commit_validated_capture",
]


class IdentityInspector(Protocol):
    def __call__(self, *, account_id: str) -> object:
        """Return one closed account-identity status."""
        ...


class CaptureValidator(Protocol):
    def __call__(self, *, capture_handle: str) -> object:
        """Return one closed capture-validation status."""
        ...


class AcquisitionWriter(Protocol):
    def __call__(self, *, descriptor: int) -> object:
        """Consume a descriptor and return the value-creation acknowledgement."""
        ...


class MetadataPublisher(Protocol):
    def __call__(self, *, value_generation: int) -> None:
        """Publish metadata for one acknowledged immutable value generation."""
        ...


class BoundedSleep(Protocol):
    def __call__(self, *, seconds: int) -> None:
        """Wait between two bounded validation attempts."""
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
    sleep = cast("BoundedSleep", ports["sleep"])
    attempts = 0
    try:
        identity_failure = _identity_failure(result=inspect_identity(account_id=account_id))
        if identity_failure is not None:
            return _failure(reason=identity_failure, attempts=attempts)

        validation_status, attempts = _validation_result(
            capture_handle=capture_handle,
            validate=validate,
            sleep=sleep,
        )
        if validation_status != "success":
            return _failure(reason=validation_status, attempts=attempts)

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


def _identity_failure(*, result: object) -> str | None:
    if isinstance(result, str) and result == "matched":
        return None
    if isinstance(result, str) and result == "mismatched":
        return "provider-rejected"
    return "flow-unavailable"


def _validation_result(
    *, capture_handle: str, validate: CaptureValidator, sleep: BoundedSleep
) -> tuple[str, int]:
    attempts = 0
    for attempts, delay in enumerate((0, 1, 2), start=1):
        if delay:
            sleep(seconds=delay)
        result = validate(capture_handle=capture_handle)
        if isinstance(result, str) and result == "success":
            return "success", attempts
        if isinstance(result, str) and result == "rejected":
            return "provider-rejected", attempts
        if not isinstance(result, str) or result != "inconclusive":
            return "flow-unavailable", attempts
    return "flow-unavailable", attempts


def _write_through_pipe(*, capture: bytearray, acquisition_writer: AcquisitionWriter) -> object:
    read_descriptor, write_descriptor = os.pipe()
    transferred = [0]
    producer = threading.Thread(
        target=_produce_capture,
        kwargs={
            "descriptor": write_descriptor,
            "capture": capture,
            "transferred": transferred,
        },
    )
    producer.start()
    try:
        acknowledgement = acquisition_writer(descriptor=read_descriptor)
    finally:
        os.close(read_descriptor)
        producer.join()
    if transferred[0] != len(capture):
        return None
    return acknowledgement


def _produce_capture(*, descriptor: int, capture: bytearray, transferred: list[int]) -> None:
    view = memoryview(capture)
    try:
        while transferred[0] < len(view):
            chunk = view[transferred[0] :]
            try:
                transferred[0] += os.write(descriptor, chunk)
            finally:
                chunk.release()
    except OSError:
        return
    finally:
        view.release()
        os.close(descriptor)


def _failure(*, reason: str, attempts: int) -> CaptureCommitOutcome:
    return CaptureCommitOutcome(
        status="failed",
        failure_reason=reason,
        validation_attempts=attempts,
    )
