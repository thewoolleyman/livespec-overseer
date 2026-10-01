"""The PARENT side of a credential-role run: launch the closed vector, read one object.

SPECIFICATION/contracts.md fixes every result crossing the credential-role launcher
boundary as exactly one UTF-8 JSON object with no extra fields, and requires the parent to
map a role's `unavailable`, a deadline, an abnormal exit or ANY nonconforming output onto a
closed failure -- never onto absence, because absence is what permits a genesis create.
`tests/test_lpm_credential_role_execution.py` drives what happens INSIDE the launcher
child; this module drives what its parent is allowed to conclude from the outside.

IT IS DRIVEN THROUGH REAL CHILD PROCESSES, not a double, wherever the property under test
is a property of the PROCESS BOUNDARY. That the role input reaches the child's standard
INPUT rather than its argument vector, that an unfamiliar exit status survives, that a
child writing garbage cannot be mistaken for one reporting absence -- a double cannot
falsify any of those, because a double is where the bytes would have been invented. The
injected `launch` appears only for the refusals that must happen BEFORE any child exists,
where the point is that it was never called.

THE REQUEST MUST NOT TRAVEL ON ARGV. A process argument list is readable through procfs by
anything that can see the process, and these inputs name records, runs and generations a
reader could correlate. The vector therefore stays exactly the six closed elements, and
the input goes over the pipe.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_REQUEST = {
    "version": 1,
    "mode": "get",
    "record_id": "rec-1",
    "op_executable": "/usr/bin/op",
}

_INHERITED = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/home/operator",
    "CLAUDECODE": "1",
    "ANTHROPIC_API_KEY": "consumer-override",
    "OP_SERVICE_ACCOUNT_TOKEN": "inherited-op",
    "LPM_METADATA_READER_OP_SERVICE_ACCOUNT_TOKEN": "inherited-manager",
}


def _runner():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_role_runner.py"
    assert module_path.is_file(), "overseer/_lpm_role_runner.py must exist"
    return importlib.import_module("_lpm_role_runner")


def _child():
    return importlib.import_module("_lpm_role_child")


def _roles():
    return importlib.import_module("_lpm_roles")


def _canonical(value):
    canonical = importlib.import_module("_lpm_canonical")
    return canonical.canonical_json_bytes(value=value).unwrap()


def _stub_companion(root, *, body):
    """A stub standing in for the resolved interpreter, plus a companion file beside it.

    The contract's vector puts the interpreter FIRST, so a stub there receives `-I -S
    <companion> --credential-role <role>` as its own arguments -- which is exactly the
    shape a test needs to prove the vector was built right and carried nothing else.
    """
    root.mkdir(parents=True, exist_ok=True)
    python = root / "python3"
    python.write_text(f"#!/bin/sh\n{body}", encoding="utf-8")
    python.chmod(0o755)
    companion = root / "_lpm_role_main.py"
    companion.write_text("# the packaged companion\n", encoding="utf-8")
    return _roles().PackagedCompanion(
        python_executable=str(python), packaged_companion=str(companion)
    )


def _role_input(*, role_name):
    role = _roles().credential_role(name=role_name)
    return _child().ClosedRoleInput(
        role_name=role_name, key_description=role.key_description, descriptors=role.descriptors
    )


def _run(runner, *, companion, launch, role_request=None, role_input=None, timeout_seconds=5.0):
    return runner.run_credential_role(
        role_input=_role_input(role_name="metadata-reader") if role_input is None else role_input,
        companion=companion,
        role_request=_REQUEST if role_request is None else role_request,
        environ=_INHERITED,
        timeout_seconds=timeout_seconds,
        launch=launch,
    )


def test_a_real_launcher_subprocess_hands_back_exactly_the_role_s_own_closed_object(tmp_path):
    """One real child, one closed object: the request on stdin, the six-element vector, back.

    The returned members are compared to the child's own bytes rather than to a
    re-serialization, because the closed shapes are specified ON those members: a parent
    that normalized them would make `item: null` -- authoritative absence -- and a missing
    `item` indistinguishable.
    """
    runner = _runner()
    captured = tmp_path / "captured"
    captured.mkdir()
    companion = _stub_companion(
        tmp_path / "pkg",
        body=(
            f'cat > "{captured}/stdin"\n'
            f'printf "%s" "$*" > "{captured}/args"\n'
            'printf \'{"version":1,"status":"ok","item":null}\'\n'
        ),
    )

    outcome = _run(runner, companion=companion, launch=runner.subprocess_role_launch)

    assert outcome.result_object == {"version": 1, "status": "ok", "item": None}
    assert outcome.refusal_reason is None
    assert outcome.launched is True
    assert (captured / "stdin").read_bytes() == _canonical(_REQUEST)
    arguments = (captured / "args").read_text(encoding="utf-8")
    assert arguments.split() == [
        "-I",
        "-S",
        companion.packaged_companion,
        "--credential-role",
        "metadata-reader",
    ]
    assert "rec-1" not in arguments, "the role input must never travel on the argument vector"


def test_any_nonconforming_child_output_becomes_that_role_s_own_closed_failure_object(tmp_path):
    """Garbage, a wrong version, a missing status, a duplicate member and a bare exit all map.

    They are driven together because the contract gives them ONE destination, and the
    danger they share is singular: every one of these outputs could be read as "the record
    is not there" by a parent that was lenient about the shape, and authoritative absence
    is what licenses a genesis create. The reason names the exit status so a later reader
    can tell a child that answered badly from one that died.
    """
    runner = _runner()

    for index, (body, fragment) in enumerate(
        (
            ("printf '\\377\\376'\n", "not UTF-8"),
            ("printf 'not json at all'\n", "not one JSON object"),
            ("printf '[1,2]'\n", "not a JSON object"),
            ('printf \'{"version":2,"status":"ok"}\'\n', "version is not 1"),
            ("printf '{\"version\":1}'\n", "carries no status"),
            (
                'printf \'{"version":1,"status":"ok","status":"unavailable"}\'\n',
                "duplicate member name",
            ),
            ("exit 9\n", "not one JSON object"),
        )
    ):
        companion = _stub_companion(tmp_path / f"case{index}", body=body)

        outcome = _run(runner, companion=companion, launch=runner.subprocess_role_launch)

        assert outcome.result_object == {"version": 1, "status": "unavailable"}, body
        assert outcome.launched is True
        assert fragment in outcome.refusal_reason, body
        assert "exited" in outcome.refusal_reason

    assert (
        "exited 9"
        in _run(
            runner,
            companion=_stub_companion(tmp_path / "status", body="exit 9\n"),
            launch=runner.subprocess_role_launch,
        ).refusal_reason
    ), "an unfamiliar exit status must survive the process boundary"


def test_the_parent_launches_nothing_when_the_role_input_or_request_is_not_closed(tmp_path):
    """`launched` is false for these, and that field is the one final provisioning reads.

    The contract forbids reinterpreting a PRE-EXEC `store-unavailable` as a target-write
    ambiguity, and after a launch the object alone cannot say which side of the exec
    produced it. So a refusal taken before any child exists has to stay distinguishable
    from one taken after -- which is also why the recording double must register NO call.
    """
    runner = _runner()
    launches = []

    def _record(*, argv, environ, request_bytes, timeout_seconds):
        launches.append((argv, dict(environ), request_bytes, timeout_seconds))
        return runner.RoleCompletion(
            stdout=b'{"version":1,"status":"ok"}', exit_status=0, timed_out=False
        )

    companion = _stub_companion(tmp_path / "pkg", body="exit 0\n")
    mismatched = _run(
        runner,
        companion=companion,
        launch=_record,
        role_input=_child().ClosedRoleInput(
            role_name="metadata-reader", key_description="lpm-op-value-reader", descriptors=()
        ),
    )
    unencodable = _run(
        runner,
        companion=companion,
        launch=_record,
        role_request={"version": 1, "external_call_timeout_seconds": 1.5},
    )

    assert launches == [], "a refused input must never reach a child"
    assert mismatched.launched is False
    assert mismatched.result_object == {"version": 1, "status": "unavailable"}
    assert "requires key description" in mismatched.refusal_reason
    assert unencodable.launched is False
    assert "not canonical JSON" in unencodable.refusal_reason


def test_a_child_that_outlives_the_parent_deadline_is_terminated_and_never_read(tmp_path):
    """A deadline is neither an abnormal exit nor absence: it is this role's closed failure.

    Driven against a real sleeping child, because the property under test is that the PARENT
    stops waiting and takes the child down with it -- against a double it would only be
    asserting its own flag. The child's output is deliberately a PERFECTLY CONFORMING
    object written AFTER the sleep, so a parent that merely waited longer would pass with a
    success: the only way through is to have terminated the child before it got there.

    The control alongside it writes the same marker INSIDE its deadline and answers
    normally, which is what makes the missing marker above evidence of termination rather
    than evidence that the write was unreachable.
    """
    runner = _runner()
    assert (
        "timed_out" in runner.RoleCompletion.__dataclass_fields__
    ), "a completion must be able to say the parent's deadline terminated the child"
    late = tmp_path / "late"
    companion = _stub_companion(
        tmp_path / "pkg",
        body=(
            "sleep 5\n"
            f'printf "ran" > "{late}"\n'
            'printf \'{"version":1,"status":"ok","item":null}\'\n'
        ),
    )

    outcome = _run(
        runner, companion=companion, launch=runner.subprocess_role_launch, timeout_seconds=0.25
    )

    assert outcome.result_object == {"version": 1, "status": "unavailable"}
    assert outcome.launched is True
    assert "deadline" in outcome.refusal_reason
    assert not late.exists(), "the child must be terminated, not merely stopped waiting for"

    mark = tmp_path / "inside"
    control = _stub_companion(
        tmp_path / "control",
        body=(f'printf "ran" > "{mark}"\n' 'printf \'{"version":1,"status":"ok","item":null}\'\n'),
    )

    inside = _run(runner, companion=control, launch=runner.subprocess_role_launch)

    assert inside.refusal_reason is None
    assert mark.read_text(encoding="utf-8") == "ran"
