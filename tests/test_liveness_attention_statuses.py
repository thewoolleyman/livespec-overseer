"""Repo-level attention membership regressions for liveness report statuses."""

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import _supervisor_records
import _supervisor_stall_watch
import registry
import supervisor
from test_supervisor_builders import busy_capture, key_for, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux


def test_winddown_starved_needs_attention():
    row = supervisor.RowView(topic="t", repo="/r", tmux="s", ctx=40, status="winddown-starved")
    assert supervisor.needs_attention(row=row) is True


def test_shell_prolonged_needs_attention():
    row = supervisor.RowView(topic="t", repo="/r", tmux="s", ctx=73, status="shell-prolonged")
    assert supervisor.needs_attention(row=row) is True


def test_pane_still_needs_attention():
    row = supervisor.RowView(topic="t", repo="/r", tmux="s", ctx=73, status="pane-still")
    assert supervisor.needs_attention(row=row) is True


def test_watch_target_gone_needs_attention():
    row = supervisor.RowView(topic="t", repo="/r", tmux="s", ctx=73, status="watch-target-gone")
    assert supervisor.needs_attention(row=row) is True


def test_working_pane_still_alert_requires_two_consecutive_due_observations(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "working"
    pane_still_after = 30.0 * 60.0
    clock["t"] += pane_still_after + 1.0

    first_due = sup.evaluate(track=track, act=True)
    assert first_due.status == "working"
    assert first_due.note is None

    second_due = sup.evaluate(track=track, act=True)
    assert second_due.status == "pane-still"
    assert "unchanged" in (second_due.note or "")
    assert not fake.has(method="respawn")


def test_stall_watch_without_snapshot_path_uses_current_daemon_identity(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, status_path=None)
    sup.status_snapshot_writer = lambda *, sup, rows: None
    state = sup.inject.setdefault(
        key_for(repo=repo, topic=topic), _supervisor_records.InjectState()
    )
    state.stall_watch_daemon_instance_id = None

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "working"
    assert state.stall_watch_daemon_instance_id == sup.daemon_instance_id


def _status_snapshot_after_bounce(*, tmp_path):
    status_path = tmp_path / "status.json"
    status_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "daemon_instance_id": "daemon-after-bounce",
                "tick_generation": 2,
                "written_at": "2026-08-18T20:00:00Z",
                "rows": [],
            }
        ),
        encoding="utf-8",
    )
    return status_path


def _mark_stall_watch_before_bounce(*, sup, repo, topic):
    state = sup.inject.setdefault(
        key_for(repo=repo, topic=topic), _supervisor_records.InjectState()
    )
    state.stall_watch_daemon_instance_id = "daemon-before-bounce"
    state.stall_watch_pane = "%old"
    return state


def test_daemon_bounce_re_resolves_glyph_prefixed_title_by_session_identity(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
    status_path = _status_snapshot_after_bounce(tmp_path=tmp_path)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=73))
    fake.pane_titles = {f"activity-frame {topic}": session}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        status_path=status_path,
    )
    state = _mark_stall_watch_before_bounce(sup=sup, repo=repo, topic=topic)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "working"
    assert not any(call[0] == "pane_by_title" for call in fake.calls)
    assert state.stall_watch_pane == session
    assert state.stall_watch_daemon_instance_id == "daemon-after-bounce"


def test_daemon_bounce_re_resolves_drifted_title_by_session_identity(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
    status_path = _status_snapshot_after_bounce(tmp_path=tmp_path)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=73))
    fake.pane_titles = {"reviewing a failing test unrelated to the topic": session}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, status_path=status_path)
    state = _mark_stall_watch_before_bounce(sup=sup, repo=repo, topic=topic)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "working"
    assert not any(call[0] == "pane_by_title" for call in fake.calls)
    assert state.stall_watch_pane == session
    assert state.stall_watch_daemon_instance_id == "daemon-after-bounce"


def _stall_watch_observation(*, state):
    return _supervisor_records.Observation(
        capture=busy_capture(ctx=73),
        busy=True,
        gate=False,
        idle=False,
        is_codex=False,
        runtime="claude",
        codex_fallback=False,
        claude_status="busy",
        current_ctx=73,
        eff_ctx=73,
        ctx_stale_age=None,
        stale_ctx=None,
        injection_stamp=None,
        round_record=registry.RoundRecord(
            at=None,
            bands=[],
            expired_at=None,
            session_identity=None,
            malformed_reason=None,
        ),
        session_identity="claude:session:topic",
        ready_uncertifiable_reason=None,
        istate=state,
        observed_at=1000.0,
        declared=None,
        malformed=False,
        blocked=None,
        acked=False,
        ready=False,
    )


def test_daemon_bounce_missing_session_identity_pane_still_reports_target_gone(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
    status_path = _status_snapshot_after_bounce(tmp_path=tmp_path)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, status_path=status_path)
    state = _supervisor_records.InjectState()
    state.stall_watch_daemon_instance_id = "daemon-before-bounce"
    state.stall_watch_pane = "%old"
    obs = _stall_watch_observation(state=state)

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        result = _supervisor_stall_watch.apply_stall_watch(
            request=_supervisor_stall_watch.StallWatchRequest(
                sup=sup,
                track=mapped_track(repo=repo, topic=topic, session=session),
                session=session,
                pane="%old",
                status="working",
                note=None,
                obs=obs,
                active_conditions=set(),
                act=True,
            )
        )

    assert result.status == "watch-target-gone"
    assert "re-resolve by tmux session identity failed" in (result.note or "")
    assert "stall watch target missing" in err.getvalue()
    assert not fake.has(method="respawn")


def test_daemon_bounce_missing_session_identity_read_only_does_not_alert(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
    status_path = _status_snapshot_after_bounce(tmp_path=tmp_path)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, status_path=status_path)
    state = _supervisor_records.InjectState()
    state.stall_watch_daemon_instance_id = "daemon-before-bounce"
    state.stall_watch_pane = "%old"
    obs = _stall_watch_observation(state=state)

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        result = _supervisor_stall_watch.apply_stall_watch(
            request=_supervisor_stall_watch.StallWatchRequest(
                sup=sup,
                track=mapped_track(repo=repo, topic=topic, session=session),
                session=session,
                pane="%old",
                status="working",
                note=None,
                obs=obs,
                active_conditions=set(),
                act=False,
            )
        )

    assert result.status == "watch-target-gone"
    assert "overseer[SURFACE]" not in err.getvalue()


def test_pane_still_read_only_reports_without_alerting(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    clock["t"] += 30.0 * 60.0 + 1.0
    assert sup.evaluate(track=track, act=False).status == "working"

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=False)

    assert view.status == "pane-still"
    assert "overseer[SURFACE]" not in err.getvalue()


def test_same_daemon_watch_state_without_pane_reuses_current_target(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    state = sup.inject.setdefault(
        key_for(repo=repo, topic=topic), _supervisor_records.InjectState()
    )
    state.stall_watch_daemon_instance_id = sup.daemon_instance_id
    state.stall_watch_pane = None

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "working"
    assert state.stall_watch_pane == session
