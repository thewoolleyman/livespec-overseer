"""Variant-dispatch edge coverage."""

import _supervisor_prompts
import registry

__all__: list[str] = []


def test_unassigned_plan_has_no_restart_resume_prompt():
    track = registry.UnassignedPlan.make(repo="/repo", topic="waiting")

    assert _supervisor_prompts.resume_for_track(track=track) is None


def test_supervisor_entity_without_live_worker_counts_archived_or_gone(*, tmp_path):
    repo = tmp_path / "repo"
    (repo / "plan").mkdir(parents=True)

    assert registry.archived_or_gone(repo=str(repo), topic="missing-supervisor") is True
