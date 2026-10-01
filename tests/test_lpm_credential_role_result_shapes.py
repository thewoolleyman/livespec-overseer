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

    `committed_at` rides only the `committed` commit status, which is the one member-level
    distinction the contract draws inside a single role's vocabulary -- a `committed`
    without it, or an `in-progress` with it, is not that shape.
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
        ("lifecycle-writer", None, {"version": 1, "status": "committed"}),
        ("report-writer", None, {"version": 1, "status": "condition-failed"}),
        ("recovery-writer", None, {"version": 1, "status": "uncommitted"}),
        ("recovery-writer", None, {"version": 1, "status": "unavailable"}),
        (
            "final-provisioning",
            None,
            {"version": 1, "status": "committed", "committed_at": "2026-09-12T10:00:00Z"},
        ),
        ("final-provisioning", None, {"version": 1, "status": "in-progress"}),
        ("final-provisioning", None, {"version": 1, "status": "store-unavailable"}),
        ("target-status", None, {"version": 1, "status": "uncommitted"}),
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
            None,
            {"version": 1, "status": "ok", "item": None},
            "closed vocabulary",
        ),
        ("final-provisioning", None, {"version": 1, "status": "committed"}, "exact members"),
        (
            "target-status",
            None,
            {"version": 1, "status": "in-progress", "committed_at": "2026-09-12T10:00:00Z"},
            "exact members",
        ),
    ):
        defect = results.closed_result_defect(role_name=role_name, mode=mode, members=members)

        assert defect is not None, (role_name, members)
        assert fragment in defect, (role_name, members, defect)
        assert _LEAK not in defect


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
        ("lifecycle-writer", None),
        ("metadata-reader", "get"),
        ("metadata-reader", "list"),
        ("recovery-writer", None),
        ("report-writer", None),
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
