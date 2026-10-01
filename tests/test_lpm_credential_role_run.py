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

# Placed in a DUPLICATE member NAME, which is the one piece of a nonconforming result that
# the canonical parser quotes back in its own defect reason.
_DUPLICATE_SENTINEL = "sk-ant-oat0-in-a-member-name"

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


def _duplicate_member_body(*, name):
    """A `printf` emitting an otherwise-conforming object with `name` repeated."""
    members = f'"version":1,"status":"ok","{name}":1,"{name}":2'
    return "printf '{" + members + "}'\n"


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
                "not one JSON object",
            ),
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


def test_a_parse_failure_reason_quotes_nothing_the_child_chose(tmp_path):
    """A duplicate member NAME is child-controlled, and the canonical parser quotes it.

    `parse_canonical_json` reports `duplicate member name: <name>`, which is exactly right
    for a generic parser and exactly wrong to embed HERE: this reason reaches
    `RoleOutcome.refusal_reason` and from there a manager log, so a token placed in a
    duplicate member name was logged by the very check that rejected the result. The shape
    checks already refuse to quote a child's status or member names; this was the one path
    still passing upstream text through.

    So every parser failure maps to one static reason at this boundary. The distinction
    between malformed JSON and a duplicate member is lost deliberately -- both are the same
    closed failure object to the manager, and keeping the distinction would mean auditing a
    SHARED parser's message text for secrets on every change to it.
    """
    runner = _runner()
    companion = _stub_companion(
        tmp_path / "sentinel",
        body=_duplicate_member_body(name=_DUPLICATE_SENTINEL),
    )

    outcome = _run(runner, companion=companion, launch=runner.subprocess_role_launch)

    assert outcome.result_object == {"version": 1, "status": "unavailable"}
    assert outcome.launched is True
    assert "not one JSON object" in outcome.refusal_reason
    assert _DUPLICATE_SENTINEL not in outcome.refusal_reason
    assert _DUPLICATE_SENTINEL not in str(outcome.result_object)


def test_a_spawn_that_never_starts_is_this_role_s_closed_failure_not_an_exception(tmp_path):
    """`subprocess_role_launch` caught only `TimeoutExpired`; an exec `OSError` escaped.

    A missing interpreter raises `FileNotFoundError` and a non-executable one raises
    `PermissionError`, both `OSError`. Escaping, they reach the manager as an exception
    rather than as this role's closed failure object -- and the contract is explicit that a
    pre-exec key, permission or exec failure "MUST produce that exact store-unavailable role
    result without target validation or target action". An exception produces no result at
    all, so every caller downstream would have to know to catch it.

    Driven against the REAL adapter with real unusable paths, because an injected
    `RoleCompletion` cannot raise what the adapter fails to catch: the double is downstream
    of the except clause under test.

    `launched` must be FALSE here. A spawn that never started is earlier than a pre-exec
    launcher refusal -- definitively no role, store or target action -- and that is the one
    field final provisioning reads to know a target write cannot be ambiguous.
    """
    runner = _runner()
    unexecutable = tmp_path / "not-executable"
    unexecutable.write_text("#!/bin/sh\n", encoding="utf-8")
    unexecutable.chmod(0o644)

    for python_executable, label in (
        (str(tmp_path / "absent-interpreter"), "missing"),
        (str(unexecutable), "unexecutable"),
    ):
        companion = _roles().PackagedCompanion(
            python_executable=python_executable, packaged_companion=str(tmp_path / "companion.py")
        )

        outcome = _run(runner, companion=companion, launch=runner.subprocess_role_launch)

        assert outcome.result_object == {"version": 1, "status": "unavailable"}, label
        assert outcome.launched is False, label
        assert "could not be started" in outcome.refusal_reason, label


