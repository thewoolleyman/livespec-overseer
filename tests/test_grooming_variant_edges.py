"""Edge coverage for the grooming mapping-row variant."""

from __future__ import annotations

import pytest
import registry
from _registry_track_row_parse import RowExtras, track_from_mapping_row

__all__: list[str] = []


def _extras() -> RowExtras:
    return RowExtras(
        resume=None,
        ctx_threshold=None,
        pinned_session_id=None,
        observed_session_identity=None,
        added_at=None,
        model_profile=None,
    )


def test_legacy_grooming_row_without_kind_parses_from_reserved_suffix():
    track = track_from_mapping_row(
        row={"topic": "repo-grooming", "repo": "/repo", "tmux": "repo-grooming"},
        extras=_extras(),
    )

    assert isinstance(track, registry.GroomingSeat)
    assert track.kind == "grooming"
    assert track.epic == registry.unresolved_plan_epic(topic="repo-grooming")


def test_grooming_seat_rejects_missing_required_identity_fields():
    with pytest.raises(ValueError, match="grooming seat requires tmux"):
        registry.GroomingSeat(topic="repo-grooming", repo="/repo", tmux="", epic="epic")
    with pytest.raises(ValueError, match="grooming seat requires epic"):
        registry.GroomingSeat(topic="repo-grooming", repo="/repo", tmux="repo-grooming", epic="")

    track = registry.GroomingSeat(
        topic="repo-grooming",
        repo="/repo",
        tmux="repo-grooming",
        epic=registry.unresolved_plan_epic(topic="repo-grooming"),
    )
    assert track.assigned is True
    assert track.is_unassigned is False
