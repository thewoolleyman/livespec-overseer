"""The assignment record a successful provision leaves behind, and its report-marker array.

SPECIFICATION/contracts.md states the record exactly: "An assignment record MUST contain
exactly `version` (integer `1`), `status` (`prepared` or `committed`), `request`, non-empty
`target_ref`, `account_id`, `value_generation` and `value_ref`, lowercase RFC 4122 UUIDv4
`record_id`, `receipt`, UTC RFC 3339-second `lease_started_at` and `lease_expires_at`,
nullable UTC RFC 3339-second `target_committed_at` and `actual_lease_ended_at`,
`report_markers` and nullable `completion`." And of the array: "`report_markers` MUST be an
array of unique objects containing exactly UTC RFC 3339-second `occurred_at` and a
`classification` from the report's closed set, sorted by `occurred_at` and then by the UTF-8
bytes of `classification`."

WHY THIS RECORD IS WHAT MAKES `report` IDEMPOTENT. `report` must answer `duplicate` for a
report it has already accepted, and `_lpm_reports.stored_marker` answers that question given
the markers already recorded — but nothing in the package RECORDED them, so there was no
state for it to consult and no way for the manager to be idempotent across processes. The
marker array on this record is that state, and `with_marker` is the only writer of it.

THE SORT AND THE UNIQUENESS ARE THE WHOLE POINT OF THE ARRAY, not decoration. Two reports
that differ only in arrival order must produce byte-identical records, or a later exact-match
check is comparing against a record whose contents depend on history rather than on facts.
The easy wrong implementation appends and never sorts, which passes any test that reports in
ascending order and fails silently the first time a retry arrives out of order.

ABSENCE IS NOT UNAVAILABILITY HERE EITHER. A `consumer_run_id` this manager never issued an
assignment for reads as `None`, which is a fact about that run; a record that exists and
cannot be trusted is `store-unavailable`. `report` needs the two apart to answer
`invalid-report` for an unknown run rather than blaming the store.
"""

from __future__ import annotations

import importlib
import json
import os
import pathlib
from typing import Any

import pytest

__all__: list[str] = []

ASSIGNMENT_PATH = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_assignment.py"
MARKERS_PATH = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_report_markers.py"

_RUN = "run-1"
_RECORD_ID = "d1f0c2a4-8b6e-4c1a-9f3d-0e7a5b2c4d69"
_GENERATION = "9b3e7c51-0a2d-4f68-b1c4-7e5a2d9f06b8"
_STARTED = "2026-09-30T20:00:00Z"
_EXPIRES = "2026-10-01T02:00:00Z"
_COMMITTED = "2026-09-30T20:00:01Z"


def _assignment_module() -> Any:
    assert ASSIGNMENT_PATH.is_file(), "overseer/_lpm_assignment.py must exist"
    return importlib.import_module("_lpm_assignment")


def _markers_module() -> Any:
    assert MARKERS_PATH.is_file(), "overseer/_lpm_report_markers.py must exist"
    return importlib.import_module("_lpm_report_markers")


def _marker(*, occurred_at: str, classification: str) -> Any:
    from _lpm_reports import ReportMarker

    return ReportMarker(occurred_at=occurred_at, classification=classification)


def _request_object() -> dict[str, object]:
    return {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "consumer_run_id": _RUN,
        "target_ref": "ref-1",
        "strategy": "consume-first",
        "lease_seconds": 21600,
    }


def _receipt_object() -> dict[str, object]:
    return {
        "record_id": _RECORD_ID,
        "account_id": "acct-1",
        "validated_at": _STARTED,
        "purpose": "factory",
        "lease_expires_at": _EXPIRES,
    }


def _stored(**overrides: object) -> dict[str, object]:
    stored: dict[str, object] = {
        "version": 1,
        "status": "committed",
        "request": _request_object(),
        "target_ref": "ref-1",
        "account_id": "acct-1",
        "value_generation": _GENERATION,
        "value_ref": f"op://LPM Values/{_RECORD_ID}.{_GENERATION}/credential",
        "record_id": _RECORD_ID,
        "receipt": _receipt_object(),
        "lease_started_at": _STARTED,
        "lease_expires_at": _EXPIRES,
        "target_committed_at": _COMMITTED,
        "actual_lease_ended_at": None,
        "report_markers": [],
        "completion": None,
    }
    stored.update(overrides)
    return stored


def _decoded(*, stored: object) -> Any:
    outcome = _assignment_module().assignment_from_object(parsed=stored)
    assert not isinstance(outcome, _failure_type()), f"{stored!r} must decode"
    return outcome.unwrap()


