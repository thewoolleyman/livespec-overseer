"""The PARENT side of a credential-role run: launch the closed vector, read one object.

SPECIFICATION/contracts.md makes the launcher a short-lived child created BEFORE any token
retrieval, fixes every result crossing that boundary as exactly one UTF-8 JSON object with
no extra fields, and requires the parent to map a reader `unavailable`, a deadline, an
abnormal exit or ANY nonconforming output onto a closed failure — NEVER onto absence.
`_lpm_role_child` is what runs inside the child; this module is everything the parent is
allowed to do and conclude from the outside.

NEVER ONTO ABSENCE IS THE WHOLE POINT OF THE OUTPUT CHECK. `item: null` asserts
AUTHORITATIVE absence, and absence is what licenses a genesis create — so a child that
wrote garbage, died, or answered a shape this parent does not recognize must not be allowed
to resolve to "there is no such record". Every non-answer therefore becomes that role's own
closed failure object, and the parse is strict rather than forgiving.

THE ROLE INPUT TRAVELS OVER THE PIPE, NEVER ON THE ARGUMENT VECTOR. A process argument list
is readable through procfs by anything that can see the process, and these inputs name
records, runs and value generations a reader could correlate. The vector stays exactly the
six closed elements the registry builds, so there is no argument position for a caller to
put anything else in — and the launcher accepts no caller-supplied executable or argument.

THE PARENT NEVER SEES A TOKEN, by construction rather than by filtering. It passes a role
NAME and a nullable key DESCRIPTION; the child does the keyring read and replaces itself.
Nothing in this module can produce a credential value, which is why the no-token-return
guarantee survives a bug here.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import canonical_json_bytes, parse_canonical_json
from _lpm_env import scrubbed_environment
from _lpm_launcher import pre_exec_failure_object, validated_launch
from _lpm_role_child import ClosedRoleInput
from _lpm_role_results import closed_result_defect
from _lpm_roles import PackagedCompanion, execution_vector_for

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ROLE_RESULT_VERSION",
    "RoleCompletion",
    "RoleLaunch",
    "RoleOutcome",
    "run_credential_role",
    "subprocess_role_launch",
]

ROLE_RESULT_VERSION: Final = 1

# No exit status was ever reported for a child the parent's own deadline terminated, and
# the parent must not invent a plausible one: an invented status is exactly how a deadline
# comes to be read as an abnormal exit, which the contract treats differently.
_TERMINATED_EXIT_STATUS: Final = -1


@dataclass(frozen=True, kw_only=True)
class RoleCompletion:
    """What a launched role child left behind: its output, its status, and whether it was cut off.

    `timed_out` carries no default, deliberately. False means "this child answered", which
    is the UNSAFE direction for a flag whose True means "nobody knows what it did" — so a
    caller that forgot to say must not be given the reassuring answer. When it is true
    `exit_status` is `_TERMINATED_EXIT_STATUS` and meaningless.
    """

    stdout: bytes
    exit_status: int
    timed_out: bool


class RoleLaunch(Protocol):
    """How the parent starts one launcher child — the seam the whole run is tested through."""

    def __call__(
        self,
        *,
        argv: tuple[str, ...],
        environ: Mapping[str, str],
        request_bytes: bytes,
        timeout_seconds: float,
        inherited_fds: tuple[int, ...],
    ) -> RoleCompletion: ...


@dataclass(frozen=True, kw_only=True)
class RoleOutcome:
    """The single closed object the parent may read from one credential-role run.

    `refusal_reason` is None exactly when `result_object` is the role's OWN conforming
    answer. Otherwise this parent SUBSTITUTED that role's closed failure object, and the
    reason names why, secret-free — a distinction the object alone cannot carry, because a
    role's genuine `unavailable` and a substituted one are the same two members.

    `launched` is False exactly when the parent refused BEFORE spawning anything, so no
    role, browser, store or target action can have happened. It is the field final
    provisioning has to read: the contract forbids reinterpreting a PRE-EXEC
    `store-unavailable` as a target-write ambiguity, and once a child has existed the
    object alone cannot say which side of the exec produced it.
    """

    result_object: dict[str, object]
    refusal_reason: str | None
    launched: bool


def subprocess_role_launch(
    *,
    argv: tuple[str, ...],
    environ: Mapping[str, str],
    request_bytes: bytes,
    timeout_seconds: float,
    inherited_fds: tuple[int, ...],
) -> RoleCompletion:
    """Run the closed role vector, streaming the role input over its standard input.

    DESCRIPTOR INHERITANCE IS EXPLICIT IN BOTH DIRECTIONS, as the contract requires. Naming
    `pass_fds` sets `close_fds` and clears close-on-exec for exactly those descriptors, so
    the allowlisted ones survive the spawn AND the launcher's own `execve` into the role,
    while every other descriptor this parent holds is closed. Relying on the default would
    have closed the allowlisted ones too — which is how a validated allowlist comes to
    grant nothing.

    The deadline TERMINATES the child rather than merely abandoning the wait. A role holds
    a service-account token and may hold a lock or a target-reference lock; one left running
    behind an abandoned parent would keep that authority with nobody reading its answer.

    STANDARD ERROR IS DISCARDED EXPLICITLY, and the distinction from leaving it alone is
    the whole point: an unset `stderr` INHERITS the parent's fd 2, so a child's diagnostic
    lands verbatim in the manager's own log — the one surface the contract requires to stay
    secret-free. A launcher child runs `keyctl` and later `op`, neither of them
    manager-owned nor answerable for what they print when they fail, so the parent cannot
    vouch for those bytes. They are discarded rather than captured because a captured
    diagnostic is a buffer the parent then holds and must remember never to log; nothing
    the parent is permitted to read comes from there in the first place.
    """
    try:
        completed = subprocess.run(  # noqa: S603 - the registry's closed role vector; never PATH
            list(argv),
            input=request_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=dict(environ),
            timeout=timeout_seconds,
            close_fds=True,
            pass_fds=inherited_fds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # Whatever the child had written so far is discarded with it. A partial result is
        # not a shorter result: these shapes are closed, and half of one is not one.
        return RoleCompletion(stdout=b"", exit_status=_TERMINATED_EXIT_STATUS, timed_out=True)
    return RoleCompletion(
        stdout=completed.stdout, exit_status=completed.returncode, timed_out=False
    )


def run_credential_role(
    *,
    role_input: ClosedRoleInput,
    companion: PackagedCompanion,
    role_request: Mapping[str, object],
    environ: Mapping[str, str],
    timeout_seconds: float,
    launch: RoleLaunch,
) -> RoleOutcome:
    """Validate, launch the closed vector, and reduce the whole run to one closed object."""
    validated = validated_launch(
        role_name=role_input.role_name,
        key_description=role_input.key_description,
        descriptors=role_input.descriptors,
    )
    if isinstance(validated, Failure):
        return _substituted(
            role_input=role_input, launched=False, reason=validated.failure().message
        )
    role = validated.unwrap()
    request = canonical_json_bytes(value=dict(role_request))
    if isinstance(request, Failure):
        return _substituted(
            role_input=role_input,
            launched=False,
            reason=f"{role.name} input is not canonical JSON: {request.failure().reason}",
        )
    inherited = _inherited_descriptors(role_input=role_input, allowed=role.descriptors)
    if isinstance(inherited, Failure):
        return _substituted(
            role_input=role_input, launched=False, reason=f"{role.name} {inherited.failure()}"
        )
    completion = launch(
        argv=execution_vector_for(companion=companion, role=role),
        # The contract puts the complete closed scrub on whichever process ACTUALLY SPAWNS
        # the child, which is this one. The launcher reapplies it before its key lookup,
        # but that reapplication runs inside an already-started launcher: without the scrub
        # HERE, the launcher begins life holding whatever credential override its parent
        # inherited — including the manager service-account variable for the very role
        # whose key it is about to fetch, which would give it a second, unaudited token
        # source that no keyring check could detect.
        environ=scrubbed_environment(environ=environ),
        request_bytes=request.unwrap(),
        timeout_seconds=timeout_seconds,
        inherited_fds=inherited.unwrap(),
    )
    interpreted = _completion_meaning(
        role_name=role.name,
        role_request=role_request,
        completion=completion,
        timeout_seconds=timeout_seconds,
    )
    if isinstance(interpreted, Failure):
        return _substituted(
            role_input=role_input,
            launched=True,
            reason=f"{role.name} {interpreted.failure()}",
        )
    return RoleOutcome(result_object=interpreted.unwrap(), refusal_reason=None, launched=True)


def _completion_meaning(
    *,
    role_name: str,
    role_request: Mapping[str, object],
    completion: RoleCompletion,
    timeout_seconds: float,
) -> Result[dict[str, object], str]:
    """What the child's completion MEANS: its own closed object, or why it is not one.

    Separated from the launch because the two are different jobs with different authority:
    above this point the parent is preparing and spawning, and from here on it is reading a
    result it did not produce. The ORDER of these four questions is the whole substance,
    and each one exists to stop the next from being asked too early.
    """
    if completion.timed_out:
        # First, because a terminated child has no exit status to report: folding this into
        # a later branch would name an invented one in the reason a reconciler reads.
        return Failure(f"exceeded its {timeout_seconds:g}-second parent deadline")
    if completion.exit_status != 0:
        # Before the output is interpreted at all, because a conforming-looking answer from
        # a child that then died is the worst input this boundary takes: `status: ok` with
        # `item: null` asserts AUTHORITATIVE ABSENCE, and absence is what licenses a genesis
        # create. A launcher emitting its own closed failure object has DONE its job and
        # exits 0 to say so, so this does not swallow a pre-exec refusal — it is what keeps
        # `unavailable`-because-we-refused apart from `unavailable`-because-we-crashed.
        return Failure(f"exited {completion.exit_status} abnormally")
    answer = _closed_role_object(stdout=completion.stdout)
    if isinstance(answer, Failure):
        return Failure(f"exited {completion.exit_status} with {answer.failure()}")
    result = answer.unwrap()
    defect = closed_result_defect(
        role_name=role_name, mode=_requested_mode(role_request=role_request), members=result
    )
    if defect is not None:
        return Failure(f"returned {defect}")
    return Success(result)


def _inherited_descriptors(
    *, role_input: ClosedRoleInput, allowed: tuple[str, ...]
) -> Result[tuple[int, ...], str]:
    """The descriptors to inherit, in the registry's own order, or why they disagree.

    Both directions refuse, and neither is cosmetic. A descriptor the registry does not
    grant would hand the role authority it was never promised. A missing one would let final
    provisioning start a write it cannot hold the target-reference lock for — the ambiguous
    outcome that whole lock exists to prevent. Ordering follows the REGISTRY rather than the
    caller's mapping so two callers offering the same names cannot produce different vectors.
    """
    offered = set(role_input.descriptor_fds)
    if offered != set(allowed):
        return Failure(
            f"was offered descriptors {sorted(offered)} but may inherit exactly "
            f"{sorted(allowed)}"
        )
    return Success(tuple(role_input.descriptor_fds[name] for name in allowed))


def _requested_mode(*, role_request: Mapping[str, object]) -> str | None:
    """The `mode` this call itself asked for, when the role's input carries one.

    Read back out of the request rather than tracked beside it: the request is the closed
    input this same invocation just serialized, so there is no second copy to drift from
    it. A role whose input has no mode simply has none, and its shapes are keyed that way.
    """
    mode = role_request.get("mode")
    return mode if isinstance(mode, str) else None


def _substituted(*, role_input: ClosedRoleInput, launched: bool, reason: str) -> RoleOutcome:
    """This role's own closed failure object, standing in for an answer it did not give.

    It is the SAME object the launcher child would have emitted pre-exec, deliberately: the
    contract gives each role exactly one secret-free failure shape, and a parent that
    invented a second one would hand its caller a word the closed result vocabulary does
    not contain.
    """
    return RoleOutcome(
        result_object=pre_exec_failure_object(
            role_name=role_input.role_name, observer_mode=role_input.observer_mode
        ),
        refusal_reason=reason,
        launched=launched,
    )


def _closed_role_object(*, stdout: bytes) -> Result[dict[str, object], str]:
    """The one version-1 JSON object a role may write, or why its output is not one.

    `parse_canonical_json` is used rather than a bare `json.loads` because it REJECTS a
    duplicate member name instead of silently keeping the last one — a child emitting two
    `status` members would otherwise hand the parent a status no reader ever saw written.
    """
    try:
        text = stdout.decode("utf-8")
    except UnicodeDecodeError:
        return Failure("output that is not UTF-8")
    parsed = parse_canonical_json(text=text.strip())
    if isinstance(parsed, Failure):
        return Failure(f"output that is not one JSON object: {parsed.failure().reason}")
    value = parsed.unwrap()
    if not isinstance(value, dict):
        return Failure("output that is not a JSON object")
    members: dict[str, object] = value
    if members.get("version") != ROLE_RESULT_VERSION:
        return Failure("output whose version is not 1")
    if not isinstance(members.get("status"), str):
        return Failure("output that carries no status")
    return Success(members)
