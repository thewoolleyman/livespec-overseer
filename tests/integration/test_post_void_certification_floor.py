"""Integration-tier scenario tests for v010 post-void ready certification."""

from __future__ import annotations

import io as _io

import _supervisor_config
import _supervisor_restart
import _supervisor_state
import registry
import signals

from overseer.test_supervisor_builders import (
    busy_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from overseer.test_supervisor_fakes import FakeTmux


def _round(*, tmp_path, ctx=40, topic="topic", now=1000.0):
    repo, topic = make_plan(tmp_path=tmp_path, topic=topic)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: now, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    opened = sup.evaluate(track=track, act=True)
    assert opened.status == "warned"
    return repo, topic, session, fake, sup, track


def _paste_count(*, fake: FakeTmux) -> int:
    return len(fake.paste_texts())


def _respawn_count(*, fake: FakeTmux) -> int:
    return len([call for call in fake.calls if call[0] == "respawn"])


def _void_ready(*, fixture, mtime=800.0):
    repo, topic, session, fake, sup, track = fixture
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=mtime)
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=40))
    view = sup.evaluate(track=track, act=True)
    assert view.status == "working"


def test_scenario_repeated_voiding_never_resends_an_already_notified_band(*, tmp_path):
    fixture = _round(tmp_path=tmp_path, ctx=40)
    repo, topic, session, fake, sup, track = fixture
    assert registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path) == [
        50,
        40,
    ]

    _void_ready(fixture=fixture)
    assert registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path) == [
        50,
        40,
    ]

    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup.evaluate(track=track, act=True)
    assert _paste_count(fake=fake) == 1


def test_scenario_a_round_whose_opening_wrapup_never_landed_is_unopened(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    fake.paste_ok = False
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "warned"
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )

    fake.paste_ok = True
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    assert sup.evaluate(track=track, act=True).status != "restarting"
    assert _respawn_count(fake=fake) == 0


def test_scenario_declaration_on_never_rounded_track_is_surfaced_not_healed(*, tmp_path):
    clock = {"t": 1000.0}
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=clock["t"])

    clock["t"] += _supervisor_config.CONDITION_CONTINUITY_GAP + 1
    view = sup.evaluate(track=track, act=True)

    assert view.status == "ready-uncertifiable"
    assert "no supervision round open" in (view.note or "")
    assert _paste_count(fake=fake) == 0
    assert _respawn_count(fake=fake) == 0


def test_scenario_standing_uncertifiable_declaration_does_not_suppress_threshold(*, tmp_path):
    clock = {"t": 1000.0}
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=clock["t"])
    clock["t"] += _supervisor_config.CONDITION_CONTINUITY_GAP + 1

    view = sup.evaluate(track=track, act=True)

    assert view.status == "ready-uncertifiable"
    assert "ready cannot certify" in (view.note or "")
    assert _paste_count(fake=fake) == 0


def test_scenario_pane_carrying_standing_declaration_is_never_pasted_into(*, tmp_path):
    fixture = _round(tmp_path=tmp_path, ctx=40)
    repo, topic, session, fake, sup, track = fixture
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=999.0)
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))

    sup.evaluate(track=track, act=True)

    assert _paste_count(fake=fake) == 1


def test_scenario_ready_after_void_certifies_without_a_new_round(*, tmp_path):
    fixture = _round(tmp_path=tmp_path, ctx=40)
    repo, topic, session, fake, sup, track = fixture
    _void_ready(fixture=fixture)
    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert record.voided_at is not None
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=record.voided_at + 1.0)
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))

    view = sup.evaluate(track=track, act=True)

    assert view.status == "restarting"
    assert _respawn_count(fake=fake) == 1
    assert _paste_count(fake=fake) == 2


