"""Daemon-facing release-currency check surfacing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["currency_row"]

_TOPIC = "release-currency"
_STATUS = "currency-blocked"


def _blocked_reason(*, verdict: Mapping[str, object] | None) -> str | None:
    if verdict is None or verdict.get("blocked") is not True:
        return None
    reason = verdict.get("reason")
    return reason if isinstance(reason, str) and reason else "release currency check blocked"


def _surface_blocked(*, sup: Supervisor, reason: str) -> None:
    message = f"release currency check blocked: {reason}; keeping the running version"
    if sup.currency_blocked_message == message:
        return
    sup.currency_blocked_message = message
    sup.log(message=message)
    sup.surface(message=message)


def currency_row(*, sup: Supervisor) -> RowView | None:
    """Run the optional currency check and return its attention row, if blocked.

    The check is an environmental forge read, so an ``OSError`` is a value-level
    blocked verdict: the supervisor keeps supervising with its current runtime
    and surfaces the degraded condition instead of letting the daemon die.
    """
    if sup.currency_check is None:
        return None
    try:
        reason = _blocked_reason(verdict=sup.currency_check())
    except OSError as exc:
        reason = f"currency check failed: {exc}"
    if reason is None:
        sup.currency_blocked_message = None
        return None
    _surface_blocked(sup=sup, reason=reason)
    return RowView(
        topic=_TOPIC,
        repo="daemon",
        tmux=None,
        ctx=None,
        status=_STATUS,
        note=reason,
    )
