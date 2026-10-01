"""The REAL host: the facts and ports a manager process resolves from the machine it runs on.

SPECIFICATION/contracts.md requires every store-facing manager action to pass the base
prerequisite closure first: a command that "first needs Linux procfs, `/usr/bin/keyctl`, its user
keyring or the configured SecretStore executable and finds it unavailable [must] return
`store-unavailable` with exit `4` BEFORE that dependent action or substantive mutation", with
`/etc/machine-id` added to that set for the `onepassword` backend. `_lpm_prereq` implements that
closure; this module is what CALLS it, and the three store-facing ports below are built over it.

THE REFUSAL A STORE-LESS HOST SEES IS MEASURED, NOT ASSERTED. Each port runs the real closure
against the real filesystem root and the manager's own inherited `PATH`, so when `provision`
answers `store-unavailable` the message names which prerequisite was actually missing on that
machine. That is the difference between a boundary and a stub: nothing here decides in advance
that the store is unreachable.

THE PRIVILEGED ROLE CHILD IS THE ONE STEP THIS BUILD DOES NOT COMPOSE, and it is named rather
than papered over. Past the prerequisite closure, every token-bearing role in
`_lpm_roles.CREDENTIAL_ROLES` draws its `op` service-account token from the kernel user keyring
through `/usr/bin/keyctl` — and from nowhere else, by construction: `_lpm_env` scrubs every
`OP_*` name and all six manager service-account variables out of any child environment, and the
contract forbids the launcher to "search `PATH` or substitute a path" for the keyctl binary. So
there is no environment, configuration or test seam through which a token can be supplied, and
the metadata read, the credential-value read and the lifecycle status write are all behind that
one unwritten child. Each port therefore returns `store-unavailable` naming the role it would
have launched.

WHY THAT IS A REFUSAL AND NEVER A SUCCESS. A `report` whose classification suspects the
credential MUST move it off `valid`. Recording the report's marker while silently dropping that
transition would tell the consumer its report was accepted and leave the rejected credential
selectable by the next run — the exact failure the lifecycle exists to prevent. Fail-closed is
the only honest answer available until the role child lands.
"""

from __future__ import annotations

import datetime
import secrets
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_command_host import ManagerHost
from _lpm_config import ManagerConfig, load_manager_config
from _lpm_paths import account_database_home, config_file, manager_state_dir
from _lpm_prereq import RuntimePrerequisites, runtime_prerequisites
from _lpm_record import CredentialRecord
from _lpm_results import ManagerError, store_unavailable
from _lpm_roles import CREDENTIAL_ROLES
from _lpm_time import capture_manager_time

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "BACKEND_EXECUTABLES",
    "FILESYSTEM_ROOT",
    "REFERENCE_ENTROPY_BYTES",
    "BackendPorts",
    "credential_backend",
    "issued_reference",
    "manager_now",
    "real_host",
    "role_child_unavailable",
    "search_path",
    "stdin_text",
]

FILESYSTEM_ROOT: Final = Path("/")
REFERENCE_ENTROPY_BYTES: Final = 32

# Which executable each registered SecretStore backend resolves. `_lpm_config` validates
# `secret_store_backend` against `_lpm_registry.REGISTERED_SECRET_STORE_BACKENDS`, so this table
# is indexed rather than looked up defensively: a name that is not here could not have been
# configured, and a `.get` would add a branch no input can take.
BACKEND_EXECUTABLES: Final[dict[str, str]] = {"onepassword": "op"}

_METADATA_READER_ROLE: Final = "metadata-reader"
_VALUE_READER_ROLE: Final = "final-provisioning"
_LIFECYCLE_WRITER_ROLE: Final = "lifecycle-writer"


def role_child_unavailable(*, role: str) -> ManagerError:
    """The refusal naming the privileged role child a store action would have launched.

    It is `store-unavailable` because that is what the condition IS from the consumer's side: the
    credential store could not be used, so fail closed. The role name is from the closed
    `CREDENTIAL_ROLES` table, never from caller input, so quoting it cannot leak anything.
    """
    return store_unavailable(
        message=f"the {role} credential-role child is not composed in this build"
    )


def search_path(*, environ: Mapping[str, str]) -> tuple[Path, ...]:
    """The manager's inherited `PATH`, in order, as the backend resolver consumes it."""
    return tuple(Path(entry) for entry in environ.get("PATH", "").split(":") if entry != "")


