"""An assignment's status relations, and the tombstone every time of which is known.

SPECIFICATION/contracts.md states the assignment as exactly fifteen members and the tombstone as
exactly fourteen, and is explicit that any violation of the assignment's STATUS-FIELD RELATIONS
makes the record malformed: `target_committed_at` is non-null EXACTLY when `status` is
`committed`, and a `prepared` assignment must have a null end time, an EMPTY marker array and a
null completion.

THAT PAIR OF RULES IS WHAT MAKES "DID THIS RUN'S TARGET COMMIT?" ANSWERABLE FROM THE RECORD
ALONE, which is the first question every recovery path asks. A `prepared` record carrying a
commit time would answer it wrongly in the direction that consumes a `consumer_run_id` forever,
so each half is asserted in both directions here rather than only on the happy path.

THE TOMBSTONE'S DIFFERENCE IS THAT NOTHING IS NULLABLE. An assignment's commit and end times are
nullable because it may still be prepared or still live; a tombstone exists only because a
committed assignment closed, so all five instants are known and a null one is malformed. The
derivation test asserts the binding members are copied VERBATIM — same reference, account,
generation and value reference — because a tombstone that disagreed with the assignment it closed
would refuse reuse of a binding nobody can reconstruct.

`request` AND `completion` ARE VALIDATED BY THE OPERATION'S OWN INPUT VALIDATOR, not by a second
transcription, and the test proves that by feeding each a shape that validator refuses. A second
spelling is how an assignment comes to disagree with the operation that created it.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_REF = "op://llm-provider-manager-token-values/3f2504e0-gen/credential"
_STARTED = "2026-09-30T10:00:00Z"
_COMMITTED = "2026-09-30T10:00:30Z"
_EXPIRES = "2026-09-30T16:00:00Z"
_ACCEPTED = "2026-09-30T12:00:00Z"


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _assignment_module():
    return _module("_lpm_assignment")


def _tombstone_module():
    return _module("_lpm_tombstone")


def _request() -> dict[str, object]:
    return {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "consumer_run_id": "run-7",
        "target_ref": "ref-7",
        "strategy": "consume-first",
        "lease_seconds": 21600,
    }


def _receipt() -> dict[str, object]:
    return {
        "record_id": _RECORD_ID,
        "account_id": "acct-1",
        "purpose": "factory",
        "validated_at": "2026-09-30T09:59:00Z",
        "lease_expires_at": _EXPIRES,
    }


def _completion() -> dict[str, object]:
    return {
        "version": 1,
        "consumer_run_id": "run-7",
        "record_id": _RECORD_ID,
        "completed_at": _ACCEPTED,
        "consumer_class": "production",
        "provider_authenticated": True,
        "alternate_credential_used": False,
        "legacy_pool_absent": False,
    }


def _committed_object(**changes: object) -> dict[str, object]:
    source: dict[str, object] = {
        "version": 1,
        "status": "committed",
        "request": _request(),
        "target_ref": "ref-7",
        "account_id": "acct-1",
        "value_generation": _GENERATION,
        "value_ref": _REF,
        "record_id": _RECORD_ID,
        "receipt": _receipt(),
        "lease_started_at": _STARTED,
        "lease_expires_at": _EXPIRES,
        "target_committed_at": _COMMITTED,
        "actual_lease_ended_at": None,
        "report_markers": [],
        "completion": None,
    }
    source.update(changes)
    return source


def _prepared_object(**changes: object) -> dict[str, object]:
    source = _committed_object(status="prepared", target_committed_at=None)
    source.update(changes)
    return source


def _defect(**changes: object) -> str:
    return (
        _assignment_module()
        .assignment_from_object(parsed=_committed_object(**changes))
        .failure()
        .message
    )


# ---------------------------------------------------------------------------
# The assignment
# ---------------------------------------------------------------------------


def test_the_assignment_is_exactly_the_fifteen_ratified_members():
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
    assert _module("_lpm_receipt").RECEIPT_MEMBERS == (
        "record_id",
        "account_id",
        "purpose",
        "validated_at",
        "lease_expires_at",
    )
    assert module.ASSIGNMENT_STATUSES == ("prepared", "committed")
    assignment = module.assignment_from_object(parsed=_committed_object()).unwrap()
    assert module.assignment_object(assignment=assignment) == _committed_object()
    assert module.assignment_from_object(parsed=_prepared_object()).unwrap().status == "prepared"


def test_the_assignment_path_is_the_contract_s_run_keyed_digest(tmp_path):
    paths = _module("_lpm_paths")
    state_dir = tmp_path / "state"

    resolved = (
        _assignment_module().assignment_path(state_dir=state_dir, consumer_run_id="run-7").unwrap()
    )

    assert (
        resolved
        == paths.local_record_path(
            state_dir=state_dir, family="assignment", identity=("run-7",)
        ).unwrap()
    )
    assert resolved.parent.name == "assignments"


def test_a_commit_time_is_non_null_exactly_when_the_status_is_committed():
    module = _assignment_module()

    assert _defect(target_committed_at=None) == (
        "target_committed_at must be non-null exactly when status is committed"
    )
    assert module.assignment_from_object(
        parsed=_prepared_object(target_committed_at=_COMMITTED)
    ).failure().message == (
        "target_committed_at must be non-null exactly when status is committed"
    ), "a prepared record carrying a commit time would consume its run identity forever"


def test_a_prepared_assignment_carries_no_end_time_no_markers_and_no_completion():
    module = _assignment_module()

    def _prepared_defect(**changes: object) -> str:
        return module.assignment_from_object(parsed=_prepared_object(**changes)).failure().message

    assert _prepared_defect(actual_lease_ended_at=_ACCEPTED) == (
        "a prepared assignment must have a null actual_lease_ended_at"
    )
    assert (
        _prepared_defect(report_markers=[{"occurred_at": _ACCEPTED, "classification": "unknown"}])
        == "a prepared assignment must have an empty report_markers array"
    )
    assert _prepared_defect(completion=_completion()) == (
        "a prepared assignment must have a null completion"
    )


def test_a_committed_assignment_s_end_time_stays_inside_its_own_lease_window():
    module = _assignment_module()

    assert _defect(actual_lease_ended_at="2026-09-30T10:00:15Z") == (
        "actual_lease_ended_at must be no earlier than the lease start and target commit"
    )
    assert _defect(actual_lease_ended_at="2026-09-30T16:00:01Z") == (
        "actual_lease_ended_at must be no later than lease_expires_at"
    )
    assert (
        module.assignment_from_object(parsed=_committed_object(actual_lease_ended_at=_ACCEPTED))
        .unwrap()
        .actual_lease_ended_at
        == _ACCEPTED
    )


def test_every_assignment_membership_and_type_defect_fails_closed():
    module = _assignment_module()
    missing = _committed_object()
    del missing["receipt"]

    assert module.assignment_from_object(parsed="not an object").failure().message == (
        "an assignment must be a JSON object"
    )
    assert module.assignment_from_object(parsed=missing).failure().message == (
        "an assignment is missing receipt"
    )
    assert _defect(extra_member=1) == "an assignment has extra member extra_member"
    assert _defect(version=True) == "an assignment version must be the integer 1"
    assert _defect(version=2) == "an assignment version must be the integer 1"
    assert _defect(status="closed") == "an assignment status must be prepared or committed"
    assert _defect(target_ref="") == "an assignment target_ref must be a non-empty string"
    assert _defect(record_id="NOT-A-UUID") == (
        "an assignment record_id must be a lowercase RFC 4122 UUIDv4"
    )
    assert _defect(lease_started_at="2026-09-30 10:00:00") == (
        "an assignment lease_started_at must be a UTC RFC 3339-second timestamp"
    )
    assert _defect(target_committed_at="whenever") == (
        "an assignment target_committed_at must be null or a UTC RFC 3339-second timestamp"
    )
    assert _defect(report_markers={}) == "an assignment report_markers must be an array"


def test_the_request_and_completion_are_validated_by_the_operation_s_own_validator():
    stored = _request()
    del stored["strategy"]

    assert _defect(request=stored) == (
        "provision normalized_input must contain exactly version, provider, kind, purpose, "
        "consumer_run_id, target_ref, strategy, lease_seconds"
    ), "the assignment's request IS the normalized provisioning request"
    assert _defect(completion={"version": 1}) == (
        "complete normalized_input must contain exactly version, consumer_run_id, record_id, "
        "completed_at, consumer_class, provider_authenticated, alternate_credential_used, "
        "legacy_pool_absent"
    ), "a non-null completion has the exact completion-input shape"


def test_the_receipt_is_the_exact_five_member_secret_free_shape():
    module = _module("_lpm_receipt")
    receipt = _receipt()
    receipt["value"] = "sk-ant-oat01-REDACTED"

    assert module.receipt_shape_defect(receipt=receipt) == (
        "an assignment receipt must contain exactly record_id, account_id, purpose, "
        "validated_at, lease_expires_at"
    ), "there is no member a captured credential could ride in on"
    assert _defect(receipt=receipt) == (
        "an assignment receipt must contain exactly record_id, account_id, purpose, "
        "validated_at, lease_expires_at"
    ), "the record validator reports the receipt defect rather than swallowing it"
    assert module.receipt_shape_defect(receipt=["not", "an", "object"]) == (
        "an assignment receipt must be a JSON object"
    )
    assert module.receipt_shape_defect(receipt={**_receipt(), "record_id": "nope"}) == (
        "a receipt record_id must be a lowercase RFC 4122 UUIDv4"
    )
    assert module.receipt_shape_defect(receipt={**_receipt(), "purpose": ""}) == (
        "a receipt purpose must be a non-empty string"
    )
    assert module.receipt_shape_defect(receipt={**_receipt(), "validated_at": "nope"}) == (
        "a receipt validated_at must be a UTC RFC 3339-second timestamp"
    )
    assert module.receipt_shape_defect(receipt=_receipt()) is None


def test_a_marker_array_defect_inside_an_assignment_is_reported_as_such():
    marker = {"occurred_at": _ACCEPTED, "classification": "unknown"}

    assert _defect(report_markers=[marker, dict(marker)]) == (
        "report_markers must hold unique objects"
    )


# ---------------------------------------------------------------------------
# The tombstone
# ---------------------------------------------------------------------------


def test_the_tombstone_is_exactly_fourteen_members_with_no_status_and_no_receipt():
    module = _tombstone_module()
    close = _module("_lpm_assignment_close")
    assignment = _assignment_module().assignment_from_object(parsed=_committed_object()).unwrap()

    tombstone = module.tombstone_from_assignment(
        assignment=assignment,
        close_times=close.CloseTimes(actual_lease_ended_at=_ACCEPTED, closed_at=_ACCEPTED),
    ).unwrap()

    assert module.TOMBSTONE_MEMBERS == (
        "version",
        "request",
        "target_ref",
        "account_id",
        "value_generation",
        "value_ref",
        "record_id",
        "lease_started_at",
        "lease_expires_at",
        "target_committed_at",
        "actual_lease_ended_at",
        "closed_at",
        "report_markers",
        "completion",
    )
    assert "status" not in module.TOMBSTONE_MEMBERS, "a tombstone is closed by construction"
    assert "receipt" not in module.TOMBSTONE_MEMBERS, "the receipt answered a provision now over"
    assert module.tombstone_object(tombstone=tombstone) == {
        "version": 1,
        "request": _request(),
        "target_ref": "ref-7",
        "account_id": "acct-1",
        "value_generation": _GENERATION,
        "value_ref": _REF,
        "record_id": _RECORD_ID,
        "lease_started_at": _STARTED,
        "lease_expires_at": _EXPIRES,
        "target_committed_at": _COMMITTED,
        "actual_lease_ended_at": _ACCEPTED,
        "closed_at": _ACCEPTED,
        "report_markers": [],
        "completion": None,
    }


def test_the_binding_members_are_copied_from_the_assignment_verbatim():
    module = _tombstone_module()
    close = _module("_lpm_assignment_close")
    marker = {"occurred_at": "2026-09-30T11:00:00Z", "classification": "rate-limit"}
    assignment = (
        _assignment_module()
        .assignment_from_object(
            parsed=_committed_object(report_markers=[marker], completion=_completion())
        )
        .unwrap()
    )

    tombstone = module.tombstone_from_assignment(
        assignment=assignment,
        close_times=close.CloseTimes(actual_lease_ended_at=_EXPIRES, closed_at=_ACCEPTED),
    ).unwrap()

    for member in ("target_ref", "account_id", "value_generation", "value_ref", "record_id"):
        assert getattr(tombstone, member) == getattr(
            assignment, member
        ), f"{member} must survive the close verbatim"
    assert tombstone.report_markers == assignment.report_markers
    assert tombstone.completion == _completion()
    assert tombstone.actual_lease_ended_at == _EXPIRES
    assert tombstone.closed_at == _ACCEPTED, "closed_at is the command's own logical instant"


def test_only_a_committed_assignment_may_become_a_tombstone():
    module = _tombstone_module()
    close = _module("_lpm_assignment_close")
    prepared = _assignment_module().assignment_from_object(parsed=_prepared_object()).unwrap()

    refusal = module.tombstone_from_assignment(
        assignment=prepared,
        close_times=close.CloseTimes(actual_lease_ended_at=_ACCEPTED, closed_at=_ACCEPTED),
    )

    assert refusal.failure().error_type == "store-unavailable"
    assert refusal.failure().message == "only a committed assignment may become a tombstone"


def test_a_tombstone_with_any_null_instant_is_malformed(tmp_path):
    module = _tombstone_module()
    paths = _module("_lpm_paths")
    close = _module("_lpm_assignment_close")
    assignment = _assignment_module().assignment_from_object(parsed=_committed_object()).unwrap()
    stored = module.tombstone_object(
        tombstone=module.tombstone_from_assignment(
            assignment=assignment,
            close_times=close.CloseTimes(actual_lease_ended_at=_ACCEPTED, closed_at=_ACCEPTED),
        ).unwrap()
    )
    missing = dict(stored)
    del missing["closed_at"]

    assert module.tombstone_from_object(parsed="not an object").failure().message == (
        "a tombstone must be a JSON object"
    )
    assert module.tombstone_from_object(parsed=missing).failure().message == (
        "a tombstone is missing closed_at"
    )
    assert (
        module.tombstone_from_object(parsed={**stored, "extra_member": 1}).failure().message
        == "a tombstone has extra member extra_member"
    )
    assert module.tombstone_from_object(parsed={**stored, "version": 2}).failure().message == (
        "a tombstone version must be the integer 1"
    )
    assert module.tombstone_from_object(
        parsed={**stored, "target_committed_at": None}
    ).failure().message == (
        "a tombstone target_committed_at must be a UTC RFC 3339-second timestamp"
    )
    assert module.tombstone_from_object(parsed={**stored, "account_id": ""}).failure().message == (
        "an assignment account_id must be a non-empty string"
    )
    assert (
        module.tombstone_from_object(parsed={**stored, "report_markers": {}}).failure().message
        == "a tombstone report_markers must be an array"
    )
    assert (
        module.tombstone_from_object(
            parsed={**stored, "actual_lease_ended_at": "2026-09-30T16:00:01Z"}
        )
        .failure()
        .message
        == "actual_lease_ended_at must be no later than lease_expires_at"
    )
    assert (
        module.tombstone_from_object(parsed={**stored, "completion": {"version": 1}})
        .failure()
        .message.startswith("complete normalized_input must contain exactly")
    )
    assert (
        module.tombstone_from_object(
            parsed={
                **stored,
                "report_markers": [
                    {"occurred_at": _ACCEPTED, "classification": "unknown"},
                    {"occurred_at": _ACCEPTED, "classification": "unknown"},
                ],
            }
        )
        .failure()
        .message
        == "report_markers must hold unique objects"
    )
    assert (
        module.tombstone_path(state_dir=tmp_path / "state", consumer_run_id="run-7").unwrap()
        == paths.local_record_path(
            state_dir=tmp_path / "state", family="tombstone", identity=("run-7",)
        ).unwrap()
    )
