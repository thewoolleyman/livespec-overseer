"""Beside-tests for supervisor.py — a malformed state value is NO declaration for the wrap-up."""

import contextlib
import io as _io

import pytest
import registry
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    wrapup_count,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_malformed_state_value_still_receives_the_low_context_wrapup(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    declare(repo=repo, topic=topic, value="working: invented token")
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track=track, act=True)

    assert wrapup_count(fake=fake) == 1
    assert not fake.has(method="respawn")
    assert "MALFORMED state file" in err.getvalue()
    assert view.note is not None
    assert "BAD state file" in view.note