def test_a_nonzero_exit_is_abnormal_however_conforming_the_output_looks(tmp_path):
    """A child that printed a perfect answer and THEN exited nonzero did not answer.

    This is the sharpest shape on the whole boundary, because the output alone is
    indistinguishable from a real one: `{"version":1,"status":"ok","item":null}` asserts
    AUTHORITATIVE ABSENCE, and absence is what licenses a genesis create. A parent that
    read the object and shrugged at the status would let a crashing child authorize a
    write against a record it never actually looked up.

    The status is therefore checked BEFORE the output is interpreted at all. That does not
    swallow a launcher's pre-exec refusal: a launcher that emits its closed failure object
    has DONE its job and exits 0 to say so, which is what keeps `unavailable`-because-we-
    refused distinguishable from `unavailable`-because-we-crashed.
    """
    runner = _runner()
    companion = _stub_companion(
        tmp_path / "pkg",
        body=('printf \'{"version":1,"status":"ok","item":null}\'\nexit 9\n'),
    )

    outcome = _run(runner, companion=companion, launch=runner.subprocess_role_launch)

    assert outcome.result_object == {"version": 1, "status": "unavailable"}
    assert outcome.launched is True
    assert "exited 9 abnormally" in outcome.refusal_reason
    assert "item" not in str(outcome.result_object), "the discarded answer must not survive"


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


def test_no_inherited_credential_override_reaches_the_launcher_child(tmp_path):
    """The parent scrubs at the CHILD-SPAWN boundary, so a token cannot be passed IN.

    This is the other half of the no-token guarantee, and the half a reader is likely to
    assume rather than check. The child's own scrub protects the ROLE process, but it runs
    INSIDE a launcher that has already started -- so without this one the launcher begins
    life holding whatever credential override its parent inherited, including, exactly, the
    manager service-account variable for the role whose key it is about to fetch. A
    launcher that could find a usable token already in its environment has a second,
    unaudited source for one, and the keyring check it passes would prove nothing about
    which token the role actually ran with.

    The survivors are asserted alongside the removals because the scrub is specified as
    copying what passes rather than deleting what fails: a child handed an EMPTY
    environment would satisfy the removals and still be wrong.
    """
    runner = _runner()
    seen = tmp_path / "env"
    companion = _stub_companion(
        tmp_path / "pkg",
        body=(f'env > "{seen}"\n' 'printf \'{"version":1,"status":"ok","item":null}\'\n'),
    )

    outcome = _run(runner, companion=companion, launch=runner.subprocess_role_launch)

    environment = seen.read_text(encoding="utf-8")
    names = sorted(line.split("=", 1)[0] for line in environment.splitlines() if "=" in line)
    assert outcome.refusal_reason is None
    assert {"PATH", "HOME"} <= set(names), "the scrub copies survivors, it does not clear"
    assert [
        name for name in names if name.startswith(("LPM_", "OP_", "ANTHROPIC_", "CLAUDE"))
    ] == []
    assert "inherited-manager" not in environment
    assert "inherited-manager" not in str(outcome.result_object)


def test_a_child_s_standard_error_never_reaches_the_parent(tmp_path, capfd):
    """NOT CAPTURING a child's stderr is not suppressing it -- it is INHERITING fd 2.

    A launcher child runs `keyctl` and, later, `op`; neither is manager-owned code and
    neither can be vouched for about what it writes when it fails. Left unredirected, the
    child's fd 2 IS the parent's, so any diagnostic it emits lands verbatim in the manager's
    own log -- the one surface the contract requires to stay secret-free. The parent cannot
    filter what it never chose to receive, so the sink is explicit and the bytes are
    discarded rather than buffered: a captured diagnostic is one more place a token could
    sit waiting to be logged by someone else.

    Read at the FILE-DESCRIPTOR level (`capfd`, not `capsys`), because a child writes to
    fd 2 directly and never touches this process's `sys.stderr` object -- the exact reason
    an in-process assertion would pass while the bytes still reached the terminal.
    """
    runner = _runner()
    companion = _stub_companion(
        tmp_path / "pkg",
        body=(
            "printf 'keyctl-sentinel-must-not-escape\\n' >&2\n"
            'printf \'{"version":1,"status":"unavailable"}\'\n'
        ),
    )
    capfd.readouterr()

    outcome = _run(runner, companion=companion, launch=runner.subprocess_role_launch)

    streams = capfd.readouterr()
    assert outcome.result_object == {"version": 1, "status": "unavailable"}
    assert outcome.refusal_reason is None, "the role answered; this is its own result"
    assert "keyctl-sentinel-must-not-escape" not in streams.err
    assert "keyctl-sentinel-must-not-escape" not in streams.out
