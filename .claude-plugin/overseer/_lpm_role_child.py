"""The in-child launcher SEQUENCE: scrub, read the user keyring, become the role.

SPECIFICATION/contracts.md makes the credential-role launcher a short-lived child created
BEFORE any token retrieval. `_lpm_launcher` holds the parts of that contract which are pure
decisions — the registry validation, the exact `rdescribe` match, the three `keyctl`
argument vectors and the child environment. THIS module is the sequence those decisions
imply: it reapplies the complete closed scrub, runs those vectors in the contract's order,
installs only the corresponding manager-named variable and replaces the process with the
role's closed execution vector.

THE ORDER IS THE SECURITY PROPERTY, not the individual steps. `search` yields a serial,
`rdescribe` proves that serial names this user's owner-only key for exactly this role's
description, and only then may `pipe` read the payload. An implementation that piped first
would hand the bytes over before anything had established that the key was the one the role
was promised, and no later check can un-read them.

RETURNING AT ALL IS A FAILURE. On success this process is REPLACED, so
:func:`launch_credential_role` has no success value: a `LauncherRefusal` is the only thing
it can hand back, and `replace_process` coming back is itself the contract's "failure to
exec the validated role vector". That inversion is deliberate — it makes the no-token-return
guarantee STRUCTURAL rather than a rule every caller has to remember.

A REFUSAL NAMES THE STEP, NEVER THE VALUE. The reason carried beside the role's own closed
failure object is built from the role name and the step that refused, so the secret-free
requirement holds by construction rather than by review of each message.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_env import scrubbed_environment
from _lpm_launcher import (
    keyctl_pipe_argv,
    keyctl_rdescribe_argv,
    keyctl_search_argv,
    pre_exec_failure_object,
    role_child_environment,
    user_keyring_description_matches,
    validated_launch,
)
from _lpm_roles import PackagedCompanion, execution_vector_for

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ChildProcessOS",
    "ClosedRoleInput",
    "CommandOutcome",
    "HostProcessOS",
    "LauncherRefusal",
    "launch_credential_role",
]


@dataclass(frozen=True, kw_only=True)
class ClosedRoleInput:
    """Exactly what a parent may tell a launcher child about WHICH role to become.

    The contract closes this list: one closed role name, one nullable key description and
    that role's declared descriptors — plus, for `provider-observer` alone, the mode it was
    launched in, because that role's two modes have different closed failure objects. No
    executable, no argument and no credential value is in it, which is why a launcher that
    reads only this cannot be talked into running something else.

    `descriptors` NAMES the allowlist and `descriptor_fds` carries what the caller actually
    holds. The redundancy is the control: the names are checked against the registry, the
    fds are checked against the names, and a validated allowlist that reached no process
    would otherwise grant nothing at all — which is precisely the defect this pairing
    closes for `final-provisioning`, whose target-reference lock must survive the exec.
    """

    role_name: str
    key_description: str | None
    descriptors: tuple[str, ...]
    descriptor_fds: Mapping[str, int] = field(default_factory=dict)
    observer_mode: str | None = None


@dataclass(frozen=True, kw_only=True)
class CommandOutcome:
    """One completed `keyctl` call: its exit status and its raw standard-output bytes.

    The bytes are kept RAW rather than decoded at the boundary because one of these three
    outputs is a credential payload, and a decode here would make an immutable copy of it
    that nothing can overwrite afterwards.
    """

    exit_status: int
    stdout: bytes


class ChildProcessOS(Protocol):
    """The only OS primitives the in-child launcher may reach for.

    Three, deliberately: the uid the key's owner field must equal, one fixed-vector command
    run, and the process replacement. A launcher that could also open files, resolve a
    `PATH` or spawn a shell would have authority the contract does not give it.
    """

    def effective_uid(self) -> int:
        """The effective uid the `rdescribe` owner field must equal exactly."""
        ...

    def run(self, *, argv: tuple[str, ...]) -> CommandOutcome:
        """Run one manager-owned `keyctl` vector, capturing only its standard output."""
        ...

    def replace_process(self, *, argv: tuple[str, ...], environ: Mapping[str, str]) -> None:
        """Replace this process with `argv`. Returning at all means the exec FAILED."""
        ...


@dataclass(frozen=True, kw_only=True)
class HostProcessOS:
    """The production primitives: this process's uid, a real `keyctl` run, a real exec.

    It carries NO configuration, deliberately. The vectors it runs are built by
    `_lpm_launcher` from the fixed `/usr/bin/keyctl` path, so there is nothing here for a
    caller to point somewhere else — the injectability that makes the sequence testable
    stops at the Protocol and never becomes a production knob.
    """

    def effective_uid(self) -> int:
        """This process's effective uid, which the key's owner field must equal."""
        return os.geteuid()

    def run(self, *, argv: tuple[str, ...]) -> CommandOutcome:
        """Run `argv` with no shell, capturing standard output only.

        Standard error is deliberately NOT captured. One of these three calls prints a
        credential payload, and a captured diagnostic is one more buffer that could end up
        in a log; nothing the launcher decides on comes from `keyctl`'s stderr anyway.
        """
        completed = subprocess.run(  # noqa: S603 - fixed /usr/bin/keyctl vectors; never PATH
            list(argv), stdout=subprocess.PIPE, check=False
        )
        return CommandOutcome(exit_status=completed.returncode, stdout=completed.stdout)

    def replace_process(self, *, argv: tuple[str, ...], environ: Mapping[str, str]) -> None:
        """Replace this process with `argv`; an `OSError` IS the failure, so it returns.

        Suppressing it is not swallowing an error: a successful `execve` never comes back,
        so coming back at all is already the complete report. Letting the `OSError` escape
        would turn the contract's closed pre-exec failure object into a crash, and a
        crashing launcher gives its parent an abnormal exit instead of a role result.
        """
        with contextlib.suppress(OSError):
            os.execve(argv[0], list(argv), dict(environ))  # noqa: S606


@dataclass(frozen=True, kw_only=True)
class LauncherRefusal:
    """A pre-exec refusal: this role's own closed failure object and a secret-free reason.

    The object is the ONLY thing the contract permits to cross back, and it is the role's
    own closed shape rather than a generic error — for final provisioning that distinction
    is load-bearing, because its pre-exec `store-unavailable` must not be reinterpreted as
    the ambiguous target-write outcome that applies only after a successful exec. The
    reason is a local diagnostic naming the step, for a manager log that must stay
    secret-free.
    """

    failure_object: dict[str, object]
    reason: str


def launch_credential_role(
    *,
    role_input: ClosedRoleInput,
    companion: PackagedCompanion,
    environ: Mapping[str, str],
    process_os: ChildProcessOS,
) -> LauncherRefusal:
    """Run the whole in-child sequence, or report why it refused before any exec.

    There is no success return value: a sequence that reaches its end has REPLACED this
    process with the mapped role, so every value this function produces is a refusal.
    """
    observer_mode = role_input.observer_mode
    validated = validated_launch(
        role_name=role_input.role_name,
        key_description=role_input.key_description,
        descriptors=role_input.descriptors,
    )
    if isinstance(validated, Failure):
        return _refusal(
            role_name=role_input.role_name,
            observer_mode=observer_mode,
            reason=validated.failure().message,
        )
    role = validated.unwrap()
    # The contract orders the complete closed scrub BEFORE key lookup, so it happens here
    # rather than at the exec. `role_child_environment` reapplies the same name-only scrub
    # when it installs the one manager-named variable — idempotent, and deliberately not
    # bypassed, so the two spellings of the closed set cannot drift apart.
    inherited = scrubbed_environment(environ=environ)
    description = role.key_description
    token: str | None = None
    if description is not None:
        retrieved = _keyring_token(expected_description=description, process_os=process_os)
        if isinstance(retrieved, Failure):
            return _refusal(
                role_name=role.name,
                observer_mode=observer_mode,
                reason=f"{role.name} {retrieved.failure()}",
            )
        token = retrieved.unwrap()
    process_os.replace_process(
        argv=execution_vector_for(companion=companion, role=role),
        environ=role_child_environment(role=role, environ=inherited, token=token),
    )
    return _refusal(
        role_name=role.name,
        observer_mode=observer_mode,
        reason=f"{role.name} could not be replaced with its mapped role process",
    )


def _refusal(*, role_name: str, observer_mode: str | None, reason: str) -> LauncherRefusal:
    """This role's own closed failure object, paired with the name of the refusing step."""
    return LauncherRefusal(
        failure_object=pre_exec_failure_object(role_name=role_name, observer_mode=observer_mode),
        reason=reason,
    )