def test_scenario_voided_declaration_never_certifies_against_its_own_void(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    identity = "claude:session:topic"
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=identity,
        stamp_path=tmp_path / "stamps.json",
    )
    registry.record_ready_void(
        repo=str(repo),
        topic=topic,
        ts=1121.0,
        floor_min=1121.0,
        stamp_path=tmp_path / "stamps.json",
    )
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    record = registry.read_round_record(
        repo=str(repo), topic=topic, stamp_path=tmp_path / "stamps.json"
    )

    assert (
        signals.ready_valid(
            repo=str(repo),
            topic=topic,
            certification_floor=record.certification_floor,
            round_session_identity=record.session_identity,
            live_session_identity=identity,
        )
        is False
    )


def test_scenario_ready_on_never_rounded_track_certifies_nothing(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    assert (
        signals.ready_valid(
            repo=str(repo),
            topic=topic,
            certification_floor=None,
            round_session_identity=None,
            live_session_identity="claude:s:t",
        )
        is False
    )


def test_scenario_successor_never_certifies_against_predecessor_floor(*, tmp_path):
    fixture = _round(tmp_path=tmp_path, ctx=40)
    repo, topic, session, fake, sup, track = fixture
    _void_ready(fixture=fixture)
    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    ready_mtime = (record.voided_at or 1000.0) + 1
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=ready_mtime)
    sup.now = lambda: ready_mtime + _supervisor_config.CONDITION_CONTINUITY_GAP + 1
    sup.claude_identity_by_session[(session, topic)] = "claude:successor"
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))

    view = sup.evaluate(track=track, act=True)

    assert view.status == "ready-uncertifiable"
    assert "identity differs" in (view.note or "")
    assert _respawn_count(fake=fake) == 0


def test_scenario_session_replaced_before_void_never_inherits_certifiable_floor(*, tmp_path):
    fixture = _round(tmp_path=tmp_path, ctx=40)
    repo, topic, session, fake, sup, track = fixture
    sup.claude_identity_by_session[(session, topic)] = "claude:successor"
    _void_ready(fixture=fixture)
    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)

    assert record.voided_at is None


def test_scenario_undeterminable_session_identity_fails_interlock_closed(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)

    assert (
        signals.ready_valid(
            repo=str(repo),
            topic=topic,
            certification_floor=1000.0,
            round_session_identity="codex:session-a",
            live_session_identity=None,
        )
        is False
    )


def test_uncertifiable_ready_at_danger_keeps_danger_status(*, tmp_path):
    clock = {"t": 1000.0}
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=20))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=clock["t"])
    clock["t"] += _supervisor_config.CONDITION_CONTINUITY_GAP + 1

    view = sup.evaluate(track=track, act=True)

    assert view.status == "danger"
    assert "ready cannot certify" in (view.note or "")
    assert _paste_count(fake=fake) == 0


def test_round_open_without_determinable_identity_alerts_and_does_not_paste(*, tmp_path, capsys):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    _supervisor_restart.maybe_inject(
        sup=sup, track=track, target=session, eff_ctx=40, threshold=40, is_codex=True
    )

    assert _paste_count(fake=fake) == 0
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )
    assert "session identity could not be determined" in capsys.readouterr().err


def test_ready_void_floor_record_exception_still_deletes_state(*, tmp_path, monkeypatch, capsys):
    fixture = _round(tmp_path=tmp_path, ctx=40)
    repo, topic, session, fake, sup, track = fixture
    marker = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=800.0)
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=40))

    def fail_record_ready_void(**_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(_supervisor_state.registry, "record_ready_void", fail_record_ready_void)

    view = sup.evaluate(track=track, act=True)

    assert view.status == "working"
    assert not marker.exists()
    assert "could not record ready void" in capsys.readouterr().err


def test_ready_void_surfaces_when_floor_and_delete_both_fail(*, tmp_path, monkeypatch, capsys):
    fixture = _round(tmp_path=tmp_path, ctx=40)
    repo, topic, session, fake, sup, track = fixture
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=800.0)
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=40))

    monkeypatch.setattr(_supervisor_state, "_record_ready_void", lambda **_kwargs: False)
    monkeypatch.setattr(_supervisor_state, "delete_state_file", lambda **_kwargs: False)

    view = sup.evaluate(track=track, act=True)

    assert view.status == "working"
    assert "ready void failed to record its floor AND delete" in capsys.readouterr().err
