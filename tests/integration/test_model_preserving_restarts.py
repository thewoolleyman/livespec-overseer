"""Integration-tier scenario tests for model-preserving Claude restarts."""

from __future__ import annotations

import contextlib
import io as _io
import stat
from dataclasses import replace
from importlib import import_module

from overseer import _supervisor_launch, registry, signals
from overseer.test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from overseer.test_supervisor_fakes import FakeTmux


def _types():
    module = import_module("_supervisor_launch_profile")
    return module.ClaudeLaunchPlan, module.LaunchProfileProblem


def test_launch_plan_scrubs_controlled_env_without_a_recorded_profile(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    track = mapped_track(repo=repo, topic=topic, session=topic)

    assert hasattr(_supervisor_launch, "claude_launch_plan")
    claude_launch_plan_type, _launch_profile_problem_type = _types()
    plan = _supervisor_launch.claude_launch_plan(track=track)

    assert isinstance(plan, claude_launch_plan_type)
    assert plan.command == f"claude --dangerously-skip-permissions -n {topic}"
    assert plan.env == {
        "ANTHROPIC_MODEL": None,
        "ANTHROPIC_SMALL_FAST_MODEL": None,
        "CLAUDE_CODE_DISABLE_1M_CONTEXT": None,
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": None,
    }


def test_launch_plan_uses_model_flag_for_a_cloud_profile(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    track = replace(
        mapped_track(repo=repo, topic=topic, session=topic),
        model_profile={
            "harness": "claude",
            "model": "claude-opus-4-1-20250805",
            "wrapper": None,
        },
    )

    assert hasattr(_supervisor_launch, "claude_launch_plan")
    claude_launch_plan_type, _launch_profile_problem_type = _types()
    plan = _supervisor_launch.claude_launch_plan(track=track)

    assert isinstance(plan, claude_launch_plan_type)
    assert plan.command == (
        f"claude --model claude-opus-4-1-20250805 --dangerously-skip-permissions -n {topic}"
    )
    assert all(value is None for value in plan.env.values())


def test_launch_plan_uses_wrapper_and_recorded_model_env(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    wrapper = tmp_path / "claude-local-llm"
    wrapper.write_text('#!/bin/sh\nexec claude "$@"\n', encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    track = replace(
        mapped_track(repo=repo, topic=topic, session=topic),
        model_profile={
            "harness": "claude",
            "model": "macmini/qwen3-coder-next",
            "wrapper": str(wrapper),
        },
    )

    assert hasattr(_supervisor_launch, "claude_launch_plan")
    claude_launch_plan_type, _launch_profile_problem_type = _types()
    plan = _supervisor_launch.claude_launch_plan(track=track)

    assert isinstance(plan, claude_launch_plan_type)
    assert plan.command == f"{wrapper} --dangerously-skip-permissions -n {topic}"
    assert plan.env == {
        "ANTHROPIC_MODEL": "macmini/qwen3-coder-next",
        "ANTHROPIC_SMALL_FAST_MODEL": None,
        "CLAUDE_CODE_DISABLE_1M_CONTEXT": None,
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": None,
    }


def test_launch_plan_rejects_a_harness_mismatch(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    track = replace(
        mapped_track(repo=repo, topic=topic, session=topic),
        model_profile={"harness": "codex", "model": "gpt-5-codex", "wrapper": None},
    )

    assert hasattr(_supervisor_launch, "claude_launch_plan")
    _claude_launch_plan_type, launch_profile_problem_type = _types()
    plan = _supervisor_launch.claude_launch_plan(track=track)

    assert isinstance(plan, launch_profile_problem_type)
    assert "cannot relaunch a Claude track" in plan.message


def _open_round(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    opened = sup.evaluate(track=track, act=True)

    assert opened.status == "warned"
    return repo, topic, session, fake, sup, track


def _restart_with_profile(*, tmp_path, model_profile):
    repo, topic, session, fake, sup, track = _open_round(tmp_path=tmp_path)
    track = replace(track, model_profile=model_profile)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=True)

    return repo, topic, session, fake, sup, view, err.getvalue()


def _respawns(*, fake):
    return [call for call in fake.calls if call[0] == "respawn"]


def test_scenario_restart_reasserts_an_explicitly_recorded_model(*, tmp_path):
    repo, topic, session, fake, _sup, view, _err = _restart_with_profile(
        tmp_path=tmp_path,
        model_profile={
            "harness": "claude",
            "model": "claude-opus-4-1-20250805",
            "wrapper": None,
        },
    )

    assert view.status == "restarting"
    assert _respawns(fake=fake) == [
        (
            "respawn",
            session,
            str(repo),
            f"claude --model claude-opus-4-1-20250805 --dangerously-skip-permissions -n {topic}",
            {
                "ANTHROPIC_MODEL": None,
                "ANTHROPIC_SMALL_FAST_MODEL": None,
                "CLAUDE_CODE_DISABLE_1M_CONTEXT": None,
                "CLAUDE_CODE_MAX_CONTEXT_TOKENS": None,
            },
        )
    ]


def test_scenario_restart_reasserts_a_local_llm_wrapper_and_env(*, tmp_path):
    wrapper = tmp_path / "claude-local-llm"
    wrapper.write_text('#!/bin/sh\nexec claude "$@"\n', encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    repo, topic, session, fake, _sup, view, _err = _restart_with_profile(
        tmp_path=tmp_path,
        model_profile={
            "harness": "claude",
            "model": "macmini/qwen3-coder-next",
            "wrapper": str(wrapper),
        },
    )

    assert view.status == "restarting"
    assert _respawns(fake=fake) == [
        (
            "respawn",
            session,
            str(repo),
            f"{wrapper} --dangerously-skip-permissions -n {topic}",
            {
                "ANTHROPIC_MODEL": "macmini/qwen3-coder-next",
                "ANTHROPIC_SMALL_FAST_MODEL": None,
                "CLAUDE_CODE_DISABLE_1M_CONTEXT": None,
                "CLAUDE_CODE_MAX_CONTEXT_TOKENS": None,
            },
        )
    ]


def test_scenario_stale_launch_profile_is_surfaced_and_restart_is_skipped(*, tmp_path):
    repo, topic, session, fake, sup, view, err = _restart_with_profile(
        tmp_path=tmp_path,
        model_profile={
            "harness": "claude",
            "model": "macmini/qwen3-coder-next",
            "wrapper": str(tmp_path / "missing-wrapper"),
        },
    )

    assert view.status == "restarting"
    assert _respawns(fake=fake) == []
    assert "stale launch profile" in err
    assert "does not exist" in err
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is not None
    )


def test_scenario_track_without_recorded_launch_profile_restarts_unaffected(*, tmp_path):
    repo, topic, session, fake, _sup, view, _err = _restart_with_profile(
        tmp_path=tmp_path,
        model_profile=None,
    )

    assert view.status == "restarting"
    assert _respawns(fake=fake) == [
        (
            "respawn",
            session,
            str(repo),
            f"claude --dangerously-skip-permissions -n {topic}",
            {
                "ANTHROPIC_MODEL": None,
                "ANTHROPIC_SMALL_FAST_MODEL": None,
                "CLAUDE_CODE_DISABLE_1M_CONTEXT": None,
                "CLAUDE_CODE_MAX_CONTEXT_TOKENS": None,
            },
        )
    ]
