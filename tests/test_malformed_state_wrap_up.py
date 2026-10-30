"""A malformed `.overseer-state` value is no declaration, so the wrap-up still lands.

The supervision package resolves via tests/conftest.py.
"""

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
