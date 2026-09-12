"""Runtime prerequisite closure: fail with `store-unavailable` before the first use.

SPECIFICATION/contracts.md requires that a command which first needs Linux procfs,
`/usr/bin/keyctl`, its user keyring or the configured SecretStore executable and finds it
unavailable return `store-unavailable` with exit `4` BEFORE that dependent action or
substantive mutation. For the initial `onepassword` backend it adds the safe
`/etc/machine-id` source required by the namespace binding to that same base set, with its
absence or wrong TYPE, OWNERSHIP, MODE or CONTENT carrying the identical outcome.

MACHINE-ID IS A PREREQUISITE RATHER THAN A DETAIL because it is the host half of the
namespace the three vaults are bound to. If it can be replaced, the binding it anchors can
be forged, and a manager on another host could read and mutate credentials that are not
its own. So the check is on the FILE — regular, root-owned, mode `0444` — and not merely on
the string it contains.

The `op` executable is resolved once per invocation and RETAINED: the first executable
named `op` on the manager's inherited `PATH`, resolved through its symlink chain, with the
canonical target required to be a regular executable file. Every later role call in that
invocation must be handed that same retained absolute path, and no role may search `PATH`
again — a second resolution could pick up a different binary placed after the first.

These checks are ORDERED AND CHEAP so that the refusal happens while it is still free:
once a role has been launched a token has left the keyring and an `op` child has been
spawned, and a prerequisite refusal at that point has already paid the cost it exists to
prevent.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_onepassword import MACHINE_ID_MODE, machine_id_digest
from _lpm_results import ManagerError, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "KEYCTL_PATH",
    "MACHINE_ID_PATH",
    "PROCFS_PATH",
    "RuntimePrerequisites",
    "machine_id_defect",
    "resolve_backend_executable",
    "runtime_prerequisites",
]

PROCFS_PATH: Final = "/proc/self/stat"
KEYCTL_PATH: Final = "/usr/bin/keyctl"
MACHINE_ID_PATH: Final = "/etc/machine-id"

_ROOT_UID: Final = 0


@dataclass(frozen=True, kw_only=True)
class RuntimePrerequisites:
    """The checked base prerequisites, including the one retained `op` path."""

    machine_id_sha256: str
    op_executable: str


def runtime_prerequisites(
    *, root: Path, search_path: Sequence[Path], executable_name: str
) -> Result[RuntimePrerequisites, ManagerError]:
    """Check every base prerequisite and retain the resolved backend executable.

    `root` is injected so the whole closure is exercisable against a fixture tree rather
    than against the host this test happens to run on.
    """
    for required in (PROCFS_PATH, KEYCTL_PATH):
        if not (root / required.lstrip("/")).exists():
            return Failure(store_unavailable(message=f"{required} is unavailable"))
    digest = machine_id_defect(path=root / MACHINE_ID_PATH.lstrip("/"))
    if isinstance(digest, Failure):
        return digest
    resolved = resolve_backend_executable(search_path=search_path, name=executable_name)
    if isinstance(resolved, Failure):
        return resolved
    return Success(
        RuntimePrerequisites(machine_id_sha256=digest.unwrap(), op_executable=resolved.unwrap())
    )


def machine_id_defect(*, path: Path) -> Result[str, ManagerError]:
    """The namespace machine-id digest, or `store-unavailable` naming the unsafe property."""
    if path.is_symlink():
        return Failure(store_unavailable(message=f"{MACHINE_ID_PATH} is a symlink"))
    try:
        status = path.stat()
    except OSError as failure:
        reason = failure.__class__.__name__
        return Failure(store_unavailable(message=f"{MACHINE_ID_PATH} is unusable: {reason}"))
    unsafe = _machine_id_source_defect(status=status)
    if unsafe is not None:
        return Failure(store_unavailable(message=f"{MACHINE_ID_PATH} {unsafe}"))
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as failure:
        reason = failure.__class__.__name__
        return Failure(store_unavailable(message=f"{MACHINE_ID_PATH} is unreadable: {reason}"))
    digest = machine_id_digest(machine_id=text)
    if digest is None:
        return Failure(store_unavailable(message=f"{MACHINE_ID_PATH} content is not a machine id"))
    return Success(digest)


def _machine_id_source_defect(*, status: os.stat_result) -> str | None:
    if not stat.S_ISREG(status.st_mode):
        return "is not a regular file"
    if status.st_uid != _ROOT_UID:
        return "is not root-owned"
    if stat.S_IMODE(status.st_mode) != MACHINE_ID_MODE:
        return "is not mode 0444"
    return None


def resolve_backend_executable(
    *, search_path: Sequence[Path], name: str
) -> Result[str, ManagerError]:
    """The FIRST `name` on the inherited path, resolved through its symlink chain.

    Resolved once and returned for retention; a later independent manager command resolves
    and retains its own path rather than reading one out of manager state.
    """
    for directory in search_path:
        candidate = directory / name
        if not candidate.exists():
            continue
        target = candidate.resolve()
        if not target.is_file() or not os.access(target, os.X_OK):
            return Failure(
                store_unavailable(message=f"{name} does not resolve to a regular executable")
            )
        return Success(str(target))
    return Failure(store_unavailable(message=f"{name} is not on the manager's PATH"))
