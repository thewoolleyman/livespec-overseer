"""Preflight the installed acquisition entrypoint before any state can exist."""

from __future__ import annotations

from collections.abc import Callable

from _lpm_results import ManagerError, invalid_request

from overseer._vendor.returns.result import Failure, Result

__all__: list[str] = [
    "acquisition_refusal",
]


def acquisition_refusal(
    *, request: dict[str, object], run_role: Callable[..., dict[str, object]]
) -> Result[dict[str, object], ManagerError]:
    """Return the closed prerequisite refusal without creating local state."""
    answer = run_role(role_name="acquisition-prerequisite", request=dict(request))
    status = answer.get("status")
    reason = {
        "absent": "acquisition prerequisites are absent",
        "malformed": "acquisition prerequisites are ambiguous or malformed",
    }.get(str(status), "acquisition prerequisites are unavailable")
    return Failure(invalid_request(message=reason))
