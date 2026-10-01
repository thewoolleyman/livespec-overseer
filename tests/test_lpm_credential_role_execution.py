"""Actually RUNNING a closed credential role: the exec, the keyring and the deadline.

SPECIFICATION/contracts.md makes the credential-role launcher a short-lived child created
BEFORE any token retrieval, maps each closed role name to exactly one execution vector
`<resolved-python> -I -S <packaged-companion> --credential-role <role-name>`, and requires
that token bytes NEVER return across the launcher pipe or enter the parent manager or
selection-brain process. `tests/test_lpm_credential_role_launcher.py` pins the launcher's
DECISIONS -- validation, the exact description match, the three `keyctl` vectors. This
module pins what happens when those decisions are EXECUTED.

EVERY OS PRIMITIVE IS INJECTED, so every branch is reachable without a keyring, a token or
a privileged host: the in-child sequence is driven through a recording double of its three
primitives. Production keeps the fixed `/usr/bin/keyctl` vectors and a real `execve`.

A SUCCESSFUL LAUNCH HAS NO RETURN VALUE -- the process is REPLACED -- so the double raises
`SystemExit` where a real `execve` would never come back, and the assertions read the
RECORDED exec rather than a returned result. That inversion is the point rather than a
testing convenience: a function that cannot return success cannot return a token either.
"""

from __future__ import annotations

import importlib
import os
import pathlib

import pytest

__all__: list[str] = []

_PYTHON = "/usr/bin/python3"
_COMPANION = "/pkg/_lpm_role_main.py"
_TOKEN = "ops-token-7a1f"
_SERIAL = "884422"
_UID = 4242

# Deliberately carries one member of every arm of the closed credential-override set --
# the exact `CLAUDECODE` spelling, an `ANTHROPIC_*`, a `CLAUDE_*`, an `OP_*` and one of the
# six manager service-account variables -- so a child environment that passed only because
# the scrub happened to miss an arm cannot pass here.
_INHERITED = {
    "PATH": "/usr/bin",
    "HOME": "/home/operator",
    "CLAUDECODE": "1",
    "ANTHROPIC_API_KEY": "consumer-override",
    "CLAUDE_CODE_OAUTH_TOKEN": "consumer-oauth",
    "OP_SERVICE_ACCOUNT_TOKEN": "inherited-op",
    "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN": "inherited-manager",
}
_SURVIVORS = {"PATH": "/usr/bin", "HOME": "/home/operator"}

_TOKEN_BEARING = (
    ("metadata-reader", "LPM_METADATA_READER_OP_SERVICE_ACCOUNT_TOKEN"),
    ("lifecycle-writer", "LPM_METADATA_WRITER_OP_SERVICE_ACCOUNT_TOKEN"),
    ("report-writer", "LPM_METADATA_WRITER_OP_SERVICE_ACCOUNT_TOKEN"),
    ("recovery-writer", "LPM_METADATA_WRITER_OP_SERVICE_ACCOUNT_TOKEN"),
    ("final-provisioning", "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN"),
)


def _child():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_role_child.py"
    assert module_path.is_file(), "overseer/_lpm_role_child.py must exist"
    return importlib.import_module("_lpm_role_child")


def _roles():
    return importlib.import_module("_lpm_roles")


class _ProcessOS:
    """A recording double of the child's three primitives: uid, one `keyctl` run, the exec.

    `answers` maps a `keyctl` verb to the outcome it must report; a verb absent from it
    succeeds with this double's canonical output. `exec_returns` models the only way a real
    `execve` ever comes back -- by failing -- and otherwise the double raises `SystemExit`
    so a test cannot mistake a returning launcher for a successful one.
    """

    def __init__(self, child, *, description=None, answers=None, payload=None, exec_returns=False):
        self.child = child
        self.calls = []
        self.replaced = []
        self.description = description
        self.answers = answers or {}
        self.payload = _TOKEN.encode("utf-8") if payload is None else payload
        self.exec_returns = exec_returns

    def effective_uid(self):
        return _UID

    def run(self, *, argv):
        verb = argv[1]
        self.calls.append(verb)
        if verb in self.answers:
            return self.answers[verb]
        return self.child.CommandOutcome(exit_status=0, stdout=self._canonical(verb=verb))

    def _canonical(self, *, verb):
        if verb == "search":
            return f"{_SERIAL}\n".encode()
        if verb == "rdescribe":
            return f"user;{_UID};{_UID};3f0b0000;{self.description}\n".encode()
        return self.payload

    def replace_process(self, *, argv, environ):
        self.replaced.append((argv, dict(environ)))
        if self.exec_returns:
            return
        raise SystemExit(0)


