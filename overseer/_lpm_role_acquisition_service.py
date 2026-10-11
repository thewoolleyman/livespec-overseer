"""Prerequisite reads performed inside the installed acquisition-reader role."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from _lpm_acquisition_prerequisite import acquisition_prerequisite_result
from _lpm_op_entrypoints import role_vault_access
from _lpm_role_context import RoleContext, role_context, role_entry

__all__: list[str] = [
    "acquisition_role_result",
]


def acquisition_role_result(
    *, role_name: str, members: dict[str, object], environ: Mapping[str, str]
) -> dict[str, object]:
    """Validate and execute one acquisition-prerequisite request."""
    if not _valid_request(role_name=role_name, members=members):
        return _failure()
    return (
        role_context()
        .map(
            lambda context: _acquisition_result(
                context=context,
                role_name=role_name,
                members=members,
                environ=environ,
            )
        )
        .value_or(_failure())
    )


def _valid_request(*, role_name: str, members: dict[str, object]) -> bool:
    version = members.get("version")
    provider = members.get("provider")
    account_id = members.get("account_id")
    kind = members.get("kind")
    executable = members.get("op_executable")
    return (
        role_name,
        members,
        type(version),
        type(provider),
        type(account_id),
        type(kind),
        type(executable),
        bool(provider),
        bool(account_id),
        bool(kind),
        bool(executable),
    ) == (
        "acquisition-prerequisite",
        {
            "version": 1,
            "provider": provider,
            "account_id": account_id,
            "kind": kind,
            "op_executable": executable,
        },
        int,
        str,
        str,
        str,
        str,
        True,
        True,
        True,
        True,
    )


def _acquisition_result(
    *,
    context: RoleContext,
    role_name: str,
    members: dict[str, object],
    environ: Mapping[str, str],
) -> dict[str, object]:
    entry = role_entry(
        role_name=role_name,
        members=members,
        environ=environ,
        context=context,
    )
    access = role_vault_access(entry=entry)
    if access is None:
        return _failure()
    return acquisition_prerequisite_result(
        access=access,
        namespace=entry.namespace,
        provider=cast("str", members["provider"]),
        account_id=cast("str", members["account_id"]),
        kind=cast("str", members["kind"]),
    )


def _failure() -> dict[str, object]:
    return {"version": 1, "status": "unavailable"}
