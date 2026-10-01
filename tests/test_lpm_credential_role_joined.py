"""The JOINED chain through real processes: parent → launcher child → exec → role → parent.

Every other test in this family drives ONE side. `test_lpm_credential_role_execution.py`
runs the in-child sequence against injected primitives, so no process is ever replaced.
`test_lpm_credential_role_run.py` runs the parent against a shell stub standing in for the
interpreter, so the product launcher never executes. Both are the right shape for what they
cover, and together they still do not prove the seam between them: that a real parent
spawning the real closed vector reaches the real `launch_credential_role`, whose real
`execve` becomes the role process, whose result travels back.

THE FIXTURE KEYRING LIVES INSIDE THE CHILD, WHICH IS THE POINT. The companion resolves its
own `ChildProcessOS` after it starts, so the fixture token exists only in that process. The
parent has no primitive that could produce it, never names it, and is asserted not to hold
it anywhere — in its result, its reason, or its own streams. A fixture injected from the
parent would prove the plumbing while destroying the property the plumbing exists for.

`replace_process` IS THE PRODUCTION ONE. The companion substitutes the keyring reads and
nothing else, so the exec on the far side is a real `os.execve` of a real interpreter
against a real companion file — and the assertions below read what that process actually
got rather than what the parent intended to send.

TELEMETRY TRAVELS BY FILE, NOT IN THE RESULT, and that is a finding rather than a
convenience: the closed result shapes have NO free-form member a test could report through.
A commit status carries exactly a status and `committed_at`. So the role writes what it
observed to a side file and returns a shape its own role is actually allowed to return,
which also keeps the assertions honest about what crossed the result boundary.

THE COMPANION IS SUPPLIED BY THE TEST because the packaged companion is the next slice's
deliverable. What is under test here is the product launcher, the product exec and the
product parent; the companion is the harness that lets those three meet.

NO COVERAGE SUBPROCESS HAZARD: the parent hands the child an explicit, scrubbed environment
that carries no `COVERAGE_PROCESS_START`, so the real Python child cannot self-instrument
and cannot race the suite's own coverage data.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import os
import pathlib
import sys

__all__: list[str] = []

_TOKEN = "fixture-keyring-token-7f3a"
_INHERITED_IMPOSTOR = "inherited-value-that-must-be-scrubbed"
_READER_VARIABLE = "LPM_METADATA_READER_OP_SERVICE_ACCOUNT_TOKEN"
_VALUE_READER_VARIABLE = "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN"
_LOCK_SENTINEL = "target-reference-lock-contents"
_UNRELATED_SENTINEL = "unrelated-descriptor-contents"
_REQUEST = {
    "version": 1,
    "mode": "get",
    "record_id": "rec-1",
    "op_executable": "/usr/bin/op",
}
# Final provisioning's input carries NO `mode` -- that member belongs to the reader's and
# the writer's inputs. Reusing the reader's request here would hand this role a request
# shape its own contract does not define.
_PROVISIONING_REQUEST = {
    "version": 1,
    "target_ref": "tgt-0001",
    "consumer_run_id": "run-a",
    "record_id": "rec-1",
    "value_generation": "0f9c0a1e-0000-4000-8000-000000000000",
    "value_ref": "ref-1",
    "lease_expires_at": "2026-09-13T10:00:00Z",
    "external_call_timeout_seconds": 30,
    "op_executable": "/usr/bin/op",
}
_READER_OK = '{"version":1,"status":"ok","item":{"item_id":"rev-1","record":{}}}'
_COMMIT_OK = '{"version":1,"status":"committed","committed_at":"2026-09-12T10:00:00Z"}'

# Written to disk and run by a real interpreter under `-I -S`. Placeholders are substituted
# rather than formatted so the JSON braces below need no escaping.
_COMPANION_SOURCE = '''
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, "__OVERSEER_DIR__")

import _lpm_role_child
import _lpm_roles

VARIABLE = "__VARIABLE__"
TOKEN = "__TOKEN__"
KEY_DESCRIPTION = "__KEY_DESCRIPTION__"
DESCRIPTORS = __DESCRIPTORS__
PROBE_FDS = __PROBE_FDS__
PID_FILE = "__PID_FILE__"
MARKER = "__MARKER__"
TELEMETRY = "__TELEMETRY__"
RESULT = r"""__RESULT__"""
HANG_SECONDS = __HANG_SECONDS__


class FixtureKeyring:
    """The keyring reads, answered inside this process; the exec is the production one."""

    def effective_uid(self):
        return os.geteuid()

    def run(self, *, argv):
        verb = argv[1]
        if verb == "search":
            stdout = b"777\\n"
        elif verb == "rdescribe":
            owner = "user;%d;%d;3f0b0000;%s\\n" % (os.geteuid(), os.getgid(), KEY_DESCRIPTION)
            stdout = owner.encode("utf-8")
        else:
            stdout = TOKEN.encode("utf-8")
        return _lpm_role_child.CommandOutcome(exit_status=0, stdout=stdout)

    def replace_process(self, *, argv, environ):
        return _lpm_role_child.HostProcessOS().replace_process(argv=argv, environ=environ)


def _descriptor_reads():
    """What each probed descriptor number actually holds in THIS process.

    `pread` rather than `read` so the shared file offset cannot make the answer depend on
    whether the parent happened to read first. Content is reported rather than mere
    openness because descriptor NUMBERS are reused: a number that reopened as something
    else would otherwise look like a surviving inheritance.
    """
    reads = {}
    for fd in PROBE_FDS:
        try:
            reads[str(fd)] = os.pread(fd, 128, 0).decode("utf-8")
        except OSError as failure:
            reads[str(fd)] = "errno:%s" % failure.errno
    return reads


def _role():
    request = sys.stdin.read()
    if HANG_SECONDS:
        time.sleep(HANG_SECONDS)
        open(MARKER, "w").close()
    # Counted with its own control: opening one extra descriptor must move the count, or a
    # count that happened to be right would prove nothing about the count's sensitivity.
    baseline = len(os.listdir("/proc/self/fd"))
    probe = os.open(os.devnull, os.O_RDONLY)
    with_one_more = len(os.listdir("/proc/self/fd"))
    os.close(probe)
    with open(TELEMETRY, "w") as handle:
        json.dump(
            {
                "token_sha256": hashlib.sha256(os.environ[VARIABLE].encode("utf-8")).hexdigest(),
                "request_sha256": hashlib.sha256(request.encode("utf-8")).hexdigest(),
                "isolated": sys.flags.isolated,
                "no_site": sys.flags.no_site,
                "descriptor_count": baseline,
                "descriptor_count_with_one_more": with_one_more,
                "descriptor_reads": _descriptor_reads(),
                "pid": os.getpid(),
                "credential_names": sorted(
                    name
                    for name in os.environ
                    if name.startswith(("LPM_", "OP_", "ANTHROPIC_", "CLAUDE"))
                ),
            },
            handle,
        )
    sys.stdout.write(RESULT)


def _launcher():
    with open(PID_FILE, "w") as handle:
        handle.write(str(os.getpid()))
    refusal = _lpm_role_child.launch_credential_role(
        role_input=_lpm_role_child.ClosedRoleInput(
            role_name=sys.argv[sys.argv.index("--credential-role") + 1],
            key_description=KEY_DESCRIPTION,
            descriptors=DESCRIPTORS,
        ),
        companion=_lpm_roles.PackagedCompanion(
            python_executable=sys.executable, packaged_companion=os.path.abspath(__file__)
        ),
        environ=os.environ,
        process_os=FixtureKeyring(),
    )
    sys.stdout.write(json.dumps(refusal.failure_object))


if VARIABLE in os.environ:
    _role()
else:
    _launcher()
'''


def _module(name):
    return importlib.import_module(name)


def _canonical(value):
    return _module("_lpm_canonical").canonical_json_bytes(value=value).unwrap()


def _paths(tmp_path):
    return tmp_path / "launcher-pid", tmp_path / "ran-past-deadline", tmp_path / "telemetry.json"


@dataclasses.dataclass(frozen=True, kw_only=True)
class _Scenario:
    """One joined run: which role, which descriptors it is handed, what it answers with."""

    role_name: str = "metadata-reader"
    variable: str = _READER_VARIABLE
    role_request: dict = dataclasses.field(default_factory=lambda: dict(_REQUEST))
    descriptor_fds: dict = dataclasses.field(default_factory=dict)
    probe_fds: tuple = ()
    result: str = _READER_OK
    hang: int = 0
    timeout_seconds: float = 60.0


def _write_companion(tmp_path, scenario):
    role = _module("_lpm_roles").credential_role(name=scenario.role_name)
    pid_file, marker, telemetry = _paths(tmp_path)
    overseer_dir = pathlib.Path(__file__).parents[1] / "overseer"
    path = tmp_path / "_lpm_role_main.py"
    path.write_text(
        _COMPANION_SOURCE.replace("__OVERSEER_DIR__", str(overseer_dir))
        .replace("__VARIABLE__", scenario.variable)
        .replace("__TOKEN__", _TOKEN)
        .replace("__KEY_DESCRIPTION__", role.key_description)
        .replace("__DESCRIPTORS__", repr(role.descriptors))
        .replace("__PROBE_FDS__", repr(scenario.probe_fds))
        .replace("__PID_FILE__", str(pid_file))
        .replace("__MARKER__", str(marker))
        .replace("__TELEMETRY__", str(telemetry))
        .replace("__RESULT__", scenario.result)
        .replace("__HANG_SECONDS__", str(scenario.hang)),
        encoding="utf-8",
    )
    return path


def _run(tmp_path, scenario=None):
    scenario = _Scenario() if scenario is None else scenario
    runner = _module("_lpm_role_runner")
    role = _module("_lpm_roles").credential_role(name=scenario.role_name)
    path = _write_companion(tmp_path, scenario)
    outcome = runner.run_credential_role(
        role_input=_module("_lpm_role_child").ClosedRoleInput(
            role_name=scenario.role_name,
            key_description=role.key_description,
            descriptors=role.descriptors,
            descriptor_fds=scenario.descriptor_fds,
        ),
        companion=_module("_lpm_roles").PackagedCompanion(
            python_executable=sys.executable, packaged_companion=str(path)
        ),
        role_request=scenario.role_request,
        # Carries an IMPOSTOR under the very name this role's token is installed as, so a
        # scrub that missed it would be caught by the digest rather than by an absence.
        environ={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            scenario.variable: _INHERITED_IMPOSTOR,
            "ANTHROPIC_API_KEY": "consumer-override",
        },
        timeout_seconds=scenario.timeout_seconds,
        launch=runner.subprocess_role_launch,
    )
    return outcome, _paths(tmp_path)


def _telemetry(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_real_parent_launcher_exec_role_chain_joins_up(tmp_path, capfd):
    """One real chain, end to end, asserted on what the ROLE process actually received."""
    capfd.readouterr()

    outcome, (pid_file, _, telemetry_path) = _run(tmp_path)

    streams = capfd.readouterr()
    assert outcome.refusal_reason is None
    assert outcome.launched is True
    seen = _telemetry(telemetry_path)

    # The exec happened and carried THIS role's token -- the fixture's, not the impostor's
    # that the parent inherited under the same name.
    assert seen["token_sha256"] == hashlib.sha256(_TOKEN.encode("utf-8")).hexdigest()
    assert seen["token_sha256"] != hashlib.sha256(_INHERITED_IMPOSTOR.encode("utf-8")).hexdigest()
    assert seen["credential_names"] == [_READER_VARIABLE], "only its own variable survives"

    # The launcher and the role are ONE process: `execve` replaced the image rather than
    # forking a second one, which is what makes "the parent never holds a token" structural.
    assert seen["pid"] == int(pid_file.read_text(encoding="utf-8"))

    # `-I -S` survived the exec, so the role runs with environment-driven import and all
    # site-package discovery disabled, as every substantive manager path must.
    assert seen["isolated"] == 1
    assert seen["no_site"] == 1

    # The request crossed the PIPE into the exec'd role, not the argument vector.
    assert seen["request_sha256"] == hashlib.sha256(_canonical(dict(_REQUEST))).hexdigest()

    # A role declaring NO descriptors inherits none beyond stdio. The 4th is the one the
    # enumeration itself opens, and the control proves the count would move otherwise.
    assert seen["descriptor_count_with_one_more"] == seen["descriptor_count"] + 1
    assert seen["descriptor_count"] == 4

    # The parent never receives the token -- not in the result, the reason, or its streams.
    assert _TOKEN not in json.dumps(outcome.result_object)
    assert _TOKEN not in streams.out
    assert _TOKEN not in streams.err


def test_the_allowlisted_descriptor_survives_into_the_role_and_an_unrelated_one_does_not(
    tmp_path,
):
    """A validated descriptor allowlist that never reaches the process allows nothing.

    `final-provisioning` must itself own and CONTINUOUSLY HOLD the target-reference lock
    from before target validation through its terminal evidence update, so the lock
    descriptor has to survive both the spawn and the `execve`. Validating the allowlist and
    then letting the default close every descriptor would leave that role unable to hold
    the one thing the contract says it must.

    The unrelated descriptor is the other half, and without it this would pass on a launch
    that simply inherited everything. Both are asserted on CONTENT rather than openness,
    because descriptor numbers are reused: a number reopened as something else would
    otherwise read as a surviving inheritance.
    """
    child = _module("_lpm_role_child")
    assert (
        "descriptor_fds" in child.ClosedRoleInput.__dataclass_fields__
    ), "a validated descriptor allowlist must be able to carry the descriptors it allows"
    lock_path = tmp_path / "lock"
    lock_path.write_text(_LOCK_SENTINEL, encoding="utf-8")
    unrelated_path = tmp_path / "unrelated"
    unrelated_path.write_text(_UNRELATED_SENTINEL, encoding="utf-8")
    lock_fd = os.open(lock_path, os.O_RDONLY)
    unrelated_fd = os.open(unrelated_path, os.O_RDONLY)
    try:
        outcome, (_, _, telemetry_path) = _run(
            tmp_path,
            _Scenario(
                role_name="final-provisioning",
                variable=_VALUE_READER_VARIABLE,
                role_request=_PROVISIONING_REQUEST,
                descriptor_fds={"target-reference-lock": lock_fd},
                probe_fds=(lock_fd, unrelated_fd),
                result=_COMMIT_OK,
            ),
        )
    finally:
        os.close(lock_fd)
        os.close(unrelated_fd)

    assert outcome.refusal_reason is None
    reads = _telemetry(telemetry_path)["descriptor_reads"]
    assert reads[str(lock_fd)] == _LOCK_SENTINEL, "the allowlisted lock descriptor was closed"
    assert (
        reads[str(unrelated_fd)] != _UNRELATED_SENTINEL
    ), "a descriptor outside the allowlist reached the role"


def test_a_descriptor_set_that_disagrees_with_the_allowlist_launches_nothing(tmp_path):
    """The fds offered must be exactly the names the registry allows, checked before launch.

    Both directions are refusals and neither is cosmetic. A descriptor the registry does
    not grant would hand the role authority it was never promised; a missing one would let
    final provisioning start a write it cannot hold the lock for, which is the ambiguous
    outcome the whole lock exists to prevent. Nothing is launched either way.
    """
    runner = _module("_lpm_role_runner")
    launches = []

    def _record(*, argv, environ, request_bytes, timeout_seconds, inherited_fds):
        launches.append(inherited_fds)
        return runner.RoleCompletion(stdout=b"", exit_status=0, timed_out=False)

    def _attempt(*, role_name, descriptor_fds):
        role = _module("_lpm_roles").credential_role(name=role_name)
        return runner.run_credential_role(
            role_input=_module("_lpm_role_child").ClosedRoleInput(
                role_name=role_name,
                key_description=role.key_description,
                descriptors=role.descriptors,
                descriptor_fds=descriptor_fds,
            ),
            companion=_module("_lpm_roles").PackagedCompanion(
                python_executable=sys.executable, packaged_companion="/nonexistent/companion.py"
            ),
            role_request=_PROVISIONING_REQUEST if role_name == "final-provisioning" else _REQUEST,
            environ={"PATH": "/usr/bin:/bin"},
            timeout_seconds=5.0,
            launch=_record,
        )

    missing = _attempt(role_name="final-provisioning", descriptor_fds={})
    unexpected = _attempt(role_name="metadata-reader", descriptor_fds={"target-reference-lock": 9})

    assert launches == [], "a disagreeing descriptor set must never reach a child"
    assert missing.launched is False
    assert missing.result_object == {"version": 1, "status": "store-unavailable"}
    assert "descriptor" in missing.refusal_reason
    assert unexpected.launched is False
    assert "descriptor" in unexpected.refusal_reason


def test_the_joined_chain_is_deadline_bounded_and_the_exec_d_role_is_reaped(tmp_path):
    """The bound holds against the REAL chain, and the process it kills is not left behind.

    The role incarnation sleeps far past the deadline and only then writes its marker, so a
    parent that waited would be caught by the marker rather than by a timing guess. The
    reaping check reads `/proc/<pid>`: a killed-but-unreaped child would still have an entry
    there in state `Z`, so its absence is what distinguishes terminated from merely
    abandoned. The pid is the launcher's, which the success case above proves is also the
    role's.
    """
    outcome, (pid_file, marker, _) = _run(tmp_path, _Scenario(hang=120, timeout_seconds=15.0))

    assert outcome.result_object == {"version": 1, "status": "unavailable"}
    assert outcome.launched is True
    assert "deadline" in outcome.refusal_reason
    assert not marker.exists(), "the role was waited for instead of being terminated"
    pid = int(pid_file.read_text(encoding="utf-8"))
    assert not pathlib.Path(f"/proc/{pid}").exists(), "terminated but never reaped"
