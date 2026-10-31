"""A malformed `.overseer-state` value is no declaration, so the wrap-up still lands.

The supervision package resolves via tests/conftest.py.
"""

import contextlib
import io as _io
from pathlib import Path

import _supervisor_state
import pytest
import registry
import signals
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


@pytest.mark.parametrize("ctx", [30, 13])
def test_malformed_state_value_still_receives_the_wrap_up(*, tmp_path, ctx):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx))
    err = _io.StringIO()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    declare(repo=repo, topic=topic, value="working: invented token", mtime=1001.0)

    with contextlib.redirect_stderr(err):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert fake.has(method="paste")
    assert not fake.has(method="respawn")
    assert "MALFORMED state file" in err.getvalue()


def test_standing_rejected_copy_stays_in_attention_and_next_wrapup(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    signals.rejected_state_path(repo=str(repo), topic=topic).parent.mkdir(parents=True)
    signals.rejected_state_path(repo=str(repo), topic=topic).write_text(
        "bad state\n", encoding="utf-8"
    )

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.note == "BAD state file: 'bad state'"
    assert any("rejected state value: 'bad state'" in text for text in fake.paste_texts())


def test_unreadable_rejected_copy_has_no_session_notice(*, tmp_path, monkeypatch):
    repo, topic = make_plan(tmp_path=tmp_path)
    rejected = signals.rejected_state_path(repo=str(repo), topic=topic)
    rejected.parent.mkdir(parents=True)
    rejected.write_text("bad state\n", encoding="utf-8")

    def refuse_read_text(self, *, encoding=None, errors=None):
        raise OSError("evidence unreadable")

    monkeypatch.setattr(Path, "read_text", refuse_read_text)

    assert signals.rejected_value(repo=str(repo), topic=topic) is None
    assert signals.rejected_value_notice(repo=str(repo), topic=topic) == ""


def test_rejection_and_restart_cleanup_failures_are_surfaced(*, tmp_path, monkeypatch):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    state = declare(repo=repo, topic=topic, value="working: invalid", mtime=1001.0)

    def refuse_replace(self, target):
        raise OSError("rejection denied")

    monkeypatch.setattr(Path, "replace", refuse_replace)
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        _ = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert state.exists()
    assert "malformed-state-rejection-failed" in err.getvalue()

    def refuse_unlink(self, *, missing_ok=False):
        raise OSError("cleanup denied")

    monkeypatch.setattr(Path, "unlink", refuse_unlink)
    assert (
        _supervisor_state.delete_rejected_state_file(
            sup=sup, track=mapped_track(repo=repo, topic=topic, session=session)
        )
        is False
    )