def _companion():
    return _roles().PackagedCompanion(python_executable=_PYTHON, packaged_companion=_COMPANION)


def _launch(child, process_os, *, role_name, key_description, descriptors, environ=None):
    return child.launch_credential_role(
        role_input=child.ClosedRoleInput(
            role_name=role_name, key_description=key_description, descriptors=descriptors
        ),
        companion=_companion(),
        environ=_INHERITED if environ is None else environ,
        process_os=process_os,
    )


def _as_registered(child, *, role_name, **overrides):
    """A double and a launch argument set that match the registry's own pairing exactly."""
    role = _roles().credential_role(name=role_name)
    process_os = _ProcessOS(child, description=role.key_description, **overrides)
    return process_os, {
        "role_name": role_name,
        "key_description": role.key_description,
        "descriptors": role.descriptors,
    }


def test_each_registered_consumer_role_is_replaced_by_its_own_closed_execution_vector():
    """Success is an exec, not a return: the role's exact vector and exactly its own token.

    The covered roles are driven together because the invariant is the same for all of
    them and the DIFFERENCES are what matter: each token-bearing role reaches its exec with
    exactly one manager-named variable, while tokenless `target-status` reaches its own
    with no keyring call and no credential variable at all.
    """
    child = _child()

    for role_name, variable in _TOKEN_BEARING:
        process_os, arguments = _as_registered(child, role_name=role_name)

        with pytest.raises(SystemExit):
            _launch(child, process_os, **arguments)

        argv, environ = process_os.replaced[-1]
        assert argv == (_PYTHON, "-I", "-S", _COMPANION, "--credential-role", role_name)
        assert process_os.calls == ["search", "rdescribe", "pipe"]
        assert environ[variable] == _TOKEN
        assert environ == {**_SURVIVORS, variable: _TOKEN}

    tokenless, arguments = _as_registered(child, role_name="target-status")
    with pytest.raises(SystemExit):
        _launch(child, tokenless, **arguments)

    argv, environ = tokenless.replaced[-1]
    assert argv == (_PYTHON, "-I", "-S", _COMPANION, "--credential-role", "target-status")
    assert tokenless.calls == [], "a null key description means no keyring call at all"
    assert environ == _SURVIVORS


def test_the_in_child_launcher_refuses_a_registry_mismatch_before_any_keyring_call():
    """A mismatch is answered with that role's own closed object, and the keyring is untouched.

    The refusal has to come before `keyctl search`, not merely before the payload read: a
    process asked to run a role the registry does not pair with that key has already proved
    it cannot be trusted with the lookup, and a search is itself an authority exercise.
    """
    child = _child()
    process_os = _ProcessOS(child, description="lpm-op-metadata-reader")

    extra_descriptor = _launch(
        child,
        process_os,
        role_name="metadata-reader",
        key_description="lpm-op-metadata-reader",
        descriptors=("target-reference-lock",),
    )
    wrong_key = _launch(
        child,
        process_os,
        role_name="final-provisioning",
        key_description="lpm-op-metadata-reader",
        descriptors=("target-reference-lock",),
    )
    unregistered = _launch(
        child, process_os, role_name="value-reader", key_description=None, descriptors=()
    )

    assert extra_descriptor.failure_object == {"version": 1, "status": "unavailable"}
    assert "may inherit exactly" in extra_descriptor.reason
    assert wrong_key.failure_object == {"version": 1, "status": "store-unavailable"}
    assert "requires key description" in wrong_key.reason
    assert "unregistered credential role" in unregistered.reason
    assert process_os.calls == []
    assert process_os.replaced == []


def test_an_exec_that_returns_is_itself_the_pre_exec_failure_that_role_must_emit():
    """`replace_process` coming back at all is the contract's failure-to-exec, not a success.

    This is also the one refusal reached AFTER a payload was piped, so it is where the
    secret-free guarantee is actually at risk: the reason names the step, never the value.
    """
    child = _child()
    process_os, arguments = _as_registered(child, role_name="final-provisioning", exec_returns=True)

    refusal = _launch(child, process_os, **arguments)

    assert process_os.calls == ["search", "rdescribe", "pipe"]
    assert refusal.failure_object == {"version": 1, "status": "store-unavailable"}
    assert "could not be replaced" in refusal.reason
    assert _TOKEN not in refusal.reason
    assert _TOKEN not in str(refusal.failure_object)


