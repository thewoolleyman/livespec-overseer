"""The one `op` child a SecretStore role spawns: fixed vectors, one token, no shell.

SPECIFICATION/contracts.md puts four controls on the single external command this backend
is permitted to run, and all four are properties of the SAME child process.

ONE TOKEN, INSTALLED BY NAME RATHER THAN COPIED. "Before spawning `op`, the role process
MUST construct a child environment by removing all six manager-named variables and every
inherited `OP_*` variable, then set exactly `OP_SERVICE_ACCOUNT_TOKEN` to the bytes from its
one manager-named role variable." The scrub runs FIRST and then one name is added back, so
an inherited `OP_SERVICE_ACCOUNT_TOKEN` cannot survive as a second, unaudited token source
that no keyring check would ever notice.

`HostOpChild` therefore holds the VARIABLE NAME, never the token. The contract also requires
the role to "destroy its copied token and child-environment value after that call", and a
long-lived field holding the bytes is exactly the copy that cannot be destroyed. Reading the
launcher-installed variable per call and clearing the child mapping afterwards keeps the only
durable copy the one the `execve` already placed in this process's own environment.

ONE EXECUTABLE. "every registry role's complete external-executable allowlist is the one
retained canonical `op` path: each role MUST require its `op_executable` to equal that
retained canonical regular executable, invoke only that absolute path, constrain the vault to
its table row and reject every other prefix." `retained_executable_defect` is the first half
of that sentence and `vault_scope_defect` the second; neither resolves anything, because a
role that could resolve a path could be pointed at another binary.

CREATE IS THE ONLY MUTATION VERB, so there are exactly three vectors: `item list`, `item get`
and the `item create` prefix `_lpm_onepassword` already states literally. A get is addressed
by ITEM ID rather than by title, because no backend in this operation may rely on 1Password
item-title uniqueness and two physical revision items may legitimately share one title — a
get by title would have to choose between them, which is the choice the append-only chain
exists to avoid making.

A NON-ZERO EXIT IS AN UNKNOWN OUTCOME, NEVER AN EMPTY ANSWER. A refusal, a failed spawn, a
missing role variable and a blown deadline all come back as a status rather than as an empty
result, because an empty result is how a backend outage comes to be read as authoritative
absence — and absence is what permits a genesis create.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_env import scrubbed_environment
from _lpm_onepassword import ACQUISITION_VAULT, METADATA_VAULT, VALUES_VAULT
from _lpm_roles import CredentialRole

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "OP_FORMAT_ARGUMENTS",
    "OP_SERVICE_ACCOUNT_VARIABLE",
    "VAULT_BY_SCOPE_PREFIX",
    "HostOpChild",
    "OpOutcome",
    "OpRunner",
    "op_child_environment",
    "op_item_get_argv",
    "op_item_list_argv",
    "retained_executable_defect",
    "vault_scope_defect",
]

# Named for the VARIABLE rather than for the token it names, on the same footing as
# `_caam_pass_span.ROTATION_EVENT`: ruff's S105 reads any constant whose own name contains
# "TOKEN" as a hardcoded credential, and the wire name below is the one that has to stay
# exact, not the binding. This constant holds a name the `op` child reads a value out of;
# it has never held a value.
OP_SERVICE_ACCOUNT_VARIABLE: Final = "OP_SERVICE_ACCOUNT_TOKEN"
OP_FORMAT_ARGUMENTS: Final = ("--format", "json")

# The registry states each role's `op` scope as prose beginning with the vault it names, so
# the vault constraint is derived from that closed table rather than restated here. A second
# spelling of "which role may touch which vault" is a second thing to keep in agreement.
VAULT_BY_SCOPE_PREFIX: Final = {
    "acquisition-vault": ACQUISITION_VAULT,
    "metadata-vault": METADATA_VAULT,
    "values-vault": VALUES_VAULT,
}

_UNAVAILABLE_EXIT_STATUS: Final = -1


@dataclass(frozen=True, kw_only=True)
class OpOutcome:
    """One completed `op` call: its exit status and its raw standard-output bytes.

    Raw rather than decoded, because one of these answers carries a credential value and a
    decode at this boundary makes an immutable copy of it that nothing can overwrite.
    """

    exit_status: int
    stdout: bytes


class OpRunner(Protocol):
    """The only way a SecretStore adapter may reach the backend: one `op` call at a time."""

    def __call__(self, *, argv: tuple[str, ...], stdin_bytes: bytes | None) -> OpOutcome:
        """Run one fixed vector, optionally streaming an item template to its input."""
        ...


def op_item_list_argv(*, op_executable: str, vault: str) -> tuple[str, ...]:
    """`op item list --vault <vault> --format json` — the one enumeration vector.

    Enumeration is what makes absence AUTHORITATIVE: the contract requires title lookups to
    "enumerate all matching items without relying on title uniqueness", so every chain and
    every namespace check starts from this list rather than from a get that happened to fail.
    """
    return (op_executable, "item", "list", "--vault", vault, *OP_FORMAT_ARGUMENTS)


def op_item_get_argv(*, op_executable: str, vault: str, item_id: str) -> tuple[str, ...]:
    """`op item get <item-id> --vault <vault> --format json`, addressed by id not title."""
    return (op_executable, "item", "get", item_id, "--vault", vault, *OP_FORMAT_ARGUMENTS)


def op_child_environment(*, environ: Mapping[str, str], token: str) -> dict[str, str]:
    """`environ` with every credential override removed and one token name installed.

    The order is the control. Scrubbing first and adding one name back means an inherited
    `OP_SERVICE_ACCOUNT_TOKEN` is replaced rather than preserved, so the child cannot be
    handed a token its role never fetched from the keyring.
    """
    return {**scrubbed_environment(environ=environ), OP_SERVICE_ACCOUNT_VARIABLE: token}


def retained_executable_defect(*, supplied: str, retained: str) -> str | None:
    """Why `supplied` is not the one retained canonical `op` path, or None when it is.

    An exact comparison, deliberately: the contract makes the fork-inherited retained path
    "the comparison authority for `op_executable`", so a role that normalized, resolved or
    searched for a near-miss would be deciding a question the manager already decided.

    THE DIAGNOSTIC QUOTES NEITHER PATH. The supplied value arrives from a role input that a
    defective caller controls, and this reason reaches a manager log that must stay
    secret-free; naming the mismatch is the whole of what a reader needs.
    """
    if supplied == retained:
        return None
    return "op_executable is not the retained canonical backend executable"


def vault_scope_defect(*, role: CredentialRole, vault: str) -> str | None:
    """Why this role's registry row does not scope it to `vault`, or None when it does.

    Derived from the row's own `op_scope` prose rather than from a second table, so a role
    whose scope changes cannot keep an authority this function still grants. A role with no
    `op` scope at all — the tokenless `target-status` — is scoped to nothing and refused for
    every vault, which is the fail-closed direction and the correct one: it answers "did
    that write commit?" and needs no backend access to do it.
    """
    scoped = {
        VAULT_BY_SCOPE_PREFIX[prefix]
        for prefix in VAULT_BY_SCOPE_PREFIX
        if any(entry.startswith(prefix) for entry in role.op_scope)
    }
    if vault in scoped:
        return None
    return f"{role.name} is not scoped to that vault"


@dataclass(frozen=True, kw_only=True)
class HostOpChild:
    """The production `op` child: this role's one token, an explicit environment, no shell.

    `variable` is the manager-named variable the credential-role launcher installed before
    the exec; the token is read from `environ` per call and the child mapping cleared
    afterwards, so this object never becomes a durable copy of the bytes.

    THE ENVIRONMENT IS PASSED EXPLICITLY, not inherited. An unset `env=` would hand the
    child whatever this process happens to hold, which defeats the scrub entirely — and in
    a test run it would also hand a Python child `COVERAGE_PROCESS_START` and let it race
    the suite's own coverage data.
    """

    environ: Mapping[str, str]
    variable: str
    timeout_seconds: float

    def __call__(self, *, argv: tuple[str, ...], stdin_bytes: bytes | None) -> OpOutcome:
        """Run one `op` vector under this role's token, or report that nothing ran."""
        token = self.environ.get(self.variable)
        if token is None:
            # The launcher installs exactly one manager-named variable before the exec, so
            # its absence is a manager defect rather than a backend answer. It is still
            # reported as an unknown outcome: raising here would reach the parent as an
            # abnormal role exit, which the contract maps to a DIFFERENT result.
            return OpOutcome(exit_status=_UNAVAILABLE_EXIT_STATUS, stdout=b"")
        child = op_child_environment(environ=self.environ, token=token)
        try:
            return self._spawned(argv=argv, stdin_bytes=stdin_bytes, child=child)
        finally:
            # The copied child-environment value, destroyed as soon as the call that needed
            # it has ended. The spawn has already copied it into the child by this point.
            child.clear()

    def _spawned(
        self, *, argv: tuple[str, ...], stdin_bytes: bytes | None, child: Mapping[str, str]
    ) -> OpOutcome:
        """Spawn `argv`, bounding the wait and discarding whatever it printed to stderr.

        STANDARD ERROR IS DISCARDED EXPLICITLY. An unset `stderr` inherits this process's
        fd 2, so `op`'s own diagnostic would land verbatim in the manager log — the one
        surface the contract requires to stay secret-free, and `op` is neither manager-owned
        nor answerable for what it prints when it fails.

        THE DEADLINE TERMINATES THE CHILD rather than abandoning the wait, because an `op`
        child holds a service-account token for as long as it runs.
        """
        try:
            completed = subprocess.run(  # noqa: S603 - the three fixed vectors; never a shell
                list(argv),
                input=stdin_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=dict(child),
                timeout=self.timeout_seconds,
                close_fds=True,
                check=False,
            )
        except subprocess.TimeoutExpired:
            # Whatever it had written is discarded with it: these answers are whole objects,
            # and half of one is not a shorter one.
            return OpOutcome(exit_status=_UNAVAILABLE_EXIT_STATUS, stdout=b"")
        except OSError:
            # A missing or non-executable backend path. NOT quoted: an operating-system
            # message carries the path it failed on.
            return OpOutcome(exit_status=_UNAVAILABLE_EXIT_STATUS, stdout=b"")
        return OpOutcome(exit_status=completed.returncode, stdout=completed.stdout)
