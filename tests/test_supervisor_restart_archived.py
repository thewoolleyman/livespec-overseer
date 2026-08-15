"""Repo-level coverage for `_supervisor_restart.do_restart`'s archived-supervisor branch.

overseer-y26's residual: a supervisor track whose computed binder
(``plan/<topic>/supervisor-handoff.md``) is absent must branch on WHY. When the
plan thread was archived (or deleted), that absence is EXPECTED — the daemon must
retire the track quietly rather than alert with wording that reads as a genuinely
missing file (the wording that taught a prior supervisor to restore a banned
tombstone, 2026-08-04). Only a genuinely LIVE plan directory with no binder keeps
the pre-existing ``supervisor-handoff-missing`` alert, because that case IS
anomalous.

``import _supervisor_restart`` resolves via `tests/conftest.py`, which puts
`overseer/` on `sys.path` exactly as `overseer/conftest.py` does for the
beside-tests — so this module can import both the product collaborator and the
`overseer/test_supervisor_builders.py` / `test_supervisor_fakes.py` doubles by
their bare names.
"""

import contextlib
import io as _io
import os

import _supervisor_restart
import registry
import signals
from test_supervisor_builders import make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _supervisor_track(*, repo, topic, session):
    return mapped_track(repo=repo, topic=topic, session=session)


def _alert_key(*, repo, topic, condition):
    return (os.path.normpath(str(repo)), topic, condition)


def test_archived_supervisor_ready_is_retired_not_restarted(*, tmp_path):
    """RED/GREEN: the plan thread was cleanly archived (`git mv plan/<t> plan/archive/<t>`),
    so the computed `supervisor-handoff.md` path is gone by DESIGN, not by accident.
    `do_restart` must not attempt a restart, must not use the missing-file wording, and
    must close the round (clear the stale `ready` marker) rather than leave it to
    re-alert every tick."""
    topic = "archived-topic"
    entity_topic = f"{topic}-supervisor"
    repo = tmp_path / "repo"
    (repo / "plan" / "archive" / topic).mkdir(parents=True)  # archived, NOT live
    session = f"{topic}-supervisor"
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture="", cmd="node")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = _supervisor_track(repo=repo, topic=entity_topic, session=session)
    signals.marker_dir(repo=str(repo), topic=entity_topic).mkdir(parents=True)
    signals.state_path(repo=str(repo), topic=entity_topic).write_text("ready\n", encoding="utf-8")

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        _supervisor_restart.do_restart(sup=sup, track=track, target=session)

    assert not fake.has(method="respawn")  # no restart was attempted
    assert "supervisor-handoff-missing" not in err.getvalue()
    key = _alert_key(repo=repo, topic=entity_topic, condition="supervisor-topic-archived")
    assert key in sup.alerted
    assert "archived or gone" in sup.alerted[key]
    # The round is CLOSED — a stale `ready` marker must not linger and re-fire forever.
    assert signals.read_state(repo=str(repo), topic=entity_topic) is None


def test_live_plan_dir_with_absent_binder_still_alerts_supervisor_handoff_missing(*, tmp_path):
    """CONTROL: the plan directory is genuinely LIVE (never archived) and simply never
    got a `supervisor-handoff.md`. That case is anomalous and must keep today's
    `supervisor-handoff-missing` alert — proving the new branch only fires for the
    archived/gone case, not for every absent binder."""
    topic = "live-topic"
    entity_topic = f"{topic}-supervisor"
    repo = tmp_path / "repo"
    (repo / "plan" / topic).mkdir(parents=True)  # live plan dir, no binder inside it
    session = f"{topic}-supervisor"
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture="", cmd="node")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = _supervisor_track(repo=repo, topic=entity_topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        _supervisor_restart.do_restart(sup=sup, track=track, target=session)

    assert not fake.has(method="respawn")  # still refused — the binder really is absent
    key = _alert_key(repo=repo, topic=entity_topic, condition="supervisor-handoff-missing")
    assert key in sup.alerted
    archived_key = _alert_key(repo=repo, topic=entity_topic, condition="supervisor-topic-archived")
    assert archived_key not in sup.alerted
    assert registry.archived_or_gone(repo=str(repo), topic=topic) is False