def test_a_key_whose_description_is_not_an_exact_match_is_never_piped():
    """`rdescribe` GATES the pipe, so the assertion that matters is the absence of `pipe`.

    Every key below EXISTS and was found by the search; the launcher refuses to READ it.
    Owning-user bits alone, another user's ownership, a key that is not a `user` key and a
    description recognized only in part are each the same answer, because a key whose
    identity was only partly recognized is not the key the role was promised -- and no
    later check can un-read a payload.
    """
    child = _child()
    expected = "lpm-op-metadata-reader"

    for raw in (
        f"user;{_UID};{_UID};3f010000;{expected}",
        f"user;{_UID + 1};{_UID};3f0b0000;{expected}",
        f"keyring;{_UID};{_UID};3f0b0000;{expected}",
        f"user;{_UID};{_UID};3f0b0000;{expected} extra",
    ):
        process_os, arguments = _as_registered(
            child,
            role_name="metadata-reader",
            answers={"rdescribe": child.CommandOutcome(exit_status=0, stdout=raw.encode())},
        )

        refusal = _launch(child, process_os, **arguments)

        assert process_os.calls == ["search", "rdescribe"], f"piped on {raw!r}"
        assert process_os.replaced == []
        assert refusal.failure_object == {"version": 1, "status": "unavailable"}
        assert "owner-only key" in refusal.reason


def test_every_other_keyring_step_failure_is_the_same_fail_closed_refusal():
    """Search, serial, description-read, pipe and decode failures all end before the exec.

    They are driven together because the contract maps them to ONE outcome -- that role's
    own closed failure object -- and what is worth pinning individually is HOW FAR each
    got: a search that found no key must not be reported as a key whose payload could not
    be read, or a later reader will reconcile against a key that was never there.
    """
    child = _child()
    failed = child.CommandOutcome(exit_status=1, stdout=b"")

    for answers, calls, reason in (
        ({"search": failed}, ["search"], "not in the user keyring"),
        (
            {"search": child.CommandOutcome(exit_status=0, stdout=b"not-a-serial\n")},
            ["search"],
            "returned no serial",
        ),
        ({"rdescribe": failed}, ["search", "rdescribe"], "description could not be read"),
        ({"pipe": failed}, ["search", "rdescribe", "pipe"], "payload could not be piped"),
        (
            {"pipe": child.CommandOutcome(exit_status=0, stdout=b"\xff\xfe")},
            ["search", "rdescribe", "pipe"],
            "payload is not UTF-8",
        ),
    ):
        process_os, arguments = _as_registered(child, role_name="lifecycle-writer", answers=answers)

        refusal = _launch(child, process_os, **arguments)

        assert process_os.calls == calls
        assert process_os.replaced == []
        assert refusal.failure_object == {"version": 1, "status": "unavailable"}
        assert reason in refusal.reason
        assert refusal.reason.startswith("lifecycle-writer ")


def test_the_host_primitives_are_a_real_uid_a_real_command_run_and_a_real_exec(tmp_path):
    """The PRODUCTION seam, driven against real processes rather than against the double.

    Three things the injected double structurally cannot prove. That `run` reports a real
    exit status and the real bytes a `keyctl` vector wrote -- the double answers from a
    table, so a seam that dropped the status or the output would pass every test above.
    That `effective_uid` is THIS process's own uid, which is the value the owner check
    compares against. And that a failed `execve` RETURNS instead of raising, because
    returning is precisely the signal `launch_credential_role` reads as failure-to-exec: a
    seam that let the `OSError` escape would turn that closed refusal into a crash.
    """
    child = _child()
    assert "HostProcessOS" in child.__all__, "the production primitives are part of the surface"
    host = child.HostProcessOS()
    stub = tmp_path / "keyctl"
    stub.write_text("#!/bin/sh\nprintf '884422\\n'\nexit 3\n", encoding="utf-8")
    stub.chmod(0o755)

    outcome = host.run(argv=(str(stub), "search"))

    assert outcome.exit_status == 3
    assert outcome.stdout == b"884422\n"
    assert host.effective_uid() == os.geteuid()
    assert host.replace_process(argv=(str(tmp_path / "absent"),), environ={}) is None
