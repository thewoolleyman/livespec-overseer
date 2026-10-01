"""Each role's closed RESULT shapes: its status vocabulary and each status's exact members.

SPECIFICATION/contracts.md requires every direct SecretStore role result crossing the
credential-role launcher boundary to be "exactly one UTF-8 JSON object with no extra
fields", then enumerates the permitted shapes per role and mode -- a metadata get answers
`ok` with `item`, `invalid` with `invalid`, or bare `unavailable`; a list answers `ok` with
`items` and `invalid`; a conditional set answers `committed`, `uncommitted`,
`condition-failed` or `unavailable`; final provisioning and tokenless `target-status`
answer a commit status or `store-unavailable`.

WHY "NO EXTRA FIELDS" IS A LEAK CONTROL AND NOT TIDINESS. A parent that accepted any object
carrying a recognized `version` and `status` would pass an unrecognized member straight
through to its caller -- including one holding a credential value. The role process is the
one place in this operation that legitimately holds a token, so the boundary it writes
across is exactly where an extra member must be refused.

WHAT THIS CLOSES AND WHAT IT DOES NOT. The ENVELOPE is closed here: which statuses a role
may answer with, and precisely which members each status carries. Record CONTENTS are
deliberately NOT -- the contract puts those after this boundary, saying the manager applies
the credential-record field and invariant checks only after receiving the envelope. And the
roles whose operations this slice does not implement are not closed at all; the pinned table
below makes that gap visible instead of leaving it to be discovered.

A REJECTION QUOTES NO CHILD BYTES. A rogue child controls both its status and its member
NAMES, so a diagnostic echoing either would let a token placed in a member name be logged
by the very check that rejected the result.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_LEAK = "sk-ant-oat0-must-not-be-logged"
# The one mode each lifecycle writer's request carries. The contract says those three
# "MUST receive exactly the latter conditional-set object", which is the one whose `mode` is
# this -- so a writer result is keyed on it, never on no mode at all.
_SET_MODE = "credential-conditional-set"


def _results():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_role_results.py"
    assert module_path.is_file(), "overseer/_lpm_role_results.py must exist"
    return importlib.import_module("_lpm_role_results")


def _runner():
    return importlib.import_module("_lpm_role_runner")


def _roles():
    return importlib.import_module("_lpm_roles")


def _child():
    return importlib.import_module("_lpm_role_child")


def _stub_companion(root, *, body):
    root.mkdir(parents=True, exist_ok=True)
    python = root / "python3"
    python.write_text(f"#!/bin/sh\n{body}", encoding="utf-8")
    python.chmod(0o755)
    companion = root / "_lpm_role_main.py"
    companion.write_text("# the packaged companion\n", encoding="utf-8")
    return _roles().PackagedCompanion(
        python_executable=str(python), packaged_companion=str(companion)
    )


def _run_against(tmp_path, *, body):
    runner = _runner()
    role = _roles().credential_role(name="metadata-reader")
    return runner.run_credential_role(
        role_input=_child().ClosedRoleInput(
            role_name="metadata-reader",
            key_description=role.key_description,
            descriptors=role.descriptors,
        ),
        companion=_stub_companion(tmp_path, body=body),
        role_request={
            "version": 1,
            "mode": "get",
            "record_id": "r",
            "op_executable": "/usr/bin/op",
        },
        environ={"PATH": "/usr/bin:/bin"},
        timeout_seconds=5.0,
        launch=runner.subprocess_role_launch,
    )


def _run_with_answer(runner, *, payload):
    """Drive the public boundary against a launch that answers with exactly `payload`.

    An injected launch rather than a real child here: the bytes under test are the point,
    and a real child would be a second place that had to produce them exactly.
    """
    role = _roles().credential_role(name="metadata-reader")

    def _launch(*, argv, environ, request_bytes, timeout_seconds, inherited_fds):
        return runner.RoleCompletion(stdout=payload, exit_status=0, timed_out=False)

    return runner.run_credential_role(
        role_input=_child().ClosedRoleInput(
            role_name="metadata-reader",
            key_description=role.key_description,
            descriptors=role.descriptors,
        ),
        companion=_roles().PackagedCompanion(
            python_executable="/usr/bin/python3", packaged_companion="/pkg/_lpm_role_main.py"
        ),
        role_request={"version": 1, "mode": "get", "record_id": "r", "op_executable": "/op"},
        environ={"PATH": "/usr/bin"},
        timeout_seconds=5.0,
        launch=_launch,
    )


def test_an_extra_member_is_refused_end_to_end_and_never_reaches_the_caller(tmp_path):
    """The headline leak: a real child adds one member to an otherwise perfect answer.

    Driven through a real subprocess rather than the table alone, because the property that
    matters is that the extra member never reaches the CALLER -- a table test proves the
    rule exists, not that the parent applies it. `{"version":1,"status":"ok","item":null}`
    is a flawless metadata-get answer; the only thing wrong with this result is the member
    beside it, which is precisely the shape a passthrough parent would hand on.

    The reason is asserted to contain neither the value nor the member NAME, because both
    are the child's bytes and a diagnostic that quoted them would log what it rejected.
    """
    outcome = _run_against(
        tmp_path,
        body=(
            'printf \'{"version":1,"status":"ok","item":null,' f'"leaked_token":"{_LEAK}"' + "}'\n"
        ),
    )

    assert outcome.result_object == {"version": 1, "status": "unavailable"}
    assert outcome.launched is True
    assert "whose members are not that shape's exact members" in outcome.refusal_reason
    assert _LEAK not in str(outcome.result_object)
    assert _LEAK not in outcome.refusal_reason
    assert "leaked_token" not in outcome.refusal_reason


def test_every_closed_shape_this_slice_covers_is_accepted():
    """The accept side, so the refusals below cannot pass by rejecting everything.

    `committed_at` is a member of EVERY commit shape and null on all but `committed`, so a
    definitive no-change answer carries the member with a null value. Its presence is a
    shape question; whether it may hold a value is a separate rule, exercised below.
    """
    results = _results()
    envelope = {"item_id": "rev-1", "record": {}}
    descriptor = {"record_id": "0f9c0a1e-0000-4000-8000-000000000000", "reason": "gap"}

    for role_name, mode, members in (
        ("metadata-reader", "get", {"version": 1, "status": "ok", "item": None}),
        ("metadata-reader", "get", {"version": 1, "status": "ok", "item": envelope}),
        ("metadata-reader", "get", {"version": 1, "status": "invalid", "invalid": descriptor}),
        ("metadata-reader", "get", {"version": 1, "status": "unavailable"}),
        ("metadata-reader", "list", {"version": 1, "status": "ok", "items": [], "invalid": []}),
        ("metadata-reader", "list", {"version": 1, "status": "unavailable"}),
        ("lifecycle-writer", _SET_MODE, {"version": 1, "status": "committed"}),
        ("report-writer", _SET_MODE, {"version": 1, "status": "condition-failed"}),
        ("recovery-writer", _SET_MODE, {"version": 1, "status": "uncommitted"}),
        ("recovery-writer", _SET_MODE, {"version": 1, "status": "unavailable"}),
        (
            "final-provisioning",
            None,
            {"version": 1, "status": "committed", "committed_at": "2026-09-12T10:00:00Z"},
        ),
        ("final-provisioning", None, {"version": 1, "status": "in-progress", "committed_at": None}),
        ("final-provisioning", None, {"version": 1, "status": "store-unavailable"}),
        ("target-status", None, {"version": 1, "status": "uncommitted", "committed_at": None}),
        ("target-status", None, {"version": 1, "status": "store-unavailable"}),
    ):
        assert (
            results.closed_result_defect(role_name=role_name, mode=mode, members=members) is None
        ), (role_name, mode, members)


def test_an_unregistered_status_or_member_set_is_refused_without_quoting_child_bytes():
    """Two refusals with two different messages, and neither carries a byte the child chose.

    The distinction is worth keeping: a status outside the vocabulary means the parent has
    no idea what the child was claiming, while a recognized status with the wrong members
    means it claimed something specific and malformed it. Only the second can name its
    status, and only because that status is drawn from the manager's own table by then.
    """
    results = _results()

    for role_name, mode, members, fragment in (
        ("metadata-reader", "get", {"version": 1, "status": "ok"}, "exact members"),
        (
            "metadata-reader",
            "get",
            {"version": 1, "status": "ok", "item": None, _LEAK: "x"},
            "exact members",
        ),
        ("metadata-reader", "get", {"version": 1, "status": "committed"}, "closed vocabulary"),
        ("metadata-reader", "get", {"version": 1, "status": _LEAK}, "closed vocabulary"),
        ("metadata-reader", "list", {"version": 1, "status": "ok", "items": []}, "exact members"),
        (
            "lifecycle-writer",
            _SET_MODE,
            {"version": 1, "status": "ok", "item": None},
            "closed vocabulary",
        ),
        (
            "final-provisioning",
            None,
            {"version": 1, "status": "committed", "committed_at": None},
            "no commit time",
        ),
        (
            "target-status",
            None,
            {"version": 1, "status": "in-progress", "committed_at": "2026-09-12T10:00:00Z"},
            "carrying a commit time",
        ),
        (
            "final-provisioning",
            None,
            {"version": 1, "status": "uncommitted"},
            "exact members",
        ),
    ):
        defect = results.closed_result_defect(role_name=role_name, mode=mode, members=members)

        assert defect is not None, (role_name, members)
        assert fragment in defect, (role_name, members, defect)
        assert _LEAK not in defect


def test_every_commit_status_carries_a_nullable_committed_at_non_null_only_for_committed():
    """`committed_at` is a member of ALL three commit shapes, null except for `committed`.

    The contract fixes commit status at `in-progress`, `committed` or `uncommitted` "plus a
    nullable `committed_at` that is non-null exactly for `committed`", and `_lpm_target`'s
    own `CommitOutcome` carries the field unconditionally as `str | None`. Treating it as
    riding `committed` alone rejects the shape the real adapter actually produces -- an
    `uncommitted` with `committed_at: null` -- which would turn every definitive no-change
    answer into a nonconforming one and lose the distinction the three words exist for.

    The value rule is the other half: a `committed` whose `committed_at` is null claims a
    commit while withholding the fence sample that dates it, and a non-null one on any other
    status dates a commit that did not happen.
    """
    results = _results()
    stamp = "2026-09-12T10:00:00Z"

    for status in ("in-progress", "uncommitted"):
        assert (
            results.closed_result_defect(
                role_name="final-provisioning",
                mode=None,
                members={"version": 1, "status": status, "committed_at": None},
            )
            is None
        ), status
        assert results.closed_result_defect(
            role_name="target-status",
            mode=None,
            members={"version": 1, "status": status, "committed_at": stamp},
        ), f"{status} must not date a commit that did not happen"

    assert (
        results.closed_result_defect(
            role_name="final-provisioning",
            mode=None,
            members={"version": 1, "status": "committed", "committed_at": stamp},
        )
        is None
    )
    assert results.closed_result_defect(
        role_name="final-provisioning",
        mode=None,
        members={"version": 1, "status": "committed", "committed_at": None},
    ), "a commit must carry the fence sample that dates it"


def test_a_boolean_or_float_version_is_not_the_integer_one():
    """`True == 1` and `1.0 == 1` in Python, so an equality check alone admits both.

    JSON `true` and `1.0` are not the integer `1`, and a parent that accepted either would
    be reading a version it was never sent. This is the cheapest shape confusion there is to
    introduce and the hardest to notice, because every other assertion about the object
    still passes. Driven through the public boundary rather than the private parse helper,
    so what is pinned is what a caller can actually observe.
    """
    runner = _runner()

    for literal in ("true", "1.0", '"1"', "null"):
        payload = f'{{"version":{literal},"status":"unavailable"}}'.encode()
        outcome = _run_with_answer(runner, payload=payload)

        assert outcome.refusal_reason is not None, literal
        assert "version is not 1" in outcome.refusal_reason, literal

    accepted = _run_with_answer(runner, payload=b'{"version":1,"status":"unavailable"}')

    assert accepted.refusal_reason is None
    assert accepted.result_object == {"version": 1, "status": "unavailable"}


def test_the_item_envelope_and_invalid_descriptor_are_themselves_closed():
    """`item` and `invalid` are objects with their own exact shapes, not opaque payloads.

    The contract gives the envelope "exactly non-empty `item_id` ... and `record`", and the
    invalid-chain descriptor "exactly lowercase RFC 4122 UUIDv4 `record_id` and `reason`
    from `gap`, `conflict`, `title-mismatch`, `predecessor-mismatch` or
    `multiple-successors`". Leaving them unchecked reopens the hole the outer member set
    closes: an extra member on the ENVELOPE carries just as well as one on the result, and a
    reader cannot refuse what it never inspected.

    `record` itself stays opaque here on purpose -- the contract has the manager apply the
    credential-record field and invariant checks only after receiving the envelope, so
    duplicating them would put one rule in two places that can disagree.
    """
    results = _results()
    uuid = "0f9c0a1e-0000-4000-8000-000000000000"

    def _get(item):
        return results.closed_result_defect(
            role_name="metadata-reader",
            mode="get",
            members={"version": 1, "status": "ok", "item": item},
        )

    def _invalid(descriptor):
        return results.closed_result_defect(
            role_name="metadata-reader",
            mode="get",
            members={"version": 1, "status": "invalid", "invalid": descriptor},
        )

    assert _get(None) is None, "authoritative absence stays legal"
    assert _get({"item_id": "rev-1", "record": {"any": "canonical value"}}) is None
    assert _get({"item_id": "rev-1", "record": {}, _LEAK: "x"}), "an extra envelope member"
    assert _get({"item_id": "rev-1"}), "a missing record member"
    assert _get({"item_id": "", "record": {}}), "an empty item_id"
    assert _get({"item_id": 7, "record": {}}), "a non-string item_id"
    assert _get(["rev-1"]), "an envelope that is not an object"

    assert _invalid({"record_id": uuid, "reason": "gap"}) is None
    assert _invalid({"record_id": uuid, "reason": "multiple-successors"}) is None
    assert _invalid({"record_id": uuid, "reason": "invented-reason"}), "an unregistered reason"
    assert _invalid({"record_id": uuid.upper(), "reason": "gap"}), "an uppercase record_id"
    assert _invalid({"record_id": "not-a-uuid", "reason": "gap"}), "a non-UUIDv4 record_id"
    assert _invalid({"record_id": uuid, "reason": "gap", "extra": 1}), "an extra member"
    assert _invalid(["not-an-object"]), "a descriptor that is not an object"

    listed = results.closed_result_defect(
        role_name="metadata-reader",
        mode="list",
        members={
            "version": 1,
            "status": "ok",
            "items": [{"item_id": "rev-1", "record": {}}],
            "invalid": [{"record_id": uuid, "reason": "conflict"}],
        },
    )
    assert listed is None
    assert results.closed_result_defect(
        role_name="metadata-reader",
        mode="list",
        members={"version": 1, "status": "ok", "items": [{"item_id": "rev-1"}], "invalid": []},
    ), "a list must close the shape of every envelope it carries"
    assert results.closed_result_defect(
        role_name="metadata-reader",
        mode="list",
        members={"version": 1, "status": "ok", "items": {}, "invalid": []},
    ), "items must be a list"
    assert results.closed_result_defect(
        role_name="metadata-reader",
        mode="list",
        members={"version": 1, "status": "ok", "items": [], "invalid": ["not-an-object"]},
    ), "every descriptor inside a list is closed too"


def test_each_nested_member_is_closed_for_its_own_role_mode_and_status():
    """A member NAME does not determine its nested shape -- the role, mode and status do.

    `invalid` is ONE descriptor object on a get and an ARRAY of them on a list. `item` is
    nullable because null asserts authoritative absence; an element of `items` is not,
    because a list of records has no member to be absent. Deciding the nested shape from the
    name alone makes each of those confusions invisible, and all three counterexamples below
    were accepted that way: an empty array where one descriptor is required, a bare object
    where an array is required, and a null masquerading as a listed record.

    `committed_at` is the same failure at the value level. Checking only non-null accepts
    `123` and `"nope"` as commit times, but the contract requires it to EQUAL the adapter's
    final lease-fence sample -- a value a later reconciler compares against stored
    timestamps. A commit dated by something no comparison can parse is not a commit anyone
    can verify.

    Every rejection is paired with the valid shape it is one step from, so none of them can
    pass by refusing the whole family.
    """
    results = _results()
    uuid = "0f9c0a1e-0000-4000-8000-000000000000"
    descriptor = {"record_id": uuid, "reason": "gap"}
    envelope = {"item_id": "rev-1", "record": {}}
    stamp = "2026-09-12T10:00:00Z"

    def _defect(*, mode, members, role_name="metadata-reader"):
        return results.closed_result_defect(role_name=role_name, mode=mode, members=members)

    # A get's `invalid` is exactly ONE descriptor, never an array -- empty or otherwise.
    assert _defect(mode="get", members={"version": 1, "status": "invalid", "invalid": []})
    assert _defect(mode="get", members={"version": 1, "status": "invalid", "invalid": [descriptor]})
    assert (
        _defect(mode="get", members={"version": 1, "status": "invalid", "invalid": descriptor})
        is None
    )

    # A list's `invalid` is exactly an ARRAY, never a bare descriptor object.
    assert _defect(
        mode="list", members={"version": 1, "status": "ok", "items": [], "invalid": descriptor}
    )
    assert (
        _defect(
            mode="list",
            members={"version": 1, "status": "ok", "items": [], "invalid": [descriptor]},
        )
        is None
    )

    # `item` is nullable; an ELEMENT of `items` is not, because a list has nothing absent.
    assert _defect(mode="get", members={"version": 1, "status": "ok", "item": None}) is None
    assert _defect(
        mode="list", members={"version": 1, "status": "ok", "items": [None], "invalid": []}
    )
    assert (
        _defect(
            mode="list",
            members={"version": 1, "status": "ok", "items": [envelope], "invalid": []},
        )
        is None
    )

    # A commit time is a canonical UTC RFC 3339-second string, not merely non-null.
    for dated in (123, "nope", "2026-09-12T10:00:00.500Z", "2026-09-12 10:00:00Z", True):
        assert _defect(
            role_name="final-provisioning",
            mode=None,
            members={"version": 1, "status": "committed", "committed_at": dated},
        ), dated
    assert (
        _defect(
            role_name="final-provisioning",
            mode=None,
            members={"version": 1, "status": "committed", "committed_at": stamp},
        )
        is None
    )
    assert (
        _defect(
            role_name="target-status",
            mode=None,
            members={"version": 1, "status": "uncommitted", "committed_at": None},
        )
        is None
    )


def test_an_unknown_mode_of_a_covered_role_fails_closed():
    """An unrecognized mode must not fall through the not-covered success path.

    `closed_result_defect` reports no defect for a role this slice does not implement, which
    is right -- an always-failing role would be worse than an unvalidated one. But applying
    that same fallback to an unknown MODE of a role that IS covered inverts it: the role
    whose results are closed becomes the one whose results are waved through, and the
    fallback that exists to avoid over-refusing starts under-refusing instead.
    """
    results = _results()

    assert results.closed_result_defect(
        role_name="metadata-reader",
        mode="invented",
        members={"version": 1, "status": "ok", "item": None},
    ), "an unknown mode of a covered role must be refused"
    assert results.closed_result_defect(
        role_name="metadata-reader", mode=None, members={"version": 1, "status": "unavailable"}
    ), "a covered role whose request named no mode must be refused"
    assert (
        results.closed_result_defect(
            role_name="lifecycle-writer",
            mode=_SET_MODE,
            members={"version": 1, "status": "committed"},
        )
        is None
    ), "the writer's one real mode is the key its results hang on"
    assert results.closed_result_defect(
        role_name="lifecycle-writer", mode=None, members={"version": 1, "status": "committed"}
    ), "a writer keyed on no mode would bypass validation on every valid request it makes"
    assert results.closed_result_defect(
        role_name="report-writer",
        mode="secret-value-set",
        members={"version": 1, "status": "committed"},
    ), "the acquisition writer's other mode is not a lifecycle writer's"
    assert (
        results.closed_result_defect(
            role_name="final-provisioning",
            mode=None,
            members={"version": 1, "status": "store-unavailable"},
        )
        is None
    ), "final provisioning and target-status really are modeless"


def test_the_closed_table_covers_exactly_the_roles_this_slice_implements():
    """The gap is PINNED, so the next slice cannot inherit it without being told.

    A role this slice does not implement is deliberately NOT closed, and says so by
    reporting no defect rather than by rejecting every result: an always-failing role would
    be a worse answer than an unvalidated one, and the contract's own shapes for those
    roles arrive with the operations that use them.
    """
    results = _results()

    assert sorted(results.CLOSED_ROLE_RESULTS) == [
        ("final-provisioning", None),
        ("lifecycle-writer", _SET_MODE),
        ("metadata-reader", "get"),
        ("metadata-reader", "list"),
        ("recovery-writer", _SET_MODE),
        ("report-writer", _SET_MODE),
        ("target-status", None),
    ]
    assert (
        results.closed_result_defect(
            role_name="provider-observer",
            mode="health",
            members={"version": 1, "status": "ok", "remaining_percent": 40},
        )
        is None
    ), "provider-observer arrives with its own operation; this slice does not close it"
