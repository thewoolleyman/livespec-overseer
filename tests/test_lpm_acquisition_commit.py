"""Validated captures cross only the acquisition-writer descriptor boundary."""

from __future__ import annotations

import importlib
import os
from pathlib import Path


def _run(*, commit, identity, probes, writer_status="committed"):
    capture = bytearray(b"synthetic-provider-credential")
    events: list[object] = []
    outcomes = iter(probes)

    def inspect_identity(*, account_id):
        events.append(("identity", account_id))
        return identity

    def validate(*, capture_handle):
        events.append(("validate", capture_handle))
        return next(outcomes)

    def writer(*, descriptor):
        events.append(("writer", os.read(descriptor, 4096)))
        return writer_status

    def publish(*, value_generation):
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


def test_identity_validation_descriptor_transfer_and_publication_are_ordered():
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_acquisition_commit.py"
    assert module_path.is_file(), "the isolated capture commit boundary must be implemented"
    commit = importlib.import_module("_lpm_acquisition_commit")

    mismatched = _run(commit=commit, identity="mismatched", probes=())
    assert mismatched[0].failure_reason == "provider-rejected"
    assert mismatched[1] == bytearray()
    assert mismatched[2] == [("identity", "account-1")]

    unavailable = _run(commit=commit, identity="unavailable", probes=())
    assert unavailable[0].failure_reason == "flow-unavailable"
    assert unavailable[1] == bytearray()

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

    uncommitted = _run(
        commit=commit, identity="matched", probes=("success",), writer_status="uncommitted"
    )
    assert uncommitted[0].failure_reason == "flow-unavailable"
    assert all(event[0] != "publish" for event in uncommitted[2])

    succeeded = _run(commit=commit, identity="matched", probes=("success",))
    assert succeeded[0].status == "success"
    assert succeeded[0].failure_reason is None
    assert succeeded[1] == bytearray()
    assert succeeded[2][-2:] == [
        ("writer", b"synthetic-provider-credential"),
        ("publish", 7),
    ]
    assert "synthetic-provider-credential" not in repr(succeeded[0])
