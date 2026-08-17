"""Supervisor-half durable marker freshness for daemon attention rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, cast

import _supervisor_config
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "SUPERVISOR_STATE_STALE_STATUS",
    "SupervisorStateFreshness",
    "observe_supervisor_state_freshness",
    "supervisor_state_path",
    "supervisor_state_stale_note",
    "surface_supervisor_state_stale_alert",
]

SUPERVISOR_STATE_STALE_STATUS = "supervisor-state-stale"


@dataclass(frozen=True, kw_only=True)
class SupervisorStateFreshness:
    stale: bool
    age: float | None
    reason: str | None


def supervisor_state_path(*, repo: str, topic: str) -> Path:
    return signals.marker_dir(repo=repo, topic=topic) / ".supervisor-state"


def _parse_updated_at(*, value: str) -> datetime:
    cleaned = value.strip().strip("'\"")
    parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _updated_at_from_yaml_subset(*, text: str) -> datetime | None:
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("updated_at:"):
            continue
        value = line.split(":", 1)[1].split("#", 1)[0].strip()
        if value == "":
            return None
        return _parse_updated_at(value=value)
    return None


def _read_updated_at(*, repo: str, topic: str) -> datetime | None:
    try:
        text = supervisor_state_path(repo=repo, topic=topic).read_text(encoding="utf-8")
        return _updated_at_from_yaml_subset(text=text)
    except (OSError, ValueError):
        return None


def _tracked_as_supervisor_half(*, topic: str) -> bool:
    return signals.topic_supervised_worker(topic=topic) is not None


def observe_supervisor_state_freshness(
    *, sup: Supervisor, track: registry.Track
) -> SupervisorStateFreshness:
    if not _tracked_as_supervisor_half(topic=track.topic):
        return SupervisorStateFreshness(stale=False, age=None, reason=None)
    topic = cast(str, signals.topic_supervised_worker(topic=track.topic))
    updated_at = _read_updated_at(repo=track.repo, topic=topic)
    if updated_at is None:
        return SupervisorStateFreshness(stale=True, age=None, reason="missing or malformed marker")
    age = max(0.0, sup.now() - updated_at.timestamp())
    if age <= _supervisor_config.SUPERVISOR_STATE_STALE_AFTER:
        return SupervisorStateFreshness(stale=False, age=age, reason=None)
    return SupervisorStateFreshness(stale=True, age=age, reason="updated_at too old")


def supervisor_state_stale_note(*, freshness: SupervisorStateFreshness) -> str:
    if freshness.age is None:
        return f"supervisor state stale: {freshness.reason or 'unknown freshness'}"
    return f"supervisor state stale {int(freshness.age)}s: {freshness.reason or 'stale'}"


def surface_supervisor_state_stale_alert(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    pane: str,
    freshness: SupervisorStateFreshness,
) -> set[str]:
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=pane,
        message=(
            f"{supervisor_state_stale_note(freshness=freshness)} — "
            "inspect and refresh tmp/overseer/<topic>/.supervisor-state in that supervisor pane"
        ),
        condition=SUPERVISOR_STATE_STALE_STATUS,
    )
    return {SUPERVISOR_STATE_STALE_STATUS}
