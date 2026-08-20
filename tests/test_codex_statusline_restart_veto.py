"""Codex restart statusline mismatch coverage."""

from __future__ import annotations

import contextlib
import io as _io
from dataclasses import replace

import pytest
import signals
from test_supervisor_builders import adopt_codex_ready, mapped_track

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_a_codex_restart_skips_statusline_model_mismatch_before_killing_the_pane(*, tmp_path):
    repo, topic, session, _session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    track = replace(
        mapped_track(repo=repo, topic=topic, session=session),
        model_profile={
            "harness": "codex",
            "model": "gpt-5.5-recorded",
            "statusline_model": "gpt-5.5 recorded",
            "wrapper": None,
        },
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup._do_codex_restart(track=track, target=fake.pane_id(session=session))

    assert not fake.has(method="respawn")
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert "statusline model mismatch" in err.getvalue()
    assert (str(repo), topic, "statusline-model-mismatch") in sup.alerted
    assert track.model_profile["statusline_model"] == "gpt-5.5 recorded"


def test_a_codex_restart_with_no_statusline_model_still_respawns(*, tmp_path):
    repo, topic, session, _session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    fake.panes[session] = "prior response\n"
    track = replace(
        mapped_track(repo=repo, topic=topic, session=session),
        model_profile={
            "harness": "codex",
            "model": "gpt-5.5-recorded",
            "statusline_model": "gpt-5.5 recorded",
            "wrapper": None,
        },
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        sup._do_codex_restart(track=track, target=fake.pane_id(session=session))

    assert fake.has(method="respawn")
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_RESTARTED


def test_a_codex_restart_with_matching_statusline_model_preserves_recorded_model(*, tmp_path):
    repo, topic, session, _session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    track = replace(
        mapped_track(repo=repo, topic=topic, session=session),
        model_profile={
            "harness": "codex",
            "model": "gpt-5.5-recorded",
            "statusline_model": "gpt-5.5 high",
            "wrapper": None,
        },
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        sup._do_codex_restart(track=track, target=fake.pane_id(session=session))

    respawn_cmds = [c[3] for c in fake.calls if c[0] == "respawn"]
    assert len(respawn_cmds) == 1
    assert "-m gpt-5.5-recorded" in respawn_cmds[0]
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_RESTARTED