def _refused(*, stored: object) -> Any:
    outcome = _assignment_module().assignment_from_object(parsed=stored)
    assert isinstance(outcome, _failure_type()), f"{stored!r} must be refused"
    return outcome.failure()


def _failure_type() -> Any:
    from overseer._vendor.returns.result import Failure

    return Failure


def test_the_assignment_member_table_is_exactly_the_ratified_one() -> None:
    module = _assignment_module()

    assert module.ASSIGNMENT_MEMBERS == (
        "version",
        "status",
        "request",
        "target_ref",
        "account_id",
        "value_generation",
        "value_ref",
        "record_id",
        "receipt",
        "lease_started_at",
        "lease_expires_at",
        "target_committed_at",
        "actual_lease_ended_at",
        "report_markers",
        "completion",
    )
    assert module.ASSIGNMENT_STATUSES == ("prepared", "committed")
    assert module.COMMITTED_ASSIGNMENT == "committed"
    assert module.PREPARED_ASSIGNMENT == "prepared"


def test_the_marker_member_table_is_exactly_the_ratified_one() -> None:
    assert _markers_module().REPORT_MARKER_MEMBERS == ("occurred_at", "classification")


def test_a_record_round_trips_through_its_object_form_unchanged() -> None:
    stored = _stored()

    encoded = _assignment_module().assignment_object(assignment=_decoded(stored=stored))

    assert encoded == stored


def test_the_encoded_form_carries_exactly_the_declared_members() -> None:
    encoded = _assignment_module().assignment_object(assignment=_decoded(stored=_stored()))

    assert sorted(encoded) == sorted(_assignment_module().ASSIGNMENT_MEMBERS)


@pytest.mark.parametrize(
    "stored",
    [
        ["not", "an", "object"],
        _stored(version=2),
        _stored(version=True),
        _stored(status="withdrawn"),
        _stored(record_id="D1F0C2A4-8B6E-4C1A-9F3D-0E7A5B2C4D69"),
        _stored(value_generation="not-a-uuid"),
        _stored(target_ref=""),
        _stored(account_id=""),
        _stored(value_ref=""),
        _stored(value_ref=7),
        _stored(lease_started_at="2026-09-30 20:00:00"),
        _stored(lease_expires_at=None),
        _stored(target_committed_at="yesterday"),
        _stored(actual_lease_ended_at="yesterday"),
        _stored(request={"version": 1}),
        _stored(request="not-an-object"),
        _stored(receipt={"record_id": _RECORD_ID}),
        _stored(receipt="not-an-object"),
        _stored(receipt={**_receipt_object(), "account_id": ""}),
        _stored(receipt={**_receipt_object(), "record_id": "nope"}),
        _stored(receipt={**_receipt_object(), "validated_at": "nope"}),
        _stored(report_markers="not-an-array"),
        _stored(report_markers=["not-an-object"]),
        _stored(report_markers=[{"occurred_at": _STARTED}]),
        _stored(report_markers=[{"occurred_at": _STARTED, "classification": "nonsense"}]),
        _stored(report_markers=[{"occurred_at": "nope", "classification": "unknown"}]),
        _stored(
            report_markers=[
                {"occurred_at": _STARTED, "classification": "unknown"},
                {"occurred_at": _STARTED, "classification": "unknown"},
            ]
        ),
        _stored(
            report_markers=[
                {"occurred_at": _EXPIRES, "classification": "unknown"},
                {"occurred_at": _STARTED, "classification": "unknown"},
            ]
        ),
        _stored(completion="not-an-object-or-null"),
        {"version": 1, "status": "committed"},
    ],
)
def test_a_nonconforming_record_is_store_unavailable(*, stored: object) -> None:
    assert _refused(stored=stored).error_type == "store-unavailable"


def test_a_prepared_record_with_no_commit_time_is_conforming() -> None:
    decoded = _decoded(stored=_stored(status="prepared", target_committed_at=None))

    assert decoded.status == "prepared"
    assert decoded.target_committed_at is None


def test_a_stored_completion_object_is_carried_through_opaquely() -> None:
    completion = {"version": 1, "consumer_run_id": _RUN}

    decoded = _decoded(stored=_stored(completion=completion))

    assert decoded.completion == completion


def test_markers_are_sorted_by_occurred_at_then_classification_bytes() -> None:
    module = _markers_module()
    unsorted = [
        _marker(occurred_at=_EXPIRES, classification="unknown"),
        _marker(occurred_at=_STARTED, classification="rate-limit"),
        _marker(occurred_at=_STARTED, classification="authentication"),
    ]

    ordered = module.sorted_markers(markers=unsorted)

    assert [(marker.occurred_at, marker.classification) for marker in ordered] == [
        (_STARTED, "authentication"),
        (_STARTED, "rate-limit"),
        (_EXPIRES, "unknown"),
    ]


