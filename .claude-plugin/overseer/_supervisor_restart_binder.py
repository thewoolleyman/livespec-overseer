"""Certification guards for entity-track restarts."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import _supervisor_launch
import _supervisor_state
import registry
import signals
from _supervisor_prompts import supervisor_epic_path, supervisor_handoff_path

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "handle_uncertified_restart_binder",
    "missing_foreman_epic_message",
    "missing_plan_epic_message",
    "missing_restart_epic_message",
]


def missing_plan_epic_message() -> str:
    """Surface text for a ready track whose mapping row lacks the plan epic locator."""
    return "ready cannot respawn: no plan epic recorded"


def missing_foreman_epic_message() -> str:
    """Surface text for a ready foreman whose mapping row lacks its ledger epic."""
    return "ready cannot respawn: no foreman epic recorded"


def missing_restart_epic_message(*, track: registry.Track) -> str:
    """Surface text for a ready track whose restart binder cannot resolve an epic."""
    if signals.is_foreman_topic(topic=track.topic):
        return missing_foreman_epic_message()
    return missing_plan_epic_message()


def _supervisor_topic_archived_message() -> str:
    """Surface text for a supervisor ready declaration whose plan thread is archived/gone."""
    return (
        "supervisor ready declared but its plan thread is archived or gone; "
        "retiring the track, not restarting"
    )


def _migrated_supervisor_epic_certifies(*, track: registry.Track) -> bool:
    """Return whether the retired-file shape is replaced by a ledger-bound binder."""
    topic = cast(str, signals.topic_supervised_worker(topic=track.topic))
    path = supervisor_epic_path(repo=track.repo, topic=topic)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return False
    lowered = text.lower()
    epic = track.epic
    names_epic = registry.epic_is_resolved(epic=epic) and epic is not None and epic in text
    names_ledger = "ledger" in lowered
    return names_epic and names_ledger


def _supervisor_resume_artifact_certifies(*, track: registry.Track) -> bool:
    """Accept either the legacy file artifact or the migrated ledger-backed shape."""
    topic = cast(str, signals.topic_supervised_worker(topic=track.topic))
    if supervisor_handoff_path(repo=track.repo, topic=topic).exists():
        return True
    return _migrated_supervisor_epic_certifies(track=track)


def _handle_uncertified_supervisor_binder(
    *, sup: Supervisor, track: registry.Track, target: str
) -> bool:
    """Alert (and report True) when a supervisor track's binder cannot certify a restart.

    Returns False, with NO side effect, when the track is not a supervisor entity or its
    binder certifies — the ordinary case, where ``do_restart`` proceeds to the actual
    respawn.

    **Branches on WHY the binder is absent (overseer-y26).** ``registry.archived_or_gone``
    is a DIRECTORY-level test, spec-permitted for the daemon to consult (it never opens a
    file under ``plan/``): when the plan thread was archived or deleted, the missing binder
    is EXPECTED, not anomalous, so the round is closed with a terminal, non-"missing-file"
    alert and no restart is attempted — that wording is exactly what taught a prior
    supervisor (livespec-dev-tooling, 2026-08-04) to restore a banned tombstone 13 hours
    after the ban, believing the daemon was pointing at a genuinely lost file. Only a
    genuinely LIVE plan directory with no binder keeps today's ``supervisor-handoff-missing``
    alert — that case IS anomalous, and the round is left open (unchanged) so it keeps
    reporting until a human intervenes.
    """
    topic = signals.topic_supervised_worker(topic=track.topic)
    if topic is None or _supervisor_resume_artifact_certifies(track=track):
        return False
    if registry.archived_or_gone(repo=track.repo, topic=topic):
        # Close the round instead of leaving a `ready` marker that re-reaches this branch
        # every tick — archive_gc ordinarily drops the mapping row in the SAME tick before
        # `do_restart` is ever reached; this only covers that narrow same-tick race.
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=_supervisor_launch.session_of(sup=sup, track=track),
            pane=target,
            message=_supervisor_topic_archived_message(),
            condition="supervisor-topic-archived",
        )
        _supervisor_state.clear_state(sup=sup, track=track)
        return True
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=_supervisor_launch.session_of(sup=sup, track=track),
        pane=target,
        message="supervisor ready declared but supervisor-handoff.md is missing; not restarting",
        condition="supervisor-handoff-missing",
    )
    return True


def _handle_uncertified_foreman_binder(
    *, sup: Supervisor, track: registry.Track, target: str
) -> bool:
    """Alert (and report True) when a foreman track has no restartable epic."""
    if not signals.is_foreman_topic(topic=track.topic) or registry.epic_is_resolved(
        epic=track.epic
    ):
        return False
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=_supervisor_launch.session_of(sup=sup, track=track),
        pane=target,
        message=missing_foreman_epic_message(),
        condition="restart-foreman-epic-missing",
    )
    return True


def handle_uncertified_restart_binder(
    *, sup: Supervisor, track: registry.Track, target: str
) -> bool:
    """Alert (and report True) when an entity track cannot certify a restart."""
    return _handle_uncertified_supervisor_binder(
        sup=sup, track=track, target=target
    ) or _handle_uncertified_foreman_binder(sup=sup, track=track, target=target)
