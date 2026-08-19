"""Direct coverage for the foreman restart-binder guard."""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "overseer"))

import _supervisor_restart
import registry
from test_supervisor_builders import make_plan, make_supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_do_restart_refuses_foreman_without_epic_before_respawn(*, tmp_path):
    """The restart-side guard refuses a foreman track before tmux respawn."""
    repo, _topic = make_plan(tmp_path=tmp_path)
    topic = "repo-foreman"
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = registry.ForemanSeat(
        topic=topic,
        repo=str(repo),
        tmux=session,
        epic=registry.unresolved_plan_epic(topic=topic),
    )

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        _supervisor_restart.do_restart(sup=sup, track=track, target=session)

    assert not fake.has(method="respawn")
    assert "ready cannot respawn: no foreman epic recorded" in err.getvalue()
