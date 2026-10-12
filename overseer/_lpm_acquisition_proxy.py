"""Private framed proxy between the execution role and browser-control service."""

from __future__ import annotations

from collections.abc import Callable

from _lpm_browser_control import ControlOutcome, frame_for

__all__: list[str] = ["proxy_call"]


def proxy_call(
    *,
    tool: str,
    arguments: dict[str, object],
    exchange: Callable[..., ControlOutcome],
) -> dict[str, object]:
    """Forward one canonical frame and expose only its closed, sanitized response."""
    outcome = exchange(frame=frame_for(tool=tool, arguments=arguments))
    if outcome.close_channel or outcome.response is None:
        return {"version": 1, "status": "unavailable"}
    return dict(outcome.response)
