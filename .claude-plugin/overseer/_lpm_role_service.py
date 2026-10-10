"""Dispatch closed installed-role requests after the launcher exec succeeds."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from _lpm_role_target_service import target_role_result

__all__: list[str] = [
    "role_result",
]


def role_result(
    *,
    role_name: str,
    request: object,
    environ: Mapping[str, str],
    lock_descriptor: int | None,
) -> dict[str, object]:
    """Execute one target role whose request crossed the closed launcher boundary."""
    return target_role_result(
        role_name=role_name,
        members=cast("dict[str, object]", request),
        environ=environ,
        lock_descriptor=lock_descriptor,
    )
