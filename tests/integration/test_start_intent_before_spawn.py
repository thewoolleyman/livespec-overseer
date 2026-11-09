"""Integration coverage for the start-intent record the attended relaunch surface writes.

Tier: `tests.integration` is one of the documented default `scenario_tiers`
prefixes. These tests drive the shipped `out_of_band_relaunch.relaunch` over a
real registry store and a fake tmux, whose launch input either kills the
process, as SIGKILL would, or fails and returns.
"""

from __future__ import annotations

import dataclasses
import json
import os
import signal
from pathlib import Path

import out_of_band_relaunch
import pytest
import registry
from test_supervisor_builders import FakeTmux, make_plan, make_supervisor, mapped_track

__all__: list[str] = []

_ACTION = "sanctioned-out-of-band-relaunch"
_INTENT_NAME = ".out-of-band-relaunch-intent.json"
_PROFILE: registry.ModelProfile = {"harness": "claude", "model": "claude-opus", "wrapper": None}


@pytest.fixture(autouse=True)
def _claude_on_path(*, tmp_path, monkeypatch):
    claude = tmp_path / "bin" / "claude"
    claude.parent.mkdir()
    claude.write_text("#!/bin/sh\n", encoding="utf-8")
    claude.chmod(0o755)
    monkeypatch.setenv("PATH", str(claude.parent))


def _dead_track_case(*, tmp_path: Path, topic: str = "alpha"):
    repo, _plan = make_plan(tmp_path=tmp_path, topic=topic)
    fake = FakeTmux()
    fake.sessions.add(topic)
    fake.cmds[topic] = "zsh"
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = dataclasses.replace(
        mapped_track(repo=repo, topic=topic, session=topic), model_profile=_PROFILE
    )
    registry.append_mapping(track=track, store_path=sup.store_path)
    request = out_of_band_relaunch.RelaunchRequest(topic=topic, target=topic, invoker="operator")
    return repo, fake, sup, track, request


def _intent_file(*, repo: Path, topic: str) -> Path:
    return repo / "tmp" / "overseer" / topic / _INTENT_NAME


def _relaunch_killed_during_spawn(*, fake, sup, request) -> int:
    pid = os.fork()
    if pid == 0:
        fake.on_paste = lambda _session, _text: os.kill(os.getpid(), signal.SIGKILL)
        _ = out_of_band_relaunch.relaunch(request=request, sup=sup)
        os._exit(0)
    _, status = os.waitpid(pid, 0)
    return status


@pytest.mark.integration
def test_a_killed_plan_start_leaves_an_attempted_and_failed_record_naming_its_invoker(*, tmp_path):
    repo, fake, sup, track, request = _dead_track_case(tmp_path=tmp_path)

    status = _relaunch_killed_during_spawn(fake=fake, sup=sup, request=request)

    assert os.WIFSIGNALED(status)
    assert os.WTERMSIG(status) == signal.SIGKILL
    record = json.loads(_intent_file(repo=repo, topic="alpha").read_text(encoding="utf-8"))
    assert record["action"] == _ACTION
    assert record["track"] == f"{repo}::alpha"
    assert record["invoker"] == "operator"
    assert record["target"] == "alpha"
    assert record["outcome"] is None
    assert "error" not in record
    assert registry.read_valid_mapping(store_path=sup.store_path) == [track]


@pytest.mark.integration
def test_an_outcome_less_intent_record_does_not_read_as_live_work(*, tmp_path):
    repo, fake, sup, track, request = _dead_track_case(tmp_path=tmp_path)
    never_attempted = _dead_track_case(tmp_path=tmp_path / "other", topic="beta")[0]
    _ = _relaunch_killed_during_spawn(fake=fake, sup=sup, request=request)
    intent = _intent_file(repo=repo, topic="alpha")
    assert json.loads(intent.read_text(encoding="utf-8"))["outcome"] is None

    fake.paste_ok = False
    retried = out_of_band_relaunch.relaunch(request=request, sup=sup)

    assert not retried.ok
    assert "launch input was not accepted" in retried.message
    assert json.loads(intent.read_text(encoding="utf-8"))["outcome"] == "launch_failed"
    assert registry.read_valid_mapping(store_path=sup.store_path) == [track]
    assert not _intent_file(repo=never_attempted, topic="beta").exists()


@pytest.mark.integration
def test_a_spawn_that_fails_and_returns_amends_its_intent_record_with_the_error(*, tmp_path):
    repo, fake, sup, track, request = _dead_track_case(tmp_path=tmp_path)
    fake.paste_ok = False

    result = out_of_band_relaunch.relaunch(request=request, sup=sup)

    assert not result.ok
    record = json.loads(_intent_file(repo=repo, topic="alpha").read_text(encoding="utf-8"))
    assert record["outcome"] == "launch_failed"
    assert record["error"] == result.message
    assert record["action"] == _ACTION
    assert record["track"] == f"{repo}::alpha"
    assert record["invoker"] == "operator"
    assert registry.read_valid_mapping(store_path=sup.store_path) == [track]
