"""Integration coverage for Codex launch-time update-check suppression."""

from __future__ import annotations

from dataclasses import replace
from importlib import import_module

from overseer import _supervisor_launch
from overseer.test_supervisor_builders import make_plan, mapped_track


def test_scenario_codex_launches_disable_the_startup_update_check(*, tmp_path) -> None:
    """Fresh, resumed, and profile-less Codex launches share one transient override."""
    repo, topic = make_plan(tmp_path=tmp_path)
    profiled_track = replace(
        mapped_track(repo=repo, topic=topic, session=topic),
        model_profile={"harness": "codex", "model": "gpt-5-codex", "wrapper": None},
    )
    unprofiled_track = mapped_track(repo=repo, topic=topic, session=topic)
    launch_profile = import_module("_supervisor_launch_profile")

    fresh = launch_profile.codex_fresh_launch_plan(track=profiled_track)
    resumed = _supervisor_launch.codex_launch_plan(
        track=profiled_track,
        session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8",
        resume="read first",
    )
    without_profile = _supervisor_launch.codex_launch_plan(
        track=unprofiled_track,
        session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8",
        resume="read first",
    )

    assert all(
        "-c check_for_update_on_startup=false" in plan.command
        for plan in (fresh, resumed, without_profile)
    )
    assert profiled_track.model_profile == {
        "harness": "codex",
        "model": "gpt-5-codex",
        "wrapper": None,
    }
