"""Repo-level attention membership regressions for liveness report statuses."""

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import _supervisor_records
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


def test_daemon_bounce_re_resolves_stall_watch_by_title_not_prior_pane_id(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
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
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=73))
    fake.pane_titles = {topic: "%new"}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        status_path=status_path,
    )
    state = sup.inject.setdefault(
        key_for(repo=repo, topic=topic), _supervisor_records.InjectState()
    )
    state.stall_watch_daemon_instance_id = "daemon-before-bounce"
    state.stall_watch_pane = "%old"

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "working"
    assert ("pane_by_title", session, topic) in fake.calls
    assert state.stall_watch_pane == "%new"
    assert state.stall_watch_daemon_instance_id == "daemon-after-bounce"


def test_daemon_bounce_failed_title_resolution_reports_without_restart(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
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
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, status_path=status_path)
    state = sup.inject.setdefault(
        key_for(repo=repo, topic=topic), _supervisor_records.InjectState()
    )
    state.stall_watch_daemon_instance_id = "daemon-before-bounce"
    state.stall_watch_pane = "%old"

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "watch-target-gone"
    assert "re-resolve by pane title failed" in (view.note or "")
    assert "stall watch target missing" in err.getvalue()
    assert not fake.has(method="respawn")


def test_daemon_bounce_failed_title_resolution_read_only_does_not_alert(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
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
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, status_path=status_path)
    state = sup.inject.setdefault(
        key_for(repo=repo, topic=topic), _supervisor_records.InjectState()
    )
    state.stall_watch_daemon_instance_id = "daemon-before-bounce"
    state.stall_watch_pane = "%old"

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)

    assert view.status == "watch-target-gone"
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