def credential_backend(
    *, config: ManagerConfig, root: Path, path_entries: Sequence[Path]
) -> Result[RuntimePrerequisites, ManagerError]:
    """Run the ratified base prerequisite closure for the configured backend."""
    return runtime_prerequisites(
        root=root,
        search_path=path_entries,
        executable_name=BACKEND_EXECUTABLES[config.secret_store_backend],
    )


@dataclass(frozen=True, kw_only=True)
class BackendPorts:
    """The three store-facing ports, each resolving the backend fresh on every call.

    Resolving per call rather than once at construction is what the contract's retention rule
    asks for: the `op` path is "resolved once per invocation and RETAINED ... a later independent
    manager command resolves and retains its own path". One command is one invocation, and a
    command that never touches the store never resolves anything — which is why `target` and the
    attention list work on a host with no credential store at all.
    """

    config: ManagerConfig
    root: Path
    path_entries: tuple[Path, ...]

    def records(self) -> Result[tuple[CredentialRecord, ...], ManagerError]:
        """Every stored credential record, read through the metadata-reader role."""
        return Failure(self.refusal(role=_METADATA_READER_ROLE))

    def read_value(self, *, value_ref: str) -> Result[bytes, ManagerError]:
        """The credential bytes for `value_ref`, read inside the final-provisioning boundary."""
        _ = value_ref
        return Failure(self.refusal(role=_VALUE_READER_ROLE))

    def write_status(
        self, *, record: CredentialRecord, next_status: str, now: str
    ) -> Result[None, ManagerError]:
        """Move one credential record to `next_status` through the lifecycle-writer role."""
        _ = (record, next_status, now)
        return Failure(self.refusal(role=_LIFECYCLE_WRITER_ROLE))

    def refusal(self, *, role: str) -> ManagerError:
        """The prerequisite closure first; then the named role child this build does not compose.

        Both legs answer `store-unavailable`, and keeping them in this order is the point: on a
        host missing procfs, keyctl, a safe `/etc/machine-id` or the backend executable, the
        message names THAT, measured on the spot. The role-child refusal is only reached once
        every prerequisite the contract lists has actually been checked and passed.
        """
        resolved = credential_backend(
            config=self.config, root=self.root, path_entries=self.path_entries
        )
        if isinstance(resolved, Failure):
            return resolved.failure()
        return role_child_unavailable(role=CREDENTIAL_ROLES[role].name)


def issued_reference() -> str:
    """One opaque, unguessable target reference.

    `secrets.token_urlsafe` draws from the operating system's cryptographic source. The contract
    requires the reference to be "opaque, unguessable", and an issued reference is the only thing
    standing between a consumer run and another run's provisioning destination.
    """
    return secrets.token_urlsafe(REFERENCE_ENTROPY_BYTES)


def manager_now() -> str:
    """The manager's current time in the one canonical spelling every record uses."""
    return capture_manager_time(now=datetime.datetime.now(tz=datetime.timezone.utc))


def stdin_text() -> str:
    """The whole of standard input as UTF-8 text — what `-` means for every command."""
    return sys.stdin.read()


def real_host(
    *, environ: Mapping[str, str], uid: int, root: Path, now: str
) -> Result[ManagerHost, ManagerError]:
    """Resolve every host fact a manager command needs, or refuse before running one.

    `root`, `environ`, `uid` and `now` are parameters rather than reads so the whole resolution is
    exercisable against a fixture tree — the same reason `_lpm_prereq.runtime_prerequisites` takes
    a root. The launcher supplies the real four and nothing else.
    """
    home = account_database_home(uid=uid)
    if home is None:
        return Failure(store_unavailable(message="the effective user has no account-database home"))
    config = load_manager_config(path=config_file(home=home))
    if isinstance(config, Failure):
        return Failure(config.failure())
    resolved = config.unwrap()
    ports = BackendPorts(config=resolved, root=root, path_entries=search_path(environ=environ))
    return Success(
        ManagerHost(
            state_dir=manager_state_dir(home=home),
            config=resolved,
            owner_uid=uid,
            now=now,
            read_input=stdin_text,
            records=ports.records,
            read_value=ports.read_value,
            write_status=ports.write_status,
            new_reference=issued_reference,
            # `time.monotonic` / `time.sleep` are passed as the builtins rather than wrapped. The
            # lock modules call them POSITIONALLY (`sleep(LOCK_POLL_SECONDS)`), which is an
            # externally-fixed calling convention, so a keyword-only wrapper here would not be
            # callable by the code that consumes it.
            monotonic=time.monotonic,
            sleep=time.sleep,
        )
    )
