"""A track the overseer STARTS carries an explicit model, so it is capturable from birth.

The launch-profile feature can only preserve a model it was able to CAPTURE, and the
primary source is argv. A track started with a bare command exposes no model token, so
adoption records no profile and every later relaunch takes the settings default — the
silent downgrade the launch-profile work exists to close.

These tests cover the START path ONLY. The two RELAUNCH paths (restart and reboot
recovery) keep the bare fail-soft command byte-for-byte, because
``SPECIFICATION/spec.md`` "The launch profile" ratifies that a row with no recorded
profile "MUST continue to relaunch exactly as it does today". The last test here is the
guard on that clause. See the blocking finding on work-item ``overseer-dnchj6`` for why
the start-side change alone is sufficient: a track started with an explicit model becomes
capturable, acquires a profile at adoption, and thereafter relaunches through the PROFILE
branch — so the forever-loop closes without touching fail-soft.
"""

from __future__ import annotations

import shlex
from dataclasses import replace
from importlib import import_module

from overseer import _supervisor_launch
from overseer.test_supervisor_builders import make_plan, mapped_track


def _profile_module():
    return import_module("_supervisor_launch_profile")


def _argv_bytes(*, command: str) -> bytes:
    """The NUL-delimited ``/proc/<pid>/cmdline`` bytes a pane running ``command`` exposes."""
    return b"\0".join(part.encode() for part in shlex.split(command)) + b"\0"


def _read_profile_from(*, command: str):
    module = _profile_module()
    argv = _argv_bytes(command=command)
    return module.read_launch_profile(
        pid=4242,
        harness="claude",
        pane_pid=None,
        cmdline_of=lambda *, pid: argv,
        environ_of=lambda *, pid: b"",
        ppid_of=lambda *, pid: None,
    )


def test_start_plan_carries_an_explicit_model_the_capture_can_read(*, tmp_path):
    """Leg 1 — the START command names a model, and the capture resolves it.

    Fails against pre-fix behavior, where the start command is bare and
    ``read_launch_profile`` returns a ``LaunchProfileProblem`` naming the missing token.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    track = mapped_track(repo=repo, topic=topic, session=topic)
    module = _profile_module()

    plan = _supervisor_launch.claude_launch_plan(track=track, start=True)

    assert isinstance(plan, module.ClaudeLaunchPlan)
    assert "--model" in plan.command
    profile = _read_profile_from(command=plan.command)
    assert not isinstance(profile, module.LaunchProfileProblem)
    assert profile["model"] == module.DEFAULT_START_MODEL


def test_started_model_token_round_trips_with_its_context_variant_intact(*, tmp_path):
    """Leg 3 — the discriminating leg.

    A fix that carries a bare model name passes legs 1 and 2 and still loses the
    context variant, which is the exact harm the epic exists to prevent. The bracketed
    alias must survive shell-quoting into argv and come back out as the FULL token, not
    collapsed to the base model name.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    track = mapped_track(repo=repo, topic=topic, session=topic)
    module = _profile_module()

    assert module.DEFAULT_START_MODEL.endswith("[1m]"), (
        "the default start model must name a context variant, or starting a track "
        "silently drops the 1M-context window the fleet actually runs"
    )

    plan = _supervisor_launch.claude_launch_plan(track=track, start=True)
    profile = _read_profile_from(command=plan.command)

    assert not isinstance(profile, module.LaunchProfileProblem)
    assert profile["model"] == module.DEFAULT_START_MODEL
    assert profile["model"] != module.DEFAULT_START_MODEL.partition("[")[0]


def test_start_does_not_overwrite_an_already_recorded_profile(*, tmp_path):
    """Leg 4 — fail-soft for tracks that already carry a profile.

    Starting must re-assert the RECORDED model, never substitute the new default.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    recorded = "claude-opus-4-1-20250805"
    track = replace(
        mapped_track(repo=repo, topic=topic, session=topic),
        model_profile={"harness": "claude", "model": recorded, "wrapper": None},
    )
    module = _profile_module()

    plan = _supervisor_launch.claude_launch_plan(track=track, start=True)

    assert isinstance(plan, module.ClaudeLaunchPlan)
    assert plan.command == (f"claude --model {recorded} --dangerously-skip-permissions -n {topic}")
    assert module.DEFAULT_START_MODEL not in plan.command


def test_a_relaunch_without_a_profile_stays_exactly_bare(*, tmp_path):
    """The ratified fail-soft clause, guarded.

    ``SPECIFICATION/spec.md`` requires that a row with no recorded profile "MUST
    continue to relaunch exactly as it does today". The start-side change must not leak
    into either relaunch path, so the default call — the one both relaunch paths make —
    stays byte-for-byte bare.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    track = mapped_track(repo=repo, topic=topic, session=topic)
    module = _profile_module()

    plan = _supervisor_launch.claude_launch_plan(track=track)

    assert isinstance(plan, module.ClaudeLaunchPlan)
    assert plan.command == f"claude --dangerously-skip-permissions -n {topic}"
    assert "--model" not in plan.command
