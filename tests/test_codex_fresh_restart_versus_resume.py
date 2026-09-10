"""The Codex fresh-wrap-up versus resume-on-crash split, pinned at both ends.

One command shape used to serve both arms, and that is precisely what made the wrap-up
restart a no-op: ``codex resume <id>`` reattaches the prior rollout AND the context it
accumulated, so a restart authorised by a ``ready`` declaration spent the declaration
while handing the successor the same exhausted window (measured live on
``fix-git-email`` 2026-09-10 — one rollout id resumed four times, 50% → 17% remaining).

The two arms answer different questions, so they are pinned together here: a wrap-up
restart owes its successor a RESET window, and crash recovery owes its successor the
conversation the crash interrupted. A change that collapses them again reddens this
module from whichever end it is collapsed toward.
"""

from __future__ import annotations

import stat
from dataclasses import replace

import registry
import supervisor
from _supervisor_launch_profile import (
    CodexLaunchPlan,
    LaunchProfileProblem,
    codex_fresh_launch_plan,
    codex_launch_plan,
)
from test_supervisor_builders import (
    TEST_EPIC,
    codex_dead_track,
    codex_home_with,
    make_plan,
    make_supervisor,
    mapped_track,
    verify_codex_respawn,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

SESSION_ID = "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
SCRUBBED_ENV = {
    "ANTHROPIC_MODEL": None,
    "ANTHROPIC_SMALL_FAST_MODEL": None,
    "CLAUDE_CODE_DISABLE_1M_CONTEXT": None,
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS": None,
}


def _codex_track(*, tmp_path, profile=None):
    repo, topic = make_plan(tmp_path=tmp_path)
    track = mapped_track(repo=repo, topic=topic, session=topic)
    return track if profile is None else replace(track, model_profile=profile)


def test_the_wrapup_arm_launches_fresh_where_the_recovery_arm_resumes(*, tmp_path):
    """The whole defect, in one comparison: same track, two arms, two commands.

    The fresh arm carries no ``resume`` subcommand and no positional session id, so Codex
    opens a rollout of its own with an empty context window — the reset a wrap-up restart
    exists to deliver. The recovery arm names the exact persisted rollout, because
    restoring the interrupted conversation is what recovery is for. Sabotage: point the
    wrap-up restart back at ``codex_launch_plan`` and the two commands become one.
    """
    track = _codex_track(tmp_path=tmp_path)

    fresh = codex_fresh_launch_plan(track=track)
    resumed = codex_launch_plan(track=track, session_id=SESSION_ID, resume="read first")

    assert isinstance(fresh, CodexLaunchPlan) and isinstance(resumed, CodexLaunchPlan)
    assert fresh.command == "codex --dangerously-bypass-approvals-and-sandbox"
    assert resumed.command == (
        "codex resume --dangerously-bypass-approvals-and-sandbox " f"{SESSION_ID} 'read first'"
    )
    assert SESSION_ID not in fresh.command  # the exhausted window is never handed back
    # Autonomy is NOT what differs: both arms keep the codex twin of
    # `--dangerously-skip-permissions`, or the successor stalls on its first approval.
    assert "--dangerously-bypass-approvals-and-sandbox" in fresh.command
    assert fresh.env == SCRUBBED_ENV


def test_a_fresh_wrapup_launch_marks_the_successor_unattended(*, tmp_path):
    """A daemon-driven restart is unattended on BOTH arms; the fresh one is no exception."""
    track = _codex_track(tmp_path=tmp_path)

    plan = codex_fresh_launch_plan(track=track, daemon_restart=True)

    assert isinstance(plan, CodexLaunchPlan)
    assert plan.env == {**SCRUBBED_ENV, "LIVESPEC_PLAN_UNATTENDED": "1"}


def test_a_fresh_wrapup_launch_re_asserts_a_recorded_cloud_model(*, tmp_path):
    """Launching fresh must not silently drop the model the track was supervised under."""
    track = _codex_track(
        tmp_path=tmp_path,
        profile={"harness": "codex", "model": "gpt-5-codex", "wrapper": None},
    )

    plan = codex_fresh_launch_plan(track=track)

    assert isinstance(plan, CodexLaunchPlan)
    assert plan.command == "codex -m gpt-5-codex --dangerously-bypass-approvals-and-sandbox"
    assert plan.env == SCRUBBED_ENV


def test_a_fresh_wrapup_launch_goes_through_the_recorded_wrapper_with_its_model(*, tmp_path):
    """The wrapper arm keeps the `-m` mechanism the resume arm needed, for the same reason.

    `codex-local-llm` execs `codex -c model_provider=… "$@"` and reads ANTHROPIC_MODEL
    nowhere, so the env assignment alone preserves the PROVIDER while leaving the model to
    Codex's own picker. The flag rides `"$@"`; the env assignment stays because the
    set-or-scrub rule binds every relaunch of every harness independently.
    """
    wrapper = tmp_path / "codex-local-llm"
    wrapper.write_text('#!/bin/sh\nexec codex "$@"\n', encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    track = _codex_track(
        tmp_path=tmp_path,
        profile={
            "harness": "codex",
            "model": "macmini/qwen3-coder-next",
            "wrapper": str(wrapper),
        },
    )

    plan = codex_fresh_launch_plan(track=track)

    assert isinstance(plan, CodexLaunchPlan)
    assert plan.command == (
        f"{wrapper} -m macmini/qwen3-coder-next --dangerously-bypass-approvals-and-sandbox"
    )
    assert plan.env == {**SCRUBBED_ENV, "ANTHROPIC_MODEL": "macmini/qwen3-coder-next"}


def test_a_fresh_wrapup_launch_refuses_a_missing_wrapper(*, tmp_path):
    """A wrapper that is gone is surfaced, never degraded into a bare cloud launch."""
    track = _codex_track(
        tmp_path=tmp_path,
        profile={
            "harness": "codex",
            "model": "macmini/qwen3-coder-next",
            "wrapper": str(tmp_path / "gone"),
        },
    )

    plan = codex_fresh_launch_plan(track=track)

    assert isinstance(plan, LaunchProfileProblem)
    assert "does not exist or is not executable" in plan.message


def test_a_fresh_wrapup_launch_refuses_a_claude_profile(*, tmp_path):
    """Runtime never switches on a restart — not on the fresh arm either."""
    track = _codex_track(
        tmp_path=tmp_path,
        profile={"harness": "claude", "model": "claude-opus", "wrapper": None},
    )

    plan = codex_fresh_launch_plan(track=track)

    assert isinstance(plan, LaunchProfileProblem)
    assert "cannot relaunch a Codex track" in plan.message


def test_crash_recovery_still_resumes_the_exact_persisted_rollout(*, tmp_path):
    """The other end of the split, driven end-to-end: recovery is NOT a fresh launch.

    A dead Codex track's conversation survives on disk as its rollout, and recovery exists
    to bring THAT back — so it resumes the exact uuid its mapping row recorded, and the
    kick rides the argv positional Codex auto-submits. Nothing about the wrap-up arm's
    fresh launch may leak here: a fresh session would orphan the rollout and silently
    discard the interrupted conversation.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()  # the tmux session is absent → recovery must recreate it
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        codex_home=str(codex_home_with(tmp_path=tmp_path, topic=topic, session_id=SESSION_ID)),
    )
    registry.append_mapping(
        track=codex_dead_track(repo=repo, topic=topic, session=session, session_id=SESSION_ID),
        store_path=sup.store_path,
    )
    verify_codex_respawn(sup=sup, fake=fake, plan=(repo, topic, session), session_id=SESSION_ID)

    assert sup.recover_missing_sessions() == [session]

    commands = [call[3] for call in fake.calls if call[0] == "respawn"]
    assert len(commands) == 1
    assert commands[0] == (
        "codex resume --dangerously-bypass-approvals-and-sandbox "
        f"{SESSION_ID} "
        f"{supervisor.plan_epic_resume(repo=str(repo), epic=TEST_EPIC)!r}"
    )
    assert SESSION_ID in commands[0]  # the SAME rollout, by its persisted identifier
    assert "claude" not in commands[0]
    # The fresh-launch command must never be what recovery issues.
    fresh = codex_fresh_launch_plan(track=mapped_track(repo=repo, topic=topic, session=session))
    assert isinstance(fresh, CodexLaunchPlan)
    assert commands[0] != fresh.command
    assert not fake.has(method="paste")  # recovery's kick is argv, not a pasted prompt
