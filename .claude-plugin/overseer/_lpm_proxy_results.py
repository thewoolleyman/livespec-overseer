"""The closed secret-free result shapes the private acquisition proxy may return.

Browser and terminal observations arrive already sanitized from the observation
sanitizer, the only producer of their variable fields; every other local-tool
result is one fixed shape whose sole variable member is an opaque capture handle.
Admitting exactly this closed set is therefore what makes a proxy response carry
only sanitized output and opaque handles — a local-tool result outside it is
malformed and must produce no proxy result at all rather than be forwarded.

The fixed handle-free sensitive marker is never a handle, so a capture result
offering it is refused here as well as at every tool that accepts a handle.
"""

from __future__ import annotations

from typing import Final

__all__: list[str] = [
    "closed_result",
]

_SENSITIVE_MARKER: Final = "[[redacted-sensitive]]"
_SCALAR_STATUSES: Final = frozenset({"applied", "not-found", "ok", "refused", "unavailable"})
_BROWSER_OBSERVATION_TEXT: Final = (
    "accessibility_tree",
    "dom_text",
    "screenshot_png",
    "state_fingerprint",
    "title",
    "url",
)
_SCALAR_MEMBERS: Final = frozenset({"version", "status"})
_CAPTURE_MEMBERS: Final = frozenset({"version", "status", "capture_handle"})
_BROWSER_MEMBERS: Final = frozenset({"version", "status", *_BROWSER_OBSERVATION_TEXT})
_TERMINAL_MEMBERS: Final = frozenset(
    {"version", "status", "running", "exit_status", "stdout", "stderr"}
)


def closed_result(*, response: dict[str, object]) -> dict[str, object] | None:
    """Return the response only when it is one closed secret-free result shape."""
    version = response.get("version")
    status = response.get("status")
    if type(version) is not int or version != 1 or not isinstance(status, str):
        return None
    members = frozenset(response)
    admitted = (
        _scalar_admitted(members=members, status=status)
        or _capture_admitted(response=response, members=members, status=status)
        or _browser_admitted(response=response, members=members, status=status)
        or _terminal_admitted(response=response, members=members, status=status)
    )
    return response if admitted else None


def _scalar_admitted(*, members: frozenset[str], status: str) -> bool:
    return members == _SCALAR_MEMBERS and status in _SCALAR_STATUSES


def _capture_admitted(*, response: dict[str, object], members: frozenset[str], status: str) -> bool:
    handle = response.get("capture_handle")
    return (
        members == _CAPTURE_MEMBERS
        and status == "captured"
        and isinstance(handle, str)
        and bool(handle)
        and handle != _SENSITIVE_MARKER
    )


def _browser_admitted(*, response: dict[str, object], members: frozenset[str], status: str) -> bool:
    return (
        members == _BROWSER_MEMBERS
        and status == "ok"
        and all(isinstance(response[name], str) for name in _BROWSER_OBSERVATION_TEXT)
    )


def _terminal_admitted(
    *, response: dict[str, object], members: frozenset[str], status: str
) -> bool:
    exit_status = response.get("exit_status")
    return (
        members == _TERMINAL_MEMBERS
        and status == "ok"
        and type(response.get("running")) is bool
        and (exit_status is None or type(exit_status) is int)
        and isinstance(response.get("stdout"), str)
        and isinstance(response.get("stderr"), str)
    )
