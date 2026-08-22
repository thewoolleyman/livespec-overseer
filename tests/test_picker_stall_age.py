import contextlib
import io as _io

import _supervisor_config
import registry
import signals
from test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    write_fresh_supervisor_state,
)
from test_supervisor_fakes import FakeTmux
from test_supervisor_liveness_starvation import picker_capture

__all__: list[str] = []


def test_picker_stall_reaches_threshold_across_incidental_redraws(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "PICKER_STALL_AFTER", 30.0)
    repo, worker_topic = make_plan(tmp_path=tmp_path)
    topic = signals.supervisor_entity_topic(topic=worker_topic)
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)
    write_fresh_supervisor_state(repo=repo, topic=topic)

    with contextlib.redirect_stderr(_io.StringIO()):
        assert sup.evaluate(track=track, act=True).status == "blocked:human"
        for redraw in range(1, 4):
            clock["t"] += 10.0
            fake.panes[session] = picker_capture() + f"redraw {redraw}\n"
            stalled = sup.evaluate(track=track, act=True)

    assert stalled.status == "picker-stalled"
    assert stalled.stall_seconds == 30
    assert len(fake.paste_texts()) == 1
    assert not any(call[0] == "keys" and call[2] in {"Enter", "1", "2"} for call in fake.calls)


def test_picker_stall_clock_resets_when_picker_closes(*, tmp_path, monkeypatch):
    monkeypatch.setattr(_supervisor_config, "PICKER_STALL_AFTER", 30.0)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=picker_capture())
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "blocked:human"
    clock["t"] += 40.0
    assert sup.evaluate(track=track, act=True).status == "picker-stalled"
    fake.panes[session] = idle_capture(ctx=80)
    clock["t"] += 1.0
    closed = sup.evaluate(track=track, act=True)
    assert closed.picker_open is False
    assert closed.stall_seconds == 0
    fake.panes[session] = picker_capture()
    clock["t"] += 1.0
    reopened = sup.evaluate(track=track, act=True)

    assert reopened.status == "blocked:human"
    assert reopened.stall_seconds == 0
