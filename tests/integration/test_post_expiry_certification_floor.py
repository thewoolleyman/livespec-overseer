"""Integration-tier scenario tests for v016 post-expiry ready certification."""

from __future__ import annotations

import io as _io

import _supervisor_config
import _supervisor_restart
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


def _busy_after_ready(*, fixture, mtime=1001.0):
    repo, topic, session, fake, sup, track = fixture
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=mtime)
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=40))
    view = sup.evaluate(track=track, act=True)
    assert view.status == "working"


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
    marker = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=clock["t"])

    # Past the maximum age too: a round-less declaration has no round to expire
    # within, so it is neither expired nor healed — only surfaced, for as long as
    # it stands.
    clock["t"] += _supervisor_config.READY_ARM_MAX_AGE + 1
    view = sup.evaluate(track=track, act=True)

    assert view.status == "ready-uncertifiable"
    assert "no supervision round open" in (view.note or "")
    assert marker.exists()
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


def test_scenario_ready_after_expiry_certifies_without_a_new_round(*, tmp_path):
    """A declaration written AFTER the recorded expiry instant certifies in the same
    round: the expiry raised the floor, it did not close the round."""
    clock = {"t": 1000.0}
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    assert sup.evaluate(track=track, act=True).status == "warned"

    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    clock["t"] = 1001.0 + _supervisor_config.READY_ARM_MAX_AGE + 1.0
    assert sup.evaluate(track=track, act=True).status == "ready-uncertifiable"
    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    expiry_instant = 1001.0 + _supervisor_config.READY_ARM_MAX_AGE
    assert record.expired_at == expiry_instant
    assert record.at == 1000.0

    clock["t"] = expiry_instant + 10.0
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=expiry_instant + 5.0)
    view = sup.evaluate(track=track, act=True)

    assert view.status == "restarting"
    assert _respawn_count(fake=fake) == 1
    # The opening wrap-up and the restart's own resume prompt — no SECOND wrap-up was
    # required to authorize the restart.
    assert _paste_count(fake=fake) == 2


def test_scenario_expired_declaration_never_certifies_against_its_own_expiry(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    identity = "claude:session:topic"
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=identity,
        stamp_path=tmp_path / "stamps.json",
    )
    registry.record_ready_expiry(
        repo=str(repo),
        topic=topic,
        expiry_instant=1001.0 + _supervisor_config.READY_ARM_MAX_AGE,
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


def test_scenario_an_aged_declaration_never_certifies_before_its_expiry_is_recorded(*, tmp_path):
    """Precondition 3's fail-closed age backstop.

    An idle, settled, correctly identified pane satisfies every OTHER precondition in
    the same observation that first sees the declaration past its maximum age — and in
    that observation the round's sidecar carries no expiry yet. The declaration must
    still fail the interlock, on its own age.
    """
    clock = {"t": 1000.0}
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    assert sup.evaluate(track=track, act=True).status == "warned"

    marker = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    clock["t"] = 1001.0 + _supervisor_config.READY_ARM_MAX_AGE + 1.0

    # The read-only evaluation records and deletes nothing, so this is the interlock
    # judged with NO expiry in the sidecar and the declaration still on disk.
    read_only = sup.evaluate(track=track, act=False)
    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)

    assert read_only.status == "ready-uncertifiable"
    assert "ready declaration exceeded 30m max age" in (read_only.note or "")
    assert record.expired_at is None
    assert marker.exists()
    assert _respawn_count(fake=fake) == 0

    acted = sup.evaluate(track=track, act=True)
    recorded = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)

    assert acted.status == "ready-uncertifiable"
    assert _respawn_count(fake=fake) == 0
    assert recorded.expired_at == 1001.0 + _supervisor_config.READY_ARM_MAX_AGE


def test_expiry_deletes_the_declaration_and_records_a_deterministic_instant(*, tmp_path):
    """The recorded instant is `mtime + maximum age` — computed from the declaration's
    own modification time, never from a second clock reading at processing time."""
    clock = {"t": 1000.0}
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    assert sup.evaluate(track=track, act=True).status == "warned"
    bands = registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)

    marker = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    clock["t"] = 1001.0 + _supervisor_config.READY_ARM_MAX_AGE + 500.0
    sup.evaluate(track=track, act=True)

    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert not marker.exists()
    assert record.expired_at == 1001.0 + _supervisor_config.READY_ARM_MAX_AGE
    assert record.at == 1000.0
    assert (
        registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == bands
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


def test_scenario_successor_sees_downgraded_predecessor_ready_as_ack(*, tmp_path):
    fixture = _round(tmp_path=tmp_path, ctx=40)
    repo, topic, session, fake, sup, track = fixture
    _busy_after_ready(fixture=fixture)
    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert record.expired_at is None
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert state.token == signals.STATE_WINDING_DOWN
    sup.claude_identity_by_session[(session, topic)] = "claude:successor"
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))

    view = sup.evaluate(track=track, act=True)

    assert view.status == "winding-down"
    assert _respawn_count(fake=fake) == 0


def test_scenario_session_replaced_before_the_expiry_never_inherits_certifiable_floor(*, tmp_path):
    """The round-open identity anchors the floor. A successor that inherits the round's
    declaration and lets it expire establishes no certifiable floor, and is surfaced
    rather than restarted when it later declares ready itself."""
    clock = {"t": 1000.0}
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    assert sup.evaluate(track=track, act=True).status == "warned"

    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    sup.claude_identity_by_session[(session, topic)] = "claude:successor"
    clock["t"] = 1001.0 + _supervisor_config.READY_ARM_MAX_AGE + 1.0
    sup.evaluate(track=track, act=True)

    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert record.expired_at is None
    assert record.session_identity == "claude:topic:topic"

    clock["t"] += 10.0
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=clock["t"] - 1.0)
    view = sup.evaluate(track=track, act=True)

    assert view.status == "ready-uncertifiable"
    assert "identity differs" in (view.note or "")
    assert _respawn_count(fake=fake) == 0


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


def test_uncertifiable_ready_at_danger_surfaces_its_certification_failure(*, tmp_path):
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

    assert view.status == "ready-uncertifiable"
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
