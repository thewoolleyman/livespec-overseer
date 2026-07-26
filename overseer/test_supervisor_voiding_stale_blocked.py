"""Beside-tests for supervisor.py — voiding stale blocked.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io

import pytest
import registry
import signals
import supervisor
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


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_stale_blocked_is_voided_for_an_in_process_sub_agent(tmp_path):
    """Claude `busy` with no spinner (an in-process Task sub-agent) is still GENERATING —
    the session is working, not waiting — so a stale declaration is voided here too."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))  # pane looks idle
    sup = make_supervisor(tmp_path, fake)
    sup._claude_status = {session: "busy"}  # sub-agent running in-process
    declare(repo, topic, "blocked: stale", mtime=800.0)
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "working"
    assert signals.read_state(str(repo), topic) is None  # voided


def test_idle_blocked_session_is_never_voided(tmp_path):
    """The load-bearing case: a session sitting blocked and NOT busy keeps its
    declaration forever and keeps alerting. Voiding is scoped to "resumed generating"."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path, fake)
    sup._claude_status = {session: "waiting"}
    declare(repo, topic, "blocked: still waiting on you", mtime=800.0)
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "blocked:human"
    state = signals.read_state(str(repo), topic)
    assert state is not None and state.token == signals.STATE_BLOCKED


def test_nudge_marker_is_not_an_attention_status():
    """`idle-with-context-left` is the daemon handling it, not a human hand-off — it must
    NOT appear in the NEEDS YOU block."""
    view = supervisor.RowView(
        topic="t", repo="/r", tmux="s", ctx=73, status="idle-with-context-left"
    )
    assert supervisor.needs_attention(view) is False


def test_live_track_without_supervisor_handoff_offers_supervise_plan_once(tmp_path):
    """Surface A: a live matching session with no durable supervisor prompt is surfaced
    once, not re-alerted every tick."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path, fake)
    track = mapped_track(repo, topic, session)
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        first = sup.evaluate(track, act=True)
        second = sup.evaluate(track, act=True)
    assert first.status == "idle-with-context-left"
    assert second.status == "idle-with-context-left"
    assert "run /livespec-overseer:supervise-plan" in err.getvalue()
    assert err.getvalue().count("run /livespec-overseer:supervise-plan") == 1


def test_running_supervisor_without_handoff_offers_capture_once(tmp_path):
    """Fourth truth-table cell: supervision is live but lacks a durable prompt, so the
    operator gets a capture offer, not silence."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    supervisor_session = f"{session}-supervisor"
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))
    fake.serve(supervisor_session, repo, capture=idle_capture(ctx=73), cmd="node")
    sup = make_supervisor(tmp_path, fake)
    track = mapped_track(repo, topic, session)
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        first = sup.evaluate(track, act=True)
        second = sup.evaluate(track, act=True)
    assert first.status == "idle-with-context-left"
    assert second.status == "idle-with-context-left"
    assert "supervision is running but has no durable prompt" in err.getvalue()
    assert err.getvalue().count("supervision is running but has no durable prompt") == 1


def test_handoff_without_running_supervisor_offers_start_once(tmp_path):
    """Surface B: a durable supervisor prompt exists, but no live supervisor process is
    running, so the operator is offered the start action once."""
    repo, topic = make_plan(tmp_path)
    (repo / "plan" / topic / "supervisor-handoff.md").write_text("supervise this\n")
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path, fake)
    track = mapped_track(repo, topic, session)
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        first = sup.evaluate(track, act=True)
        second = sup.evaluate(track, act=True)
    assert first.status == "idle-with-context-left"
    assert second.status == "idle-with-context-left"
    assert f"start tmux session '{session}-supervisor'" in err.getvalue()
    assert err.getvalue().count("supervisor handoff exists") == 1


def test_dead_supervisor_tmux_name_still_offers_surface_b(tmp_path):
    """A tmux session named like a supervisor is insufficient; Surface B still fires
    unless live process evidence proves a supervisor is running."""
    repo, topic = make_plan(tmp_path)
    (repo / "plan" / topic / "supervisor-handoff.md").write_text("supervise this\n")
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))
    fake.serve(f"{session}-supervisor", repo, capture=idle_capture(ctx=73), cmd="zsh")
    sup = make_supervisor(tmp_path, fake)
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "idle-with-context-left"
    # The status alone proves nothing here: the silent-healthy cell renders the SAME
    # status. Assert the Surface B ALERT actually fired, or this sabotage check cannot
    # fail on the very defect it exists to catch (a dead supervisor's leftover tmux
    # session suppressing Surface B forever).
    assert f"start tmux session '{session}-supervisor'" in err.getvalue()
    assert err.getvalue().count("supervisor handoff exists") == 1


def test_track_without_live_matching_session_is_silent_about_supervision(tmp_path):
    """The supervision-artifact probe is liveness-gated: no live matching session means
    no Surface A or B alert even when the file exists."""
    repo, topic = make_plan(tmp_path)
    (repo / "plan" / topic / "supervisor-handoff.md").write_text("supervise this\n")
    fake = FakeTmux()
    sup = make_supervisor(tmp_path, fake)
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(mapped_track(repo, topic, registry.tmux_id(str(repo), topic)), act=True)
    assert view.status == "session-gone"
    assert "supervisor" not in err.getvalue()


def test_supervision_surfaces_do_not_preempt_blocked_or_danger(tmp_path):
    """The offer surfaces sit below existing NEEDS-YOU classes in the precedence
    cascade: blocked and danger keep their established statuses and alerts."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))
    declare(repo, topic, "blocked: needs a decision")
    sup = make_supervisor(tmp_path, fake)
    blocked = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert blocked.status == "blocked:human"

    other_repo, other_topic = make_plan(tmp_path, repo_name="other", topic="other")
    other_session = registry.tmux_id(str(other_repo), other_topic)
    fake.serve(other_session, other_repo, capture=idle_capture(ctx=15))
    danger = sup.evaluate(mapped_track(other_repo, other_topic, other_session), act=True)
    assert danger.status == "danger"


def test_handoff_and_running_supervisor_is_silent_healthy_cell(tmp_path):
    """When both the durable handoff and live supervisor exist, the supervision truth
    table is healthy and falls through to the ordinary idle classification."""
    repo, topic = make_plan(tmp_path)
    (repo / "plan" / topic / "supervisor-handoff.md").write_text("supervise this\n")
    session = registry.tmux_id(str(repo), topic)
    supervisor_session = f"{session}-supervisor"
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))
    fake.serve(supervisor_session, repo, capture=idle_capture(ctx=73), cmd="node")
    sup = make_supervisor(tmp_path, fake)
    track = mapped_track(repo, topic, session)
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track, act=True)
        listed = sup.evaluate(track, act=False)
    assert view.status == "idle-with-context-left"
    assert listed.status == "idle-with-context-left"
    assert "supervisor" not in err.getvalue()
