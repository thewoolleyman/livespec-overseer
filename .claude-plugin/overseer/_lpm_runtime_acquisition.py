"""Preflight the installed acquisition entrypoint before any state can exist."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from _lpm_config import ManagerConfig
from _lpm_results import ManagerError, invalid_request

from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = [
    "acquisition_preflight",
    "start_after_preflight",
]


def acquisition_preflight(
    *, request: dict[str, object], run_role: Callable[..., dict[str, object]]
) -> Result[None, ManagerError]:
    """Accept only the prerequisite role's positive closed verdict."""
    answer = run_role(role_name="acquisition-prerequisite", request=dict(request))
    status = answer.get("status")
    if status == "present":
        return Success(None)
    return Failure(invalid_request(message="acquisition prerequisites are unavailable"))


def start_after_preflight(
    *,
    request: dict[str, object],
    state_dir: Path,
    owner_uid: int,
    config: ManagerConfig,
    run_role: Callable[..., dict[str, object]],
    start: Callable[..., object] | None,
) -> Result[dict[str, object], ManagerError]:
    """Keep the no-mutation prerequisite verdict ahead of the worker owner."""
    preflight = acquisition_preflight(request=request, run_role=run_role)
    if isinstance(preflight, Failure):
        return Failure(preflight.failure())
    return cast(
        "Result[dict[str, object], ManagerError]",
        cast("Callable[..., object]", start)(
            request=dict(request),
            state_dir=state_dir,
            owner_uid=owner_uid,
            config=config,
        ),
    )
