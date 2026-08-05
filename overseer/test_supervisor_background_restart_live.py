"""Beside-tests for supervisor.py — restart certification under live background checks."""

import registry
import supervisor
from test_supervisor_builders import (
    arm_ready_marker,
    idle_capture,
    key_for,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_fresh_marker_survives_busy_certifying_tail(*, tmp_path):
    """RB1: a YOUNG ready marker (age < grace) seen busy is the certifying turn's
    OWN tail (final streaming + stop hooks) — it must NOT be voided, else the
    restart never fires. now()=1000, stamp=990, marker mtime=995 → age 5s < grace."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture="esc to interrupt\n  Ctx: 30% left\n"
    )  # busy tail
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(repo=str(repo), topic=topic, ts=990.0, stamp_path=sup.stamp_path)
    marker = arm_ready_marker(repo=repo, topic=topic, mtime=995.0)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "working"
    assert marker.exists()  # NOT voided — it is the certifying tail
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 990.0
    )


def test_stale_marker_voided_when_busy_past_grace(*, tmp_path):
    """An OLD ready marker (age > grace) seen busy means the session genuinely
    resumed work after certifying — void the declaration but keep the round open."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture="esc to interrupt\n  Ctx: 30% left\n"
    )  # busy again
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(repo=str(repo), topic=topic, ts=700.0, stamp_path=sup.stamp_path)
    marker = arm_ready_marker(repo=repo, topic=topic, mtime=800.0)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "working"
    assert not marker.exists()  # certification voided (stale)
    assert registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)


def test_void_resets_inject_state_so_round_can_recertify(*, tmp_path):
    """After a ready void, the in-memory state and durable notified bands survive."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    # Round 1: inject (stamp written, a band recorded) on an idle low-ctx pane.
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup.claude_status_by_session = {session: "idle"}
    sup.evaluate(track=track, act=True)
    assert key_for(repo=repo, topic=topic) in sup.inject  # in-memory last_ctx tracked
    assert registry.read_notified_bands(
        repo=str(repo), topic=topic, stamp_path=sup.stamp_path
    )  # a band recorded
    # Session resumes work with a STALE marker → declaration voided, round preserved.
    registry.write_injection_stamp(repo=str(repo), topic=topic, ts=700.0, stamp_path=sup.stamp_path)
    arm_ready_marker(repo=repo, topic=topic, mtime=800.0)
    fake.panes[session] = "esc to interrupt\n  Ctx: 30% left\n"  # busy
    sup.evaluate(track=track, act=True)
    assert key_for(repo=repo, topic=topic) in sup.inject
    # Next idle low-ctx tick sees no due band from the still-open round.
    fake.panes[session] = idle_capture(ctx=35)
    sup.claude_status_by_session = {session: "idle"}
    sup.evaluate(track=track, act=True)
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 700.0
    )


def test_no_restart_when_not_idle(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture="stale scrollback with no prompt box\n"
    )  # not idle, not busy
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "settling"
    assert not fake.has(method="respawn")


def test_restart_keeps_marker_when_respawn_fails(*, tmp_path):
    """B5: a failed respawn must NOT delete the ready marker — the certification
    is preserved so the restart retries, never silently destroyed."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    fake.respawn_ok = False  # respawn fails
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    marker = arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert marker.exists()  # certification preserved
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 1000.0
    )
    # and the resume line was NOT pasted (we bailed before submit)
    assert supervisor.default_resume(repo=str(repo), topic=topic) not in fake.paste_texts()


def test_renamed_session_is_idle_and_restarts(*, tmp_path):
    """B2: a session showing the `-n <topic>` TITLED top border is still detected
    as idle, so injection/restart keep working after the first rename (else every
    daemon-launched session becomes permanently unmanageable)."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=30, topic=topic)
    )  # titled border
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "restarting"
