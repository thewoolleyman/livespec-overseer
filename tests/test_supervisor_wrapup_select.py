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


def test_select_wrapup_message_selects_the_foreman_variant_text():
    track = registry.Track(
        topic="repo-foreman",
        repo=REPO,
        tmux="repo-foreman",
        epic=EPIC,
    )

    assert _selected(track=track) == _supervisor_prompts.foreman_wrapup_message(
        remaining=REMAINING,
        repo=REPO,
        topic="repo-foreman",
        epic=EPIC,
    )


def test_select_wrapup_message_selects_the_grooming_variant_text():
    track = registry.Track(
        topic="repo-grooming",
        repo=REPO,
        tmux="repo-grooming",
        epic=EPIC,
    )

    assert _selected(track=track) == _supervisor_prompts.grooming_wrapup_message(
        remaining=REMAINING,
        repo=REPO,
        topic="repo-grooming",
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
    track = track_from_mapping_row(
        row={
            "kind": "foreman",
            "topic": "alpha-supervisor",
            "repo": REPO,
            "tmux": "alpha-supervisor",
            "epic": EPIC,
        },
        extras=_extras(),
    )
    assert isinstance(track, registry.ForemanSeat)

    assert _selected(track=track) == _supervisor_prompts.foreman_wrapup_message(
        remaining=REMAINING,
        repo=REPO,
        topic="alpha-supervisor",
        epic=EPIC,
    )
