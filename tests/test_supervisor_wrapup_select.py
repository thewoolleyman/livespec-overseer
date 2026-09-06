"""Direct coverage for low-context wrap-up selection."""

import _supervisor_prompts
import _supervisor_wrapup_select
import registry
from _registry_track_row_parse import RowExtras, track_from_mapping_row

__all__: list[str] = []

REMAINING = 42
REPO = "/repo"
EPIC = "overseer-alpha"


def _extras() -> RowExtras:
    return RowExtras(
        resume=None,
        ctx_threshold=None,
        idle_nudge=None,
        pinned_session_id=None,
        observed_session_identity=None,
        added_at=None,
        model_profile=None,
    )


def _worker_wrapup(remaining: int, repo: str, topic: str, epic: str | None) -> str:
    return _supervisor_prompts.wrapup_message(
        remaining=remaining,
        repo=repo,
        topic=topic,
        epic=epic,
    )


def _selected(*, track: registry.Track) -> str:
    return _supervisor_wrapup_select.select_wrapup_message(
        track=track,
        remaining=REMAINING,
        worker_wrapup=_worker_wrapup,
    )


def test_select_wrapup_message_selects_the_supervisor_variant_text():
    track = registry.Track(
        topic="alpha-supervisor",
        repo=REPO,
        tmux="alpha-supervisor",
        epic=EPIC,
    )

    assert _selected(track=track) == _supervisor_prompts.supervisor_wrapup_message(
        remaining=REMAINING,
        repo=REPO,
        topic="alpha",
        epic=EPIC,
    )


def test_select_wrapup_message_selects_the_plan_variant_text():
    track = registry.Track(
        topic="alpha",
        repo=REPO,
        tmux="alpha",
        epic=EPIC,
    )

    assert _selected(track=track) == _supervisor_prompts.wrapup_message(
        remaining=REMAINING,
        repo=REPO,
        topic="alpha",
        epic=EPIC,
    )


def test_select_wrapup_message_uses_loaded_variant_before_topic_suffix():
    """Selection reads the LOADED record type, never the topic's suffix.

    The vehicle is a `plan` row whose topic nonetheless ends in `-supervisor`: if
    selection sniffed the suffix it would pick the supervisor variant, and it must
    pick the plan one. This used to be spelled with a grooming row and is respelled
    rather than dropped, because the precedence it pins is unchanged by that cut.
    """
    track = track_from_mapping_row(
        row={
            "kind": "plan",
            "topic": "alpha-supervisor",
            "repo": REPO,
            "tmux": "alpha-supervisor",
            "epic": EPIC,
        },
        extras=_extras(),
    )
    assert isinstance(track, registry.PlanTrack)

    assert _selected(track=track) == _supervisor_prompts.wrapup_message(
        remaining=REMAINING,
        repo=REPO,
        topic="alpha-supervisor",
        epic=EPIC,
    )