def _keyring_token(*, expected_description: str, process_os: ChildProcessOS) -> Result[str, str]:
    """Search, inspect, and only then pipe the named token out of the user keyring.

    EVERY STEP IS A GATE, including `rdescribe`, whose answer is what authorizes the pipe
    at all: the exact five-field check in `user_keyring_description_matches` runs on the
    description BEFORE the payload vector is ever built, so a key that exists but is not
    this role's owner-only key is refused unread. Each failure returns the STEP it reached,
    role-free, because the caller owns the role's own closed failure object and a reason
    that conflated "no such key" with "could not read the payload" would send a reconciler
    looking for a key that was never there.

    The payload lands in a `bytearray` that is zeroed before this returns, so the only
    surviving reference to the token is the one string handed to the child environment and
    consumed by the exec.
    """
    serial = _key_serial(expected_description=expected_description, process_os=process_os)
    if isinstance(serial, Failure):
        return serial
    described = process_os.run(argv=keyctl_rdescribe_argv(serial=serial.unwrap()))
    if described.exit_status != 0:
        return Failure("key description could not be read")
    if not user_keyring_description_matches(
        raw=_decoded_line(data=described.stdout),
        effective_uid=process_os.effective_uid(),
        expected_description=expected_description,
    ):
        return Failure("key is not this user's owner-only key for that description")
    piped = process_os.run(argv=keyctl_pipe_argv(serial=serial.unwrap()))
    if piped.exit_status != 0:
        return Failure("key payload could not be piped")
    payload = bytearray(piped.stdout)
    try:
        return Success(payload.decode("utf-8").strip())
    except UnicodeDecodeError:
        return Failure("key payload is not UTF-8")
    finally:
        payload[:] = bytes(len(payload))


def _key_serial(*, expected_description: str, process_os: ChildProcessOS) -> Result[str, str]:
    """The serial `keyctl search @u user <description>` found, or why there is none.

    A non-numeric answer is refused rather than passed on: `rdescribe` and `pipe` take a
    serial, and handing them something else would make the next step's failure the one
    that gets reported.
    """
    found = process_os.run(argv=keyctl_search_argv(description=expected_description))
    if found.exit_status != 0:
        return Failure("key is not in the user keyring")
    serial = _decoded_line(data=found.stdout)
    if not serial.isdigit():
        return Failure("key search returned no serial")
    return Success(serial)


def _decoded_line(*, data: bytes) -> str:
    """One `keyctl` output line as text, with an undecodable byte replaced.

    Replacement rather than refusal is right here, and only here: this text is compared
    against an exact expected serial or description, so a mangled byte can only make the
    comparison FAIL, which is already the fail-closed answer. It is never used for the
    payload, whose decode has to be exact.
    """
    return data.decode("utf-8", errors="replace").strip()
