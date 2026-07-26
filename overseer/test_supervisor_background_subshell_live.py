"""Beside-tests for supervisor.py — background subshell live.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import pytest
import registry
import supervisor
from test_supervisor_builders import (
    arm_ready_marker,
    busy_capture,
    idle_capture,
    key_for,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_bg_shell_at_danger_is_working_and_never_restarted(tmp_path):
    """A session deep in the danger band whose pane LOOKS idle, but which has a live
    background shell (a `Bash(run_in_background)` build/test still running), reads
    `working` — never `danger`, never restarted. This is the concrete case proving why
    the daemon may not equate "idle + settled" with "safe to kill": the pane text is
    indistinguishable from idle, yet real work is in flight."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=13)
    )  # idle-LOOKING, deep in danger
    fake.pane_pid_map[session] = 100
    children = {100: [200], 200: [300]}
    comms = {200: "node", 300: "bash"}  # a LIVE background shell under the pane process
    sup = make_supervisor(
        tmp_path, fake, children_of=lambda pid: children.get(pid, []), comm_of=comms.get
    )
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "working"  # bg shell ⇒ busy; the danger branch is never reached
    assert view.note == "background shell"
    assert not fake.has(method="respawn")  # the live background work was NOT killed


def test_bg_shell_sets_background_shell_note(tmp_path):
    """When a bg shell is the SOLE reason a pane isn't idle (pane text is idle, no
    blocked marker), the `working` row carries the note `background shell`."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=73)
    )  # idle, high ctx (no inject)
    fake.pane_pid_map[session] = 100
    children = {100: [200]}
    comms = {200: "bash"}  # a bg-command shell directly under the pane process
    sup = make_supervisor(
        tmp_path,
        fake,
        children_of=lambda pid: children.get(pid, []),
        comm_of=comms.get,
    )
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "working"
    assert view.note == "background shell"


def test_textually_busy_pane_has_no_background_shell_note(tmp_path):
    """The note is `background shell` ONLY when a bg shell is the SOLE reason. A
    TEXTUALLY busy pane (spinner) is `working` with NO note, even when a descendant
    shell is also present — the note guard is `bg_shell and not is_busy(capture)`."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=40))  # actively generating
    fake.pane_pid_map[session] = 100
    children = {100: [200]}
    comms = {200: "zsh"}
    sup = make_supervisor(
        tmp_path,
        fake,
        children_of=lambda pid: children.get(pid, []),
        comm_of=comms.get,
    )
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "working"
    assert view.note is None


def test_fresh_marker_survives_busy_certifying_tail(tmp_path):
    """RB1: a YOUNG ready marker (age < grace) seen busy is the certifying turn's
    OWN tail (final streaming + stop hooks) — it must NOT be voided, else the
    restart never fires. now()=1000, stamp=990, marker mtime=995 → age 5s < grace."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture="esc to interrupt\n  Ctx: 30% left\n"
    )  # busy tail
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(repo=str(repo), topic=topic, ts=990.0, stamp_path=sup.stamp_path)
    marker = arm_ready_marker(repo, topic, mtime=995.0)

    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "working"
    assert marker.exists()  # NOT voided — it is the certifying tail
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 990.0
    )


def test_stale_marker_voided_when_busy_past_grace(tmp_path):
    """RB1/B4: an OLD ready marker (age > grace) seen busy means the session
    genuinely resumed work after certifying — void it durably (marker + stamp +
    inject state). now()=1000, stamp=700, marker mtime=800 → age 200s > grace."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture="esc to interrupt\n  Ctx: 30% left\n"
    )  # busy again
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(repo=str(repo), topic=topic, ts=700.0, stamp_path=sup.stamp_path)
    marker = arm_ready_marker(repo, topic, mtime=800.0)

    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "working"
    assert not marker.exists()  # certification voided (stale)
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )


def test_void_resets_inject_state_so_round_can_recertify(tmp_path):
    """RB2: after a void, the in-memory inject state is popped AND the durable stamp
    + notified bands are cleared, so the NEXT threshold crossing opens a fresh round
    that writes a new stamp — else the wedged round would never re-certify."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path, fake)
    track = mapped_track(repo, topic, session)
    # Round 1: inject (stamp written, a band recorded) on an idle low-ctx pane.
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup.evaluate(track=track, act=True)
    assert key_for(repo, topic) in sup.inject  # in-memory last_ctx tracked
    assert registry.read_notified_bands(
        repo=str(repo), topic=topic, stamp_path=sup.stamp_path
    )  # a band recorded
    # Session resumes work with a STALE marker → void (age > grace) → state popped.
    registry.write_injection_stamp(repo=str(repo), topic=topic, ts=700.0, stamp_path=sup.stamp_path)
    arm_ready_marker(repo, topic, mtime=800.0)
    fake.panes[session] = "esc to interrupt\n  Ctx: 30% left\n"  # busy
    sup.evaluate(track=track, act=True)
    assert key_for(repo, topic) not in sup.inject  # inject state popped
    # Next idle low-ctx tick opens a FRESH round: new stamp written, re-injected.
    fake.panes[session] = idle_capture(ctx=35)
    sup.evaluate(track=track, act=True)
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 1000.0
    )


def test_no_restart_when_not_idle(tmp_path):
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture="stale scrollback with no prompt box\n"
    )  # not idle, not busy
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo, topic, mtime=1001.0)

    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "settling"
    assert not fake.has(method="respawn")


def test_restart_keeps_marker_when_respawn_fails(tmp_path):
    """B5: a failed respawn must NOT delete the ready marker — the certification
    is preserved so the restart retries, never silently destroyed."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    fake.respawn_ok = False  # respawn fails
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    marker = arm_ready_marker(repo, topic, mtime=1001.0)

    sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert marker.exists()  # certification preserved
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 1000.0
    )
    # and the resume line was NOT pasted (we bailed before submit)
    assert supervisor.default_resume(repo=str(repo), topic=topic) not in fake.paste_texts()


def test_renamed_session_is_idle_and_restarts(tmp_path):
    """B2: a session showing the `-n <topic>` TITLED top border is still detected
    as idle, so injection/restart keep working after the first rename (else every
    daemon-launched session becomes permanently unmanageable)."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=30, topic=topic)
    )  # titled border
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo, topic, mtime=1001.0)
    view = sup.evaluate(track=mapped_track(repo, topic, session), act=True)
    assert view.status == "restarting"
