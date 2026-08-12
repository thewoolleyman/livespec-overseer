"""Edge coverage for post-respawn restart attention."""

import contextlib
import io as _io
import json
from pathlib import Path

import _supervisor_view
import registry
import signals
import supervisor
from test_supervisor_builders import arm_ready_marker, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _capture_with_resume(*, resume: str, ctx: int) -> str:
    return (
        "● welcome\n"
        "────────────────────────────────────────\n"
        f"❯ {resume}\n"
        "────────────────────────────────────────\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
        "  ⏵⏵ bypass permissions on\n"
    )


def _record_post_respawn(*, sup: supervisor.Supervisor, repo: str, topic: str, resume: str) -> None:
    registry.write_injection_stamp(repo=repo, topic=topic, ts=900.0, stamp_path=sup.stamp_path)
    stamp_path = Path(sup.stamp_path)
    stamp_data = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp_entry = next(iter(stamp_data.values()))
    stamp_entry["post_respawn"] = {"ctx": 100, "resume": resume}
    stamp_path.write_text(json.dumps(stamp_data), encoding="utf-8")


def test_restart_never_worked_read_only_evaluation_reports_without_alerting(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    resume = supervisor.default_resume(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=_capture_with_resume(resume=resume, ctx=100))
    clock = {"now": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["now"], own_pane="%7")
    _record_post_respawn(sup=sup, repo=str(repo), topic=topic, resume=resume)

    first = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)
    assert first.status == "settling"
    clock["now"] += 61.0

    due = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)
    assert due.status == "restart-never-worked"
    assert supervisor.needs_attention(row=due) is True
    assert sup.alerted == {}


def test_resume_retry_re_evaluates_restart_never_worked_without_suppressing_retry(*, tmp_path):
    """A resume-pending tick still owns the act, but it must not preserve stale attention."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    resume = supervisor.default_resume(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=_capture_with_resume(resume=resume, ctx=100))
    clock = {"now": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["now"], own_pane="%7")
    _record_post_respawn(sup=sup, repo=str(repo), topic=topic, resume=resume)
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "settling"
    clock["now"] += 61.0
    assert sup.evaluate(track=track, act=True).status == "restart-never-worked"

    registry.set_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    fake.panes[session] = _capture_with_resume(resume="changed composer", ctx=100)
    retry = sup.evaluate(track=track, act=True)
    assert retry.status == "restarting"
    assert retry.note == _supervisor_view.RESUME_PENDING_NOTE
    assert any(call[0] == "keys" and call[2] == "Enter" for call in fake.calls)
    assert not fake.has(method="respawn")

    stamp_path = Path(sup.stamp_path)
    stamp_data = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp_entry = next(iter(stamp_data.values()))
    stamp_entry.pop("resume_pending", None)
    stamp_path.write_text(json.dumps(stamp_data), encoding="utf-8")

    fake.panes[session] = _capture_with_resume(resume=resume, ctx=100)
    rearmed = sup.evaluate(track=track, act=True)
    assert rearmed.status == "settling"


def test_due_restart_never_worked_attention_does_not_retry_or_clear_round(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    resume = supervisor.default_resume(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=_capture_with_resume(resume=resume, ctx=100))
    clock = {"now": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["now"], own_pane="%7")
    _record_post_respawn(sup=sup, repo=str(repo), topic=topic, resume=resume)
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "settling"
    registry.set_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    fake.calls.clear()
    clock["now"] += 61.0

    with contextlib.redirect_stderr(_io.StringIO()):
        due = sup.evaluate(track=track, act=True)
    assert due.status == "restart-never-worked"
    assert supervisor.needs_attention(row=due) is True
    assert not any(call[0] == "keys" for call in fake.calls)
    assert not fake.has(method="respawn")
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_READY
    assert registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)


def test_restart_never_worked_attention_clears_on_busy_and_rearms(*, tmp_path):
    """Busy evidence ends the episode even when the resume text and context still match."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    resume = supervisor.default_resume(repo=str(repo), topic=topic)
    stuck_capture = _capture_with_resume(resume=resume, ctx=100)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=stuck_capture)
    clock = {"now": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["now"])
    _record_post_respawn(sup=sup, repo=str(repo), topic=topic, resume=resume)
    track = mapped_track(repo=repo, topic=topic, session=session)
    log = _io.StringIO()

    with contextlib.redirect_stderr(log):
        initial = sup.evaluate(track=track, act=True)
        clock["now"] = 1061.0
        first = sup.evaluate(track=track, act=True)
        repeated = sup.evaluate(track=track, act=True)
        fake.panes[session] = "esc to interrupt\n" + stuck_capture
        busy = sup.evaluate(track=track, act=True)
        fake.panes[session] = stuck_capture
        reset = sup.evaluate(track=track, act=True)
        clock["now"] = 1122.0
        second = sup.evaluate(track=track, act=True)

    assert [initial.status, first.status, repeated.status] == [
        "settling",
        "restart-never-worked",
        "restart-never-worked",
    ]
    assert [busy.status, reset.status, second.status] == [
        "working",
        "settling",
        "restart-never-worked",
    ]
    assert log.getvalue().count("fresh session has not begun work after restart") == 2
