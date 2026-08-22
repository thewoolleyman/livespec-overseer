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


def _codex_types():
    module = import_module("_supervisor_launch_profile")
    return module.CodexLaunchPlan, module.LaunchProfileProblem


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


def test_operator_start_launch_plan_does_not_set_unattended_resume_env(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    track = mapped_track(repo=repo, topic=topic, session=topic)

    claude_launch_plan_type, _launch_profile_problem_type = _types()
    plan = _supervisor_launch.claude_launch_plan(track=track, start=True)

    assert isinstance(plan, claude_launch_plan_type)
    assert "LIVESPEC_PLAN_UNATTENDED" not in plan.env


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


def _restart_with_profile(*, tmp_path, model_profile, restart_capture: str | None = None):
    repo, topic, session, fake, sup, track = _open_round(tmp_path=tmp_path)
    track = replace(track, model_profile=model_profile)
    if restart_capture is not None:
        fake.panes[session] = restart_capture
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
            "statusline_model": "Opus 4.8 (1M context)",
            "wrapper": None,
        },
        restart_capture=idle_capture(ctx=40),
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
                "LIVESPEC_PLAN_UNATTENDED": "1",
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
            "statusline_model": "macmini/qwen3-coder-next",
            "wrapper": str(wrapper),
        },
        restart_capture=idle_capture(ctx=40).replace(
            "Opus 4.8 (1M context)", "macmini/qwen3-coder-next"
        ),
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
                "LIVESPEC_PLAN_UNATTENDED": "1",
            },
        )
    ]


def test_scenario_stale_launch_profile_is_surfaced_and_restart_is_skipped(*, tmp_path):
    repo, topic, session, fake, sup, view, err = _restart_with_profile(
        tmp_path=tmp_path,
        model_profile={
            "harness": "claude",
            "model": "macmini/qwen3-coder-next",
            "statusline_model": "macmini/qwen3-coder-next",
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
                "LIVESPEC_PLAN_UNATTENDED": "1",
            },
        )
    ]


def test_codex_launch_plan_without_recorded_profile_matches_the_bare_command_byte_for_byte(
    *, tmp_path
):
    repo, topic = make_plan(tmp_path=tmp_path)
    track = mapped_track(repo=repo, topic=topic, session=topic)
    session_id = "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
    resume = "read /tmp/repo/plan/topic/handoff.md and follow it"

    assert hasattr(_supervisor_launch, "codex_launch_plan")
    codex_launch_plan_type, _launch_profile_problem_type = _codex_types()
    plan = _supervisor_launch.codex_launch_plan(
        track=track,
        session_id=session_id,
        resume=resume,
    )

    assert isinstance(plan, codex_launch_plan_type)
    assert plan.command == _supervisor_launch.codex_launch_command(
        session_id=session_id,
        resume=resume,
    )
    assert plan.env is None


def test_codex_daemon_restart_sets_unattended_resume_env_without_recorded_profile(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    track = mapped_track(repo=repo, topic=topic, session=topic)

    codex_launch_plan_type, _launch_profile_problem_type = _codex_types()
    plan = _supervisor_launch.codex_launch_plan(
        track=track,
        session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8",
        resume="read first",
        daemon_restart=True,
    )

    assert isinstance(plan, codex_launch_plan_type)
    assert plan.env == {"LIVESPEC_PLAN_UNATTENDED": "1"}


def test_codex_launch_plan_uses_m_flag_for_a_cloud_profile(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    track = replace(
        mapped_track(repo=repo, topic=topic, session=topic),
        model_profile={"harness": "codex", "model": "gpt-5-codex", "wrapper": None},
    )

    assert hasattr(_supervisor_launch, "codex_launch_plan")
    codex_launch_plan_type, _launch_profile_problem_type = _codex_types()
    plan = _supervisor_launch.codex_launch_plan(
        track=track,
        session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8",
        resume="read first",
    )

    assert isinstance(plan, codex_launch_plan_type)
    assert plan.command == (
        "codex -m gpt-5-codex resume --dangerously-bypass-approvals-and-sandbox "
        "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8 'read first'"
    )
    assert plan.env == {
        "ANTHROPIC_MODEL": None,
        "ANTHROPIC_SMALL_FAST_MODEL": None,
        "CLAUDE_CODE_DISABLE_1M_CONTEXT": None,
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": None,
    }


def test_codex_launch_plan_uses_wrapper_and_recorded_model_env(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    wrapper = tmp_path / "codex-local-llm"
    wrapper.write_text('#!/bin/sh\nexec codex "$@"\n', encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    track = replace(
        mapped_track(repo=repo, topic=topic, session=topic),
        model_profile={
            "harness": "codex",
            "model": "macmini/qwen3-coder-next",
            "wrapper": str(wrapper),
        },
    )

    assert hasattr(_supervisor_launch, "codex_launch_plan")
    codex_launch_plan_type, _launch_profile_problem_type = _codex_types()
    plan = _supervisor_launch.codex_launch_plan(
        track=track,
        session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8",
        resume="read first",
    )

    assert isinstance(plan, codex_launch_plan_type)
    assert plan.command == (
        f"{wrapper} resume --dangerously-bypass-approvals-and-sandbox "
        "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8 'read first'"
    )
    assert plan.env == {
        "ANTHROPIC_MODEL": "macmini/qwen3-coder-next",
        "ANTHROPIC_SMALL_FAST_MODEL": None,
        "CLAUDE_CODE_DISABLE_1M_CONTEXT": None,
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": None,
    }


def test_codex_launch_plan_rejects_a_harness_mismatch(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    track = replace(
        mapped_track(repo=repo, topic=topic, session=topic),
        model_profile={"harness": "claude", "model": "claude-opus", "wrapper": None},
    )

    assert hasattr(_supervisor_launch, "codex_launch_plan")
    _codex_launch_plan_type, launch_profile_problem_type = _codex_types()
    plan = _supervisor_launch.codex_launch_plan(
        track=track,
        session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8",
        resume="read first",
    )

    assert isinstance(plan, launch_profile_problem_type)
    assert "cannot relaunch a Codex track" in plan.message


def test_codex_launch_plan_rejects_a_stale_wrapper_profile(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    track = replace(
        mapped_track(repo=repo, topic=topic, session=topic),
        model_profile={
            "harness": "codex",
            "model": "macmini/qwen3-coder-next",
            "wrapper": str(tmp_path / "missing-codex-local-llm"),
        },
    )

    codex_launch_plan_type, launch_profile_problem_type = _codex_types()
    plan = _supervisor_launch.codex_launch_plan(
        track=track,
        session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8",
        resume="read first",
    )

    assert not isinstance(plan, codex_launch_plan_type)
    assert isinstance(plan, launch_profile_problem_type)
    assert "does not exist or is not executable" in plan.message
