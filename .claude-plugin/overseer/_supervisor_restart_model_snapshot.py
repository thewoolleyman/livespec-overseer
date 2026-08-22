"""Restart-model verdict payloads for the status snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

import jsonio
import registry
from _supervisor_statusline_model import rendered_statusline_model
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["restart_model_payload"]


def _track_for_row(*, sup: Supervisor, row: RowView) -> registry.Track | None:
    if not hasattr(sup, "store_path"):
        return None
    store_path = getattr(sup, "store_path", None)
    repo = registry.norm(repo=row.repo)
    for track in registry.read_valid_mapping(store_path=store_path):
        if registry.norm(repo=track.repo) == repo and track.topic == row.topic:
            return track
    return None


def _current_default_model() -> str | None:
    try:
        settings_path = Path.home() / ".claude" / "settings.json"
        parsed = jsonio.parse_object(text=settings_path.read_text(encoding="utf-8"))
    except OSError:
        return None
    if jsonio.is_parse_failure(result=parsed):
        return None
    payload = parsed.unwrap()
    if payload is None:
        return None
    model = payload.get("model")
    return model if isinstance(model, str) and model else None


def _current_default_statusline_model(
    *, sup: Supervisor, current_default: str | None
) -> str | None:
    if current_default is None:
        return None
    reader = getattr(sup, "current_default_statusline_model", None)
    if not callable(reader):
        return None
    rendered = reader(current_default=current_default)
    return rendered if isinstance(rendered, str) and rendered else None


def _capture_for_row(*, sup: Supervisor, row: RowView) -> str | None:
    if row.tmux is None:
        return None
    tmux = getattr(sup, "tmux", None)
    if tmux is None:
        return None
    return tmux.capture_pane(session=row.tmux)


def _restart_model_payload(
    *,
    current_default: str | None,
    current_default_statusline_model: str | None,
    model_profile: Mapping[str, str | None] | None,
    rendered: str | None,
    row: RowView,
) -> dict[str, object]:
    recorded = None if model_profile is None else model_profile.get("statusline_model")
    base: dict[str, object] = {
        "current_default": current_default,
        "current_default_statusline_model": current_default_statusline_model,
        "rendered_statusline_model": rendered,
        "recorded_statusline_model": recorded,
    }
    if model_profile is not None:
        return {"verdict": "profile-preserved", "reason": "recorded-profile", **base}
    if row.tmux is None:
        return {"verdict": "unknown", "reason": "pane-absent", **base}
    if rendered is None:
        return {"verdict": "unknown", "reason": "statusline-unreadable", **base}
    if current_default is None:
        verdict, reason = "unknown", "default-unreadable"
    elif current_default_statusline_model is None:
        verdict, reason = "unknown", "default-statusline-unresolved"
    elif rendered == current_default_statusline_model:
        verdict, reason = "no-op", "matches-current-default"
    else:
        verdict, reason = "would-change", "differs-from-current-default"
    return {"verdict": verdict, "reason": reason, **base}


def restart_model_payload(*, sup: Supervisor, row: RowView) -> dict[str, object]:
    track = _track_for_row(sup=sup, row=row)
    model_profile = None if track is None else track.model_profile
    capture = _capture_for_row(sup=sup, row=row)
    rendered = None if capture is None else rendered_statusline_model(capture=capture)
    current_default = _current_default_model()
    return _restart_model_payload(
        current_default=current_default,
        current_default_statusline_model=_current_default_statusline_model(
            sup=sup, current_default=current_default
        ),
        model_profile=model_profile,
        rendered=rendered,
        row=row,
    )
