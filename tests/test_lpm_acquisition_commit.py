"""Validated captures cross only the acquisition-writer descriptor boundary."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import ModuleType


def _run(
    *,
    commit: ModuleType,
    identity: object,
    probes: tuple[object, ...],
    writer_status: object = "committed",
) -> tuple[object, bytearray, list[object], list[int]]:
    capture = bytearray(b"synthetic-provider-credential")
    events: list[object] = []
    outcomes = iter(probes)

    def inspect_identity(*, account_id: str) -> object:
        events.append(("identity", account_id))
        return identity

    def validate(*, capture_handle: str) -> object:
        events.append(("validate", capture_handle))
        return next(outcomes)

    def writer(*, descriptor: int) -> object:
        events.append(("writer", os.read(descriptor, 4096)))
        return writer_status

    def publish(*, value_generation: int) -> None:
        events.append(("publish", value_generation))

    waits: list[int] = []
    result = commit.commit_validated_capture(
        capture=capture,
        capture_handle="capture:opaque",
        account_id="account-1",
        value_generation=7,
        inspect_identity=inspect_identity,
        validate=validate,
        acquisition_writer=writer,
        publish_metadata=publish,
        sleep=lambda seconds: waits.append(seconds),
    )
    return result, capture, events, waits


def _assert_identity_is_exact(*, commit: ModuleType) -> None:
    mismatched = _run(commit=commit, identity="mismatched", probes=())
    assert mismatched[0].failure_reason == "provider-rejected"
    assert mismatched[1] == bytearray()
    assert mismatched[2] == [("identity", "account-1")]

    for malformed in ("unavailable", "matched-ish", {"status": "matched"}, None):
        unavailable = _run(commit=commit, identity=malformed, probes=())
        assert unavailable[0].failure_reason == "flow-unavailable"
        assert unavailable[1] == bytearray()
        assert unavailable[2] == [("identity", "account-1")]


def _assert_validation_is_closed_and_bounded(*, commit: ModuleType) -> None:
    rejected = _run(commit=commit, identity="matched", probes=("rejected",))
    assert rejected[0].failure_reason == "provider-rejected"
    assert rejected[0].validation_attempts == 1

    inconclusive = _run(
        commit=commit,
        identity="matched",
        probes=("inconclusive", "inconclusive", "inconclusive"),
    )
    assert inconclusive[0].failure_reason == "flow-unavailable"
    assert inconclusive[0].validation_attempts == 3
    assert inconclusive[3] == [1, 2]
    assert all(event[0] != "writer" for event in inconclusive[2])

    for malformed in ("success-ish", {"status": "success"}, None):
        unavailable = _run(commit=commit, identity="matched", probes=(malformed,))
        assert unavailable[0].failure_reason == "flow-unavailable"
        assert unavailable[0].validation_attempts == 1
        assert all(event[0] != "writer" for event in unavailable[2])


def _assert_descriptor_transfer_precedes_publication(*, commit: ModuleType) -> None:
    for malformed in ("uncommitted", {"status": "committed"}, None):
        unavailable = _run(
            commit=commit,
            identity="matched",
            probes=("success",),
            writer_status=malformed,
        )
        assert unavailable[0].failure_reason == "flow-unavailable"
        assert all(event[0] != "publish" for event in unavailable[2])

    succeeded = _run(commit=commit, identity="matched", probes=("success",))
    assert succeeded[0].status == "success"
    assert succeeded[0].failure_reason is None
    assert succeeded[1] == bytearray()
    assert succeeded[2][-2:] == [
        ("writer", b"synthetic-provider-credential"),
        ("publish", 7),
    ]
    assert "synthetic-provider-credential" not in repr(succeeded[0])


def test_commit_gate_is_exact_bounded_and_descriptor_only() -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_acquisition_commit.py"
    assert module_path.is_file(), "the isolated capture commit boundary must be implemented"
    commit = importlib.import_module("_lpm_acquisition_commit")

    _assert_identity_is_exact(commit=commit)
    _assert_validation_is_closed_and_bounded(commit=commit)
    _assert_descriptor_transfer_precedes_publication(commit=commit)
