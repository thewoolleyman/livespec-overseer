"""Track construction for attended supervisor assignment surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import registry
import signals

__all__: list[str] = ["NO_OVERRIDES", "TrackOverrides", "assignment_track"]

SUPERVISOR_SEAT_EPIC_ERROR = "supervisor seat requires epic"
FOREMAN_SEAT_EPIC_ERROR = "foreman seat requires epic"
GROOMING_SEAT_EPIC_ERROR = "grooming seat requires epic"
PLAN_TRACK_DIRECTORY_ERROR = "plan track requires directory"


@dataclass(frozen=True, kw_only=True)
class TrackOverrides:
    """The operator's per-track overrides, carried together because they behave alike.

    Both are nullable TRI-STATES on every assigned variant, and ``None`` means the same
    thing for each: no override, so the daemon-wide default applies (``--warn-percent``
    for the threshold, ``--idle-nudge`` for the nudge). Both are omitted from the mapping
    row when unset and cleared by their CLI's ``inherit``, so a bare row can never be
    confused with one that pinned today's value of the default.

    They travel as one value rather than as two more keyword arguments because they are
    one concept — "what has the operator said about THIS track?" — and because the family
    is expected to keep growing as more daemon-wide defaults acquire per-track tiers.
    """

    ctx_threshold: int | None = None
    idle_nudge: bool | None = None


# The default for a caller that supplies neither override. A module constant rather than
# a `TrackOverrides()` call in the signature: `TrackOverrides` is frozen, so one shared
# instance is safe, and a call in a default argument is its own hazard.
NO_OVERRIDES = TrackOverrides()


def assignment_track(
    *,
    repo: str,
    topic: str,
    session: str,
    epic_source_topic: str | None = None,
    epic: str | None = None,
    overrides: TrackOverrides = NO_OVERRIDES,
) -> registry.Track:
    """Build the mapping row written by attended assignment surfaces.

    No ``resume`` is written. That field is the OPERATOR's optional per-track
    override of the respawn prompt, and auto-populating it with a derived line
    made every row look like an override. The daemon derives the prompt from
    ``repo``, ``epic``, and the entity name instead.

    ``epic_source_topic`` overrides which topic's ``plan/<topic>/`` the epic is
    derived FROM, while ``topic``/``tmux`` stay the entity's own — the
    supervisor-epic-inheritance path. None derives from ``topic`` itself.

    ``overrides`` carries the operator's per-track overrides (see
    :class:`TrackOverrides`); the default supplies none, which is what every caller that
    is not the ``add`` CLI wants.
    """
    resolved_epic = (
        epic
        if epic is not None
        else registry.epic_from_plan_anchor(repo=repo, topic=epic_source_topic or topic)
    )
    if signals.is_foreman_topic(topic=topic):
        if resolved_epic is None:
            raise ValueError(FOREMAN_SEAT_EPIC_ERROR)
        return registry.ForemanSeat(
            topic=topic,
            repo=repo,
            tmux=session,
            epic=resolved_epic,
            ctx_threshold=overrides.ctx_threshold,
            idle_nudge=overrides.idle_nudge,
        )
    if signals.is_grooming_topic(topic=topic):
        if resolved_epic is None:
            raise ValueError(GROOMING_SEAT_EPIC_ERROR)
        return registry.GroomingSeat(
            topic=topic,
            repo=repo,
            tmux=session,
            epic=resolved_epic,
            ctx_threshold=overrides.ctx_threshold,
            idle_nudge=overrides.idle_nudge,
        )
    supervised_topic = signals.topic_supervised_worker(topic=topic)
    if supervised_topic is not None:
        if resolved_epic is None:
            raise ValueError(SUPERVISOR_SEAT_EPIC_ERROR)
        return registry.SupervisorSeat(
            topic=topic,
            repo=repo,
            tmux=session,
            epic=resolved_epic,
            supervised_topic=supervised_topic,
            ctx_threshold=overrides.ctx_threshold,
            idle_nudge=overrides.idle_nudge,
        )
    plan_dir = Path(repo) / "plan" / topic
    if not plan_dir.is_dir():
        raise ValueError(PLAN_TRACK_DIRECTORY_ERROR, str(plan_dir))
    return registry.PlanTrack(
        topic=topic,
        repo=repo,
        tmux=session,
        epic=resolved_epic or registry.unresolved_plan_epic(topic=topic),
        ctx_threshold=overrides.ctx_threshold,
        idle_nudge=overrides.idle_nudge,
    )
