import _supervisor_records
import _supervisor_snapshot
import registry
from test_supervisor_builders import make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux
from test_supervisor_liveness_starvation import picker_capture

__all__: list[str] = []


def test_progressing_stale_picker_transcript_does_not_publish_blocked_human(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture(ctx=80))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)
    sup.inject[(str(repo), topic)] = _supervisor_records.InjectState(last_ctx=80)

    fake.panes[session] = picker_capture(ctx=79)
    row = sup.evaluate(track=track, act=True)
    payload = _supervisor_snapshot.row_payload(sup=sup, row=row)

    assert row.status == "working"
    assert payload["status"] == "working"
    assert payload["progress_now"] is True


def test_genuine_human_picker_still_publishes_blocked_human(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture(ctx=80))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)

    row = sup.evaluate(track=track, act=True)

    assert row.status == "blocked:human"
    assert row.picker_open is True
    assert row.stall_seconds == 0


def test_progressing_stale_picker_snapshot_does_not_publish_zero_stall_pair(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture(ctx=80))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)
    sup.inject[(str(repo), topic)] = _supervisor_records.InjectState(last_ctx=80)

    fake.panes[session] = picker_capture(ctx=79)
    payload = _supervisor_snapshot.row_payload(sup=sup, row=sup.evaluate(track=track, act=True))

    assert not (payload["stall_seconds"] == 0 and payload["progress_now"] is False)
