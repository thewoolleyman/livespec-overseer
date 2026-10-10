"""Resolve the account-bound namespace used inside an installed credential role."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from _lpm_onepassword import namespace_item_fields
from _lpm_op_entrypoints import RoleEntry
from _lpm_paths import account_database_home, manager_state_dir
from _lpm_prereq import machine_id_defect
from _lpm_results import ManagerError

from overseer._vendor.returns.result import Result

__all__: list[str] = [
    "RoleContext",
    "role_context",
    "role_entry",
]


@dataclass(frozen=True, kw_only=True)
class RoleContext:
    """Account-database state and namespace facts resolved by the role itself."""

    state_dir: Path
    owner_uid: int
    machine_id_sha256: str


def role_context() -> Result[RoleContext, ManagerError]:
    """Resolve the single local manager namespace or retain its typed refusal."""
    owner_uid = os.geteuid()
    home = cast("Path", account_database_home(uid=owner_uid))
    digest = machine_id_defect(path=Path("/etc/machine-id"))
    return digest.map(
        lambda machine_id_sha256: RoleContext(
            state_dir=manager_state_dir(home=home),
            owner_uid=owner_uid,
            machine_id_sha256=machine_id_sha256,
        )
    )


def role_entry(
    *,
    role_name: str,
    members: Mapping[str, object],
    environ: Mapping[str, str],
    context: RoleContext,
) -> RoleEntry:
    """Build the role's own OnePassword authority from its closed process state."""
    executable = cast("str", members["op_executable"])
    timeout = cast("int", members.get("external_call_timeout_seconds", 30))
    return RoleEntry(
        role_name=role_name,
        op_executable=executable,
        retained_executable=executable,
        environ=environ,
        namespace=namespace_item_fields(
            machine_id_sha256=context.machine_id_sha256,
            effective_uid=context.owner_uid,
            manager_state=str(context.state_dir),
        ),
        timeout_seconds=float(timeout),
    )