def test_appending_a_marker_keeps_the_array_sorted_and_unique() -> None:
    module = _markers_module()
    first = _marker(occurred_at=_EXPIRES, classification="unknown")
    second = _marker(occurred_at=_STARTED, classification="authentication")

    once = module.markers_with(markers=(first,), marker=second)
    twice = module.markers_with(markers=once, marker=second)

    assert [marker.occurred_at for marker in once] == [_STARTED, _EXPIRES]
    assert twice == once


def test_appending_a_marker_to_an_assignment_rewrites_only_its_array() -> None:
    module = _assignment_module()
    assignment = _decoded(stored=_stored())
    marker = _marker(occurred_at=_COMMITTED, classification="authentication")

    updated = module.with_marker(assignment=assignment, marker=marker)

    assert updated.report_markers == (marker,)
    assert assignment.report_markers == ()
    assert module.assignment_object(assignment=updated)["report_markers"] == [
        {"occurred_at": _COMMITTED, "classification": "authentication"}
    ]


def test_a_run_with_no_assignment_reads_as_absent(tmp_path: pathlib.Path) -> None:
    outcome = _assignment_module().read_assignment(
        state_dir=tmp_path, consumer_run_id=_RUN, owner_uid=os.getuid()
    )

    assert not isinstance(outcome, _failure_type())
    assert outcome.unwrap() is None


def test_a_written_assignment_reads_back_identically(tmp_path: pathlib.Path) -> None:
    module = _assignment_module()
    assignment = _decoded(stored=_stored())

    written = module.write_assignment(
        state_dir=tmp_path, assignment=assignment, owner_uid=os.getuid()
    )
    assert not isinstance(written, _failure_type())
    reread = module.read_assignment(state_dir=tmp_path, consumer_run_id=_RUN, owner_uid=os.getuid())

    assert not isinstance(reread, _failure_type())
    assert reread.unwrap() == assignment


def test_the_assignment_path_is_the_consumer_run_keyed_local_record(
    tmp_path: pathlib.Path,
) -> None:
    from _lpm_paths import local_record_path

    outcome = _assignment_module().assignment_path(state_dir=tmp_path, consumer_run_id=_RUN)

    assert not isinstance(outcome, _failure_type())
    assert (
        outcome.unwrap()
        == local_record_path(state_dir=tmp_path, family="assignment", identity=[_RUN]).unwrap()
    )


def test_a_readable_but_nonconforming_record_on_disk_is_store_unavailable(
    tmp_path: pathlib.Path,
) -> None:
    module = _assignment_module()
    path = module.assignment_path(state_dir=tmp_path, consumer_run_id=_RUN).unwrap()
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(_stored(status="withdrawn")), encoding="utf-8")
    path.chmod(0o600)

    outcome = module.read_assignment(
        state_dir=tmp_path, consumer_run_id=_RUN, owner_uid=os.getuid()
    )

    assert isinstance(outcome, _failure_type())
    assert outcome.failure().error_type == "store-unavailable"


def test_an_unregistered_record_family_is_an_internal_bug_on_both_sides(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one defect `local_record_path` reports, reached through the module that owns it.

    `_lpm_paths.LOCAL_PATH_FAMILIES` is a closed table, so this rail is unreachable with the
    table intact -- which is exactly why it is `internal-bug` rather than an operator-facing
    refusal. Deleting the row is the only honest way to prove both callers propagate it rather
    than swallowing it into a path they then write to.
    """
    import _lpm_paths

    module = _assignment_module()
    assignment = _decoded(stored=_stored())
    monkeypatch.delitem(_lpm_paths.LOCAL_PATH_FAMILIES, module.ASSIGNMENT_FAMILY)

    read = module.read_assignment(state_dir=tmp_path, consumer_run_id=_RUN, owner_uid=os.getuid())
    written = module.write_assignment(
        state_dir=tmp_path, assignment=assignment, owner_uid=os.getuid()
    )

    assert isinstance(read, _failure_type())
    assert read.failure().error_type == "internal-bug"
    assert isinstance(written, _failure_type())
    assert written.failure().error_type == "internal-bug"


def test_an_unreadable_assignment_file_is_store_unavailable(tmp_path: pathlib.Path) -> None:
    module = _assignment_module()
    path = module.assignment_path(state_dir=tmp_path, consumer_run_id=_RUN).unwrap()
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(_stored()), encoding="utf-8")
    path.chmod(0o644)

    outcome = module.read_assignment(
        state_dir=tmp_path, consumer_run_id=_RUN, owner_uid=os.getuid()
    )

    assert isinstance(outcome, _failure_type())
    assert outcome.failure().error_type == "store-unavailable"
