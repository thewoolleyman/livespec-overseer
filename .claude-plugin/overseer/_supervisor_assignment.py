"""Track construction for attended supervisor assignment surfaces."""

from __future__ import annotations

import registry
import signals

__all__: list[str] = ["assignment_track"]

SUPERVISOR_SEAT_EPIC_ERROR = "supervisor seat requires epic"
FOREMAN_SEAT_EPIC_ERROR = "foreman seat requires epic"


def assignment_track(
    *,
    repo: str,
    topic: str,
    session: str,
    epic_source_topic: str | None = None,
    epic: str | None = None,
    ctx_threshold: int | None = None,
) -> registry.Track:
    """Build the mapping row written by attended assignment surfaces.

    No ``resume`` is written. That field is the OPERATOR's optional per-track
    override of the respawn prompt, and auto-populating it with a derived line
    made every row look like an override. The daemon derives the prompt from
    ``repo``, ``epic``, and the entity name instead.

    ``epic_source_topic`` overrides which topic's ``plan/<topic>/`` the epic is
    derived FROM, while ``topic``/``tmux`` stay the entity's own — the
    supervisor-epic-inheritance path. None derives from ``topic`` itself.
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
            ctx_threshold=ctx_threshold,
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
            ctx_threshold=ctx_threshold,
        )
    return registry.PlanTrack(
        topic=topic,
        repo=repo,
        tmux=session,
        epic=resolved_epic or registry.unresolved_plan_epic(topic=topic),
        ctx_threshold=ctx_threshold,
    )
