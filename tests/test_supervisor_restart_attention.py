"""Repo-level coverage for post-respawn restart attention."""

import contextlib
import io as _io
import json
from pathlib import Path

import registry
import signals
import supervisor
from test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    render_of,
)
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


def test_restarted_never_worked_session_is_report_only_attention(*, tmp_path):
    """The ratified scenario: report the stranded fresh composer, authorize no act."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    resume = supervisor.default_resume(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=_capture_with_resume(resume=resume, ctx=100))
    clock = {"now": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["now"], own_pane="%7")
    _record_post_respawn(sup=sup, repo=str(repo), topic=topic, resume=resume)
    track = mapped_track(repo=repo, topic=topic, session=session)

    first = sup.evaluate(track=track, act=True)
    assert first.status == "settling"
    assert supervisor.needs_attention(row=first) is False
    clock["now"] += 61.0

    with contextlib.redirect_stderr(_io.StringIO()):
        due = sup.evaluate(track=track, act=True)
    assert due.status == "restart-never-worked"
    assert "fresh session has not consumed context" in (due.note or "")
    assert supervisor.needs_attention(row=due) is True
    sup._refresh_window_name(attention=int(supervisor.needs_attention(row=due)))
    assert fake.window_name == "overseer(1!)"
    assert "tmux switch-client -t" in render_of(sup=sup, views=[due])
    assert not fake.has(method="respawn")
    assert not any(call[0] == "keys" for call in fake.calls)
    assert signals.read_state(repo=str(repo), topic=topic) is None

    fake.panes[session] = idle_capture(ctx=99)
    cleared = sup.evaluate(track=track, act=True)
    assert supervisor.needs_attention(row=cleared) is False
    sup._refresh_window_name(attention=int(supervisor.needs_attention(row=cleared)))
    assert fake.window_name == "overseer"


def test_restarted_never_worked_survives_missing_resume_pending_marker(*, tmp_path):
    """A falsely-closed round must still surface a stranded fresh composer."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    resume = supervisor.default_resume(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=_capture_with_resume(resume=resume, ctx=100))
    clock = {"now": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["now"], own_pane="%7")
    _record_post_respawn(sup=sup, repo=str(repo), topic=topic, resume=resume)
    registry.clear_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    track = mapped_track(repo=repo, topic=topic, session=session)

    first = sup.evaluate(track=track, act=True)
    assert first.status == "settling"
    clock["now"] += 61.0

    with contextlib.redirect_stderr(_io.StringIO()):
        due = sup.evaluate(track=track, act=True)
    assert due.status == "restart-never-worked"
    assert supervisor.needs_attention(row=due) is True
    assert not fake.has(method="respawn")
    assert not any(call[0] == "keys" for call in fake.calls)
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is False
    )
