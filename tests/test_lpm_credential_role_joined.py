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

THE COMPANION IS SUPPLIED BY THE TEST because the packaged companion is the next slice's
deliverable. What is under test here is the product launcher, the product exec and the
product parent; the companion is the harness that lets those three meet.

NO COVERAGE SUBPROCESS HAZARD: the parent hands the child an explicit, scrubbed environment
that carries no `COVERAGE_PROCESS_START`, so the real Python child cannot self-instrument
and cannot race the suite's own coverage data.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import pathlib
import sys

__all__: list[str] = []

_TOKEN = "fixture-keyring-token-7f3a"
_INHERITED_IMPOSTOR = "inherited-value-that-must-be-scrubbed"
_VARIABLE = "LPM_METADATA_READER_OP_SERVICE_ACCOUNT_TOKEN"
_REQUEST = {
    "version": 1,
    "mode": "get",
    "record_id": "rec-1",
    "op_executable": "/usr/bin/op",
}

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
PID_FILE = "__PID_FILE__"
MARKER = "__MARKER__"
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
            owner = "user;%d;%d;3f0b0000;lpm-op-metadata-reader\\n" % (os.geteuid(), os.getgid())
            stdout = owner.encode("utf-8")
        else:
            stdout = TOKEN.encode("utf-8")
        return _lpm_role_child.CommandOutcome(exit_status=0, stdout=stdout)

    def replace_process(self, *, argv, environ):
        return _lpm_role_child.HostProcessOS().replace_process(argv=argv, environ=environ)


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
    sys.stdout.write(
        json.dumps(
            {
                "version": 1,
                "status": "ok",
                "item": {
                    "item_id": "rev-1",
                    "record": {
                        "token_sha256": hashlib.sha256(
                            os.environ[VARIABLE].encode("utf-8")
                        ).hexdigest(),
                        "request_sha256": hashlib.sha256(request.encode("utf-8")).hexdigest(),
                        "isolated": sys.flags.isolated,
                        "no_site": sys.flags.no_site,
                        "descriptor_count": baseline,
                        "descriptor_count_with_one_more": with_one_more,
                        "pid": os.getpid(),
                        "credential_names": sorted(
                            name
                            for name in os.environ
                            if name.startswith(("LPM_", "OP_", "ANTHROPIC_", "CLAUDE"))
                        ),
                    },
                },
            }
        )
    )


def _launcher():
    with open(PID_FILE, "w") as handle:
        handle.write(str(os.getpid()))
    refusal = _lpm_role_child.launch_credential_role(
        role_input=_lpm_role_child.ClosedRoleInput(
            role_name=sys.argv[sys.argv.index("--credential-role") + 1],
            key_description="lpm-op-metadata-reader",
            descriptors=(),
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


def _companion(tmp_path, *, hang_seconds):
    """Write the companion and return it plus the pid and marker paths it reports through."""
    overseer_dir = pathlib.Path(__file__).parents[1] / "overseer"
    pid_file = tmp_path / "launcher-pid"
    marker = tmp_path / "role-ran-past-its-deadline"
    path = tmp_path / "_lpm_role_main.py"
    path.write_text(
        _COMPANION_SOURCE.replace("__OVERSEER_DIR__", str(overseer_dir))
        .replace("__VARIABLE__", _VARIABLE)
        .replace("__TOKEN__", _TOKEN)
        .replace("__PID_FILE__", str(pid_file))
        .replace("__MARKER__", str(marker))
        .replace("__HANG_SECONDS__", str(hang_seconds)),
        encoding="utf-8",
    )
    return path, pid_file, marker


def _run(tmp_path, *, hang_seconds=0, timeout_seconds=60.0):
    runner = _module("_lpm_role_runner")
    path, pid_file, marker = _companion(tmp_path, hang_seconds=hang_seconds)
    outcome = runner.run_credential_role(
        role_input=_module("_lpm_role_child").ClosedRoleInput(
            role_name="metadata-reader",
            key_description="lpm-op-metadata-reader",
            descriptors=(),
        ),
        companion=_module("_lpm_roles").PackagedCompanion(
            python_executable=sys.executable, packaged_companion=str(path)
        ),
        role_request=_REQUEST,
        # Carries an IMPOSTOR under the very name this role's token is installed as, so a
        # scrub that missed it would be caught by the digest rather than by an absence.
        environ={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            _VARIABLE: _INHERITED_IMPOSTOR,
            "ANTHROPIC_API_KEY": "consumer-override",
        },
        timeout_seconds=timeout_seconds,
        launch=runner.subprocess_role_launch,
    )
    return outcome, pid_file, marker


def test_the_real_parent_launcher_exec_role_chain_joins_up(tmp_path, capfd):
    """One real chain, end to end, asserted on what the ROLE process actually received."""
    capfd.readouterr()

    outcome, pid_file, _ = _run(tmp_path)

    streams = capfd.readouterr()
    assert outcome.refusal_reason is None
    assert outcome.launched is True
    record = outcome.result_object["item"]["record"]

    # The exec happened and carried THIS role's token -- the fixture's, not the impostor's
    # that the parent inherited under the same name.
    assert record["token_sha256"] == hashlib.sha256(_TOKEN.encode("utf-8")).hexdigest()
    assert record["token_sha256"] != hashlib.sha256(_INHERITED_IMPOSTOR.encode("utf-8")).hexdigest()
    assert record["credential_names"] == [_VARIABLE], "only its own variable survives"

    # The launcher and the role are ONE process: `execve` replaced the image rather than
    # forking a second one, which is what makes "the parent never holds a token" structural.
    assert record["pid"] == int(pid_file.read_text(encoding="utf-8"))

    # `-I -S` survived the exec, so the role runs with environment-driven import and all
    # site-package discovery disabled, as every substantive manager path must.
    assert record["isolated"] == 1
    assert record["no_site"] == 1

    # The request crossed the PIPE into the exec'd role, not the argument vector.
    assert record["request_sha256"] == hashlib.sha256(_canonical(_REQUEST)).hexdigest()

    # Descriptor allowlisting: `metadata-reader` declares no descriptors and inherits none
    # beyond stdio. The 4th is the one the enumeration itself opens, and the control proves
    # the count would move if anything else were held.
    assert record["descriptor_count_with_one_more"] == record["descriptor_count"] + 1
    assert record["descriptor_count"] == 4

    # The parent never receives the token -- not in the result, the reason, or its streams.
    assert _TOKEN not in json.dumps(outcome.result_object)
    assert _TOKEN not in streams.out
    assert _TOKEN not in streams.err


def test_the_joined_chain_is_deadline_bounded_and_the_exec_d_role_is_reaped(tmp_path):
    """The bound holds against the REAL chain, and the process it kills is not left behind.

    The role incarnation sleeps far past the deadline and only then writes its marker, so a
    parent that waited would be caught by the marker rather than by a timing guess. The
    reaping check reads `/proc/<pid>`: a killed-but-unreaped child would still have an entry
    there in state `Z`, so its absence is what distinguishes terminated from merely
    abandoned. The pid is the launcher's, which the success case above proves is also the
    role's.
    """
    outcome, pid_file, marker = _run(tmp_path, hang_seconds=120, timeout_seconds=15.0)

    assert outcome.result_object == {"version": 1, "status": "unavailable"}
    assert outcome.launched is True
    assert "deadline" in outcome.refusal_reason
    assert not marker.exists(), "the role was waited for instead of being terminated"
    pid = int(pid_file.read_text(encoding="utf-8"))
    assert not pathlib.Path(f"/proc/{pid}").exists(), "terminated but never reaped"
