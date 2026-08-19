"""Codex reboot-recovery launch-profile behavior."""

from __future__ import annotations

import dataclasses
import shlex
import stat

import pytest
import registry
import supervisor
from test_supervisor_builders import (
    TEST_EPIC,
    codex_home_with,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_recover_resumes_a_codex_track_with_its_recorded_wrapper_profile(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    wrapper = tmp_path / "codex-local-llm"
    wrapper.write_text('#!/bin/sh\nexec codex "$@"\n', encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    fake = FakeTmux()
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        codex_home=str(codex_home_with(tmp_path=tmp_path, topic=topic, session_id=sid)),
    )
    registry.append_mapping(
        track=dataclasses.replace(
            mapped_track(repo=repo, topic=topic, session=session),
            model_profile={
                "harness": "codex",
                "model": "macmini/qwen3-coder-next",
                "wrapper": str(wrapper),
            },
        ),
        store_path=sup.store_path,
    )

    recovered = sup.recover_missing_sessions()

    assert recovered == [session]
    assert (
        "respawn",
        session,
        str(repo),
        f"{wrapper} resume --dangerously-bypass-approvals-and-sandbox "
        f"{sid} {shlex.quote(supervisor.plan_epic_resume(repo=str(repo), epic=TEST_EPIC))}",
        {
            "ANTHROPIC_MODEL": "macmini/qwen3-coder-next",
            "ANTHROPIC_SMALL_FAST_MODEL": None,
            "CLAUDE_CODE_DISABLE_1M_CONTEXT": None,
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS": None,
        },
    ) in fake.calls


def test_recover_surfaces_and_skips_a_codex_track_with_a_stale_profile(*, tmp_path, capsys):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    fake = FakeTmux()
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        codex_home=str(codex_home_with(tmp_path=tmp_path, topic=topic, session_id=sid)),
    )
    registry.append_mapping(
        track=dataclasses.replace(
            mapped_track(repo=repo, topic=topic, session=session),
            model_profile={
                "harness": "claude",
                "model": "claude-opus",
                "wrapper": None,
            },
        ),
        store_path=sup.store_path,
    )

    recovered = sup.recover_missing_sessions()

    assert recovered == []
    assert fake.has(method="new")
    assert not fake.has(method="respawn")
    err = capsys.readouterr().err
    assert "cannot relaunch a Codex track" in err
    assert "skipping" in err
