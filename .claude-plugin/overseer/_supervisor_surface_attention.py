"""Daemon render-surface attention for a table that is not reaching tmux."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "SURFACE_HEADLESS_STATUS",
    "SurfaceAttention",
    "render_surface_attention",
]

SURFACE_HEADLESS_STATUS = "daemon-table-headless"
_SURFACE_ALERT_KEY = ("__daemon__", "__daemon__", SURFACE_HEADLESS_STATUS)


@dataclass(frozen=True, kw_only=True)
class SurfaceAttention:
    status: str
    note: str


def _stream_target(*, sup: Supervisor) -> str | None:
    name = getattr(sup.out, "name", None)
    if isinstance(name, str) and name and not name.startswith("<"):
        return name
    if sup.require_render_terminal:
        return "non-terminal stream"
    return None


def _table_reaches_tmux_pane(*, sup: Supervisor) -> bool:
    isatty = getattr(sup.out, "isatty", None)
    if not (callable(isatty) and bool(isatty())):
        return False
    # A terminal stream inside the herdr pane herdr exported is the operator's view too.
    # Measured 2026-10-12: a daemon drawing its table in a herdr top pane was reported
    # headless every tick, because only a tmux pane was recognized. This is a display
    # fact, never authority for a mutation, so herdr's own export is enough.
    environ = sup.environ()
    if environ.get("HERDR_SOCKET_PATH") and environ.get("HERDR_PANE_ID"):
        return True
    pane = sup.own_pane
    if not pane:
        return False
    return sup.tmux.pane_id(session=pane) == pane


def render_surface_attention(*, sup: Supervisor, act: bool) -> SurfaceAttention | None:
    if _table_reaches_tmux_pane(sup=sup):
        _ = sup.alerted.pop(_SURFACE_ALERT_KEY, None)
        return None
    target = _stream_target(sup=sup)
    if target is None:
        _ = sup.alerted.pop(_SURFACE_ALERT_KEY, None)
        return None
    note = f"rendering to {target}; restore the two-pane model with /overseer bootstrap"
    message = f"daemon table is not reaching a tmux pane; {note}"
    if act and sup.alerted.get(_SURFACE_ALERT_KEY) != message:
        sup.surface(message=message, event="daemon-alert")
        sup.alerted[_SURFACE_ALERT_KEY] = message
    return SurfaceAttention(status=SURFACE_HEADLESS_STATUS, note=note)
