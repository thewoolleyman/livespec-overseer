"""Focused branch controls for binding Codex to a Herdr replacement round."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import _herdr_replacement_authorization
import _supervisor_herdr_codex
import herdr_identity
import pytest
from _codex_session_models import CodexSession
from _supervisor_launch_profile import CodexLaunchPlan
from test_supervisor_builders import FakeTmux, make_plan, make_supervisor, mapped_track

OLD_ROLLOUT = "019f548d-0000-7000-8000-000000000001"


def _world(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    target = "pane"
    fake = FakeTmux()
    fake.serve(session=target, repo=repo, cmd="codex")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = replace(
        mapped_track(repo=repo, topic=topic, session=target),
        model_profile={"harness": "codex", "model": "gpt-5.5", "wrapper": None},
    )
    sup.live_codex[(target, topic)] = CodexSession(
        pid=201,
        name=topic,
        cwd=str(repo),
        session_id=OLD_ROLLOUT,
    )
    sup.starttime_of = lambda *, pid: "old-start" if pid == 201 else None
    return sup, track, target


def test_codex_binding_freezes_fresh_profile_rollout_and_resume(*, tmp_path, monkeypatch) -> None:
    sup, track, target = _world(tmp_path=tmp_path)
    captured = {}

    def begin(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(reason="bound")

    monkeypatch.setattr(
        _supervisor_herdr_codex._supervisor_herdr_replacement,
        "begin_herdr_replacement",
        begin,
    )

    result = _supervisor_herdr_codex.begin_codex_replacement(sup=sup, track=track, target=target)

    assert result.reason == "bound"
    binding = captured["binding"]
    assert binding.runtime == "codex"
    assert binding.predecessor_identity == f"codex:201:old-start:{track.topic}"
    assert binding.predecessor_rollout == OLD_ROLLOUT
    assert "overseer-test-epic" in binding.resume
    launch = captured["launch"]
    assert " resume " not in launch.command
    assert "-m gpt-5.5" in launch.command
    assert launch.env["ANTHROPIC_MODEL"] is None


@pytest.mark.parametrize("hazard", ["missing-live", "invalid-rollout", "missing-starttime"])
def test_codex_binding_refuses_unstable_predecessor(*, tmp_path, monkeypatch, hazard: str) -> None:
    sup, track, target = _world(tmp_path=tmp_path)
    if hazard == "missing-live":
        sup.live_codex.clear()
    elif hazard == "invalid-rollout":
        sup.live_codex[(target, track.topic)] = CodexSession(
            pid=201, name=track.topic, cwd=track.repo, session_id="not-a-rollout"
        )
    else:
        sup.starttime_of = lambda *, pid: None
    began = []
    monkeypatch.setattr(
        _supervisor_herdr_codex._supervisor_herdr_replacement,
        "begin_herdr_replacement",
        lambda **kwargs: began.append(kwargs),
    )

    result = _supervisor_herdr_codex.begin_codex_replacement(sup=sup, track=track, target=target)

    assert result is None
    assert began == []
    assert any(key[-1] == "codex-session-vanished-before-restart" for key in sup.alerted)


def test_codex_binding_refuses_missing_resume(*, tmp_path, monkeypatch) -> None:
    sup, track, target = _world(tmp_path=tmp_path)
    began = []
    monkeypatch.setattr(_supervisor_herdr_codex, "resume_for_track", lambda **kwargs: None)
    monkeypatch.setattr(
        _supervisor_herdr_codex._supervisor_herdr_replacement,
        "begin_herdr_replacement",
        lambda **kwargs: began.append(kwargs),
    )

    result = _supervisor_herdr_codex.begin_codex_replacement(sup=sup, track=track, target=target)

    assert result is None
    assert began == []
    assert any(key[-1] == "restart-plan-epic-missing" for key in sup.alerted)


@pytest.mark.parametrize("healed", [False, True])
def test_codex_binding_routes_profile_problem_through_self_heal(
    *, tmp_path, monkeypatch, healed: bool
) -> None:
    sup, track, target = _world(tmp_path=tmp_path)
    track = replace(
        track,
        model_profile={"harness": "claude", "model": "opus[1m]", "wrapper": None},
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex, "heal_cross_runtime_profile", lambda **kwargs: healed
    )

    result = _supervisor_herdr_codex.begin_codex_replacement(sup=sup, track=track, target=target)

    assert result is None
    assert healed or any(key[-1] == "stale-launch-profile" for key in sup.alerted)


def test_codex_binding_honors_statusline_refusal(*, tmp_path, monkeypatch) -> None:
    sup, track, target = _world(tmp_path=tmp_path)
    began = []
    monkeypatch.setattr(_supervisor_herdr_codex, "statusline_mismatch", lambda **kwargs: True)
    monkeypatch.setattr(
        _supervisor_herdr_codex._supervisor_herdr_replacement,
        "begin_herdr_replacement",
        lambda **kwargs: began.append(kwargs),
    )

    result = _supervisor_herdr_codex.begin_codex_replacement(sup=sup, track=track, target=target)

    assert result is None
    assert began == []


def test_authorization_persists_optional_codex_rollout_and_resume(*, tmp_path, monkeypatch) -> None:
    sup, track, _target = _world(tmp_path=tmp_path)
    target = herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=str(tmp_path / "herdr.sock"),
            server_pid=700,
            server_starttime="server-start",
            pane_id="w1:p9",
        )
    )
    shell = SimpleNamespace(
        pid=100,
        starttime="shell-start",
        executable="/bin/bash",
        argv=("/bin/bash",),
        process_group=100,
        session_id=90,
    )
    predecessor = SimpleNamespace(
        pid=201,
        starttime="old-start",
        executable="/usr/bin/codex",
        argv=("codex",),
        process_group=200,
        session_id=90,
    )
    monkeypatch.setattr(
        _herdr_replacement_authorization.registry,
        "read_round_record",
        lambda **kwargs: SimpleNamespace(
            at=1000.0,
            session_identity=f"codex:201:old-start:{track.topic}",
        ),
    )
    monkeypatch.setattr(
        _herdr_replacement_authorization.signals,
        "read_state",
        lambda **kwargs: SimpleNamespace(mtime=1001.0),
    )

    transaction, reason = _herdr_replacement_authorization.bind_authorization(
        sup=sup,
        track=track,
        target=target,
        launch=CodexLaunchPlan(command="codex", env={}),
        snapshot=SimpleNamespace(
            shell=shell,
            foreground_group=200,
            processes=(shell, predecessor),
        ),
        binding=_herdr_replacement_authorization.ReplacementBinding(
            runtime="codex",
            predecessor_identity=f"codex:201:old-start:{track.topic}",
            predecessor_rollout=OLD_ROLLOUT,
            resume="read handoff",
        ),
    )

    assert reason == ""
    assert transaction is not None
    assert transaction["predecessor_rollout"] == OLD_ROLLOUT
    assert transaction["resume"] == "read handoff"

    without_resume, reason = _herdr_replacement_authorization.bind_authorization(
        sup=sup,
        track=track,
        target=target,
        launch=CodexLaunchPlan(command="codex", env={}),
        snapshot=SimpleNamespace(
            shell=shell,
            foreground_group=200,
            processes=(shell, predecessor),
        ),
        binding=_herdr_replacement_authorization.ReplacementBinding(
            runtime="codex",
            predecessor_identity=f"codex:201:old-start:{track.topic}",
            predecessor_rollout=OLD_ROLLOUT,
        ),
    )
    assert reason == ""
    assert without_resume is not None
    assert "resume" not in without_resume
