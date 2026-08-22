"""Beside-tests for supervisor.py — Claude live-name gate.

Split from `test_supervisor_codex_restart_safety2.py` to keep the beside-test
modules below the LLOC margin while preserving the R2 Claude identity scenarios.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io

import pytest
import registry
from test_supervisor_builders import (
    adopt_sup,
    arm_ready_marker,
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


# --------------------------------------------------------------------------- #
# R2 — Claude identity gate `name == topic` parity + stale-mapping re-point
# (2026-07-18). Generic reused tmux windows (livespec1…) are cycled across topics,
# so a window the store maps to topic A but now running topic B's Claude (same repo)
# passed the process+cwd gate and got A's wrap-up injected into B — then a `ready`
# respawn-KILLED B as A. The Codex gate was already pane-scoped (`name == topic`);
# this brings the Claude gate to parity and re-points the stale mapping.
# --------------------------------------------------------------------------- #


def test_claude_act_refuses_pane_whose_live_name_differs_from_topic(*, tmp_path):
    """A pane running a live Claude for a DIFFERENT topic (same repo) is NOT ours: the gate
    rejects it on the `name != topic` proof, so the track never injects into nor respawns
    it and renders `session-gone` — even with a valid `ready` that WOULD otherwise restart."""
    repo, topic = make_plan(tmp_path=tmp_path, topic="alpha")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    # A genuinely-live Claude pane in this tmux session, cwd in the repo — but it is
    # topic BETA's session, not our track's ALPHA. (Process + cwd both pass; only the
    # name betrays it.)
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sup = adopt_sup(
        tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir, ppid={}, starttimes={}
    )  # empty registry → no live-outside-tmux
    # the live Claude here belongs to topic `beta`
    sup.claude_names_by_session = {session: {"beta"}}
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)  # would restart if the gate passed

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "session-gone"  # not ours → routed to session-gone, like a foreign pane
    assert not fake.has(method="respawn")  # never respawn-kill another topic's live Claude
    assert not fake.has(method="paste")  # never keystroke into it


def test_claude_gate_allows_pane_whose_live_name_matches_topic(*, tmp_path):
    """The parity check is POSITIVE-mismatch only: a matching `name == topic` (the normal
    case) still passes the gate and the track acts as before. Pairs with the refusal test so
    the check cannot be read as "reject unless proven" — it rejects only a proven mismatch."""
    repo, topic = make_plan(tmp_path=tmp_path, topic="alpha")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_names_by_session = {session: {"alpha"}}  # the live Claude here IS our topic
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "restarting"  # name matches → ours → the `ready` restart fires
    assert fake.has(method="respawn")
