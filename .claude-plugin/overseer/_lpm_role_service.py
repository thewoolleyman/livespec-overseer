"""Dispatch closed installed-role requests after the launcher exec succeeds."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from _lpm_role_acquisition_service import acquisition_role_result
from _lpm_role_store_service import store_role_result
from _lpm_role_target_service import target_role_result

__all__: list[str] = [
    "role_result",
    "store_role_result",
]


def role_result(
    *,
    role_name: str,
    request: object,
    environ: Mapping[str, str],
    lock_descriptor: int | None,
) -> dict[str, object]:
    """Execute one closed role request after the launcher crossed its isolation boundary."""
    if not isinstance(request, dict):
        return {"version": 1, "status": "unavailable"}
    members = cast("dict[str, object]", request)
    if role_name == "acquisition-prerequisite":
        return acquisition_role_result(role_name=role_name, members=members, environ=environ)
    if role_name in ("metadata-reader", "report-writer"):
        return store_role_result(role_name=role_name, members=members, environ=environ)
    return target_role_result(
        role_name=role_name,
        members=members,
        environ=environ,
        lock_descriptor=lock_descriptor,
    )
