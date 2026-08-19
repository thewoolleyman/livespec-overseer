"""Rendered statusline model parsing and mismatch checks."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING

import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "rendered_statusline_model",
    "restart_blocked_by_statusline_mismatch",
    "statusline_model_disagreement",
]

_STATUSLINE_CTX_RE = re.compile(r"(?:Ctx:|Context)\s*\d+%\s*left")
_MIN_STATUSLINE_PARTS = 3
_STATUSLINE_TAIL_ROWS = 4


def _tail_non_empty_lines(*, capture: str) -> list[str]:
    out: list[str] = []
    for raw in reversed(capture.splitlines()):
        line = signals.strip_ansi(text=raw).strip()
        if line:
            out.append(line)
            if len(out) >= _STATUSLINE_TAIL_ROWS:
                break
    out.reverse()
    return out


def _statusline_parts(*, line: str) -> list[str]:
    separator = "·" if "·" in line else "|"
    return [part.strip() for part in line.split(separator)]


def _has_statusline_shape(*, parts: list[str]) -> bool:
    if len(parts) < _MIN_STATUSLINE_PARTS:
        return False
    model, cwd, *rest = parts
    return (
        bool(model)
        and cwd.startswith(("/", "~"))
        and any(_STATUSLINE_CTX_RE.search(part) for part in rest)
    )


def rendered_statusline_model(*, capture: str) -> str | None:
    """Best-effort rendered model segment from the runtime statusline."""
    for line in reversed(_tail_non_empty_lines(capture=capture)):
        parts = _statusline_parts(line=line)
        if _has_statusline_shape(parts=parts):
            return parts[0]
    return None


def statusline_model_disagreement(
    *,
    capture: str,
    model_profile: Mapping[str, str | None] | None,
) -> tuple[str, str] | None:
    """Return ``(recorded, rendered)`` only for a resolved disagreement."""
    recorded = None if model_profile is None else model_profile.get("statusline_model")
    rendered = rendered_statusline_model(capture=capture)
    if not recorded or rendered is None or rendered == recorded:
        return None
    return recorded, rendered


def restart_blocked_by_statusline_mismatch(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    session: str,
) -> bool:
    """Surface and veto only a resolved recorded-vs-rendered model disagreement."""
    disagreement = statusline_model_disagreement(
        capture=sup.tmux.capture_pane(session=target),
        model_profile=track.model_profile,
    )
    if disagreement is None:
        return False
    recorded, rendered = disagreement
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=target,
        message=(
            "statusline model mismatch: "
            f"{track.repo}::{track.topic} has "
            f"recorded model {recorded!r}, rendered model {rendered!r}; "
            "skipping restart and keeping the ready declaration"
        ),
        condition="statusline-model-mismatch",
    )
    return True
