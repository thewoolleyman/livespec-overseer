"""Releasing a HELD channel delivery (SPECIFICATION v060).

contracts.md, the daemon-message delivery channel: a held delivery is released when a
late acceptance acknowledgement for it arrives or, on a pane that was not already
busy, a turn is observed starting after the send — either of which makes it DELIVERED
— or when its round closes. A held keep-going nudge, which opens no round, is released
instead when the idle episode it answered ends.

A hold that could never be released would be worse than no hold at all: it withholds
every later daemon message to that session, so an unreleasable hold silently retires a
track from supervision. These four rules are the whole exit, which is why each one is
driven here rather than left to the act that consults the hold.
"""

import contextlib
import io as _io

import registry
from test_supervisor_builders import (
    FakeTmux,
    busy_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    nudge_count,
    wrapup_count,
)

__all__: list[str] = []


class HeldChannel:
    """A channel whose send is UNCONFIRMED and whose late acceptance is switchable."""

    def __init__(self, *, addressed_identity, outcome="unconfirmed"):
        self.name = "test-channel"
        self.addressed_identity = addressed_identity
        self.outcome = outcome
        self.accepted_late = False
        self.sent: list[str] = []

    def send(self, *, text):
        import _supervisor_channel

        self.sent.append(text)
        return _supervisor_channel.ChannelSend(outcome=self.outcome)

    def late_acceptance(self) -> bool:
        return self.accepted_late


def offer(*, monkeypatch, channel):
    import _supervisor_channel

    def provide(*, sup, runtime, session, topic, identity):
        del sup, runtime, session, topic, identity
        return channel

    monkeypatch.setattr(_supervisor_channel, "channel_provider", provide)


def _hold_of(*, sup, repo, topic):
    return registry.read_channel_hold(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)


def test_a_late_acceptance_acknowledgement_releases_the_hold(*, tmp_path, monkeypatch):
    """Release rule 1: the channel eventually says the session took it.

    That makes the delivery DELIVERED, so the hold goes and the track's later
    daemon messages flow again.
    """
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    channel = HeldChannel(addressed_identity=f"claude:{session}:{session}")
    offer(monkeypatch=monkeypatch, channel=channel)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)
        assert len(channel.sent) == 1
        assert _hold_of(sup=sup, repo=repo, topic=topic) is not None

        channel.accepted_late = True
        clock["t"] += 60.0
        sup.evaluate(track=track, act=True)

    assert _hold_of(sup=sup, repo=repo, topic=topic) is None


def test_a_turn_starting_after_the_send_releases_the_hold(*, tmp_path, monkeypatch):
    """Release rule 2: the pane was NOT already busy and now a turn is running.

    A turn that began after the send is evidence the session took the message, so
    the delivery is DELIVERED and the hold goes.
    """
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    channel = HeldChannel(addressed_identity=f"claude:{session}:{session}")
    offer(monkeypatch=monkeypatch, channel=channel)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)
        held = _hold_of(sup=sup, repo=repo, topic=topic)
        assert held is not None and held.pane_was_busy is False

        # The session starts a turn, which it could only have done after the send.
        fake.panes[session] = busy_capture(ctx=40)
        clock["t"] += 60.0
        sup.evaluate(track=track, act=True)

    assert _hold_of(sup=sup, repo=repo, topic=topic) is None


def test_a_turn_on_an_already_busy_pane_does_not_release_the_hold(*, tmp_path):
    """The control for rule 2, and the reason the hold records `pane_was_busy`.

    On a pane that was ALREADY busy when the message was sent, the turn in flight
    proves nothing about this delivery — so observing it must not release the hold.
    """
    import _supervisor_channel_hold

    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), now=lambda: 2000.0)
    hold = registry.ChannelHold(
        message="wrap-up",
        channel="test-channel",
        session_identity="claude:s:t",
        held_at=1000.0,
        pane_was_busy=True,
    )

    assert (
        _supervisor_channel_hold.release_reason(
            hold=hold, late_accepted=False, pane_busy=True, idle=False
        )
        is None
    )
    # The same hold on a pane that was NOT already busy IS released by that turn.
    assert (
        _supervisor_channel_hold.release_reason(
            hold=registry.ChannelHold(
                message="wrap-up",
                channel="test-channel",
                session_identity="claude:s:t",
                held_at=1000.0,
                pane_was_busy=False,
            ),
            late_accepted=False,
            pane_busy=True,
            idle=False,
        )
        is not None
    )
    del sup


def test_closing_the_round_releases_the_hold(*, tmp_path):
    """Release rule 3: a wrap-up's hold cannot outlive the round it belongs to.

    The hold shares the round's sidecar entry precisely so that closing the round
    takes it, rather than leaving a hold behind to withhold the NEXT round's
    wind-down from a session that has already moved on.
    """
    stamp_path = tmp_path / "stamps.json"
    registry.write_injection_stamp(
        repo="/repo", topic="topic", ts=1000.0, session_identity="claude:s:t", stamp_path=stamp_path
    )
    registry.record_channel_hold(
        repo="/repo",
        topic="topic",
        hold=registry.ChannelHold(
            message="wrap-up",
            channel="test-channel",
            session_identity="claude:s:t",
            held_at=1000.0,
            pane_was_busy=False,
        ),
        stamp_path=stamp_path,
    )
    assert (
        registry.read_channel_hold(repo="/repo", topic="topic", stamp_path=stamp_path) is not None
    )

    registry.clear_injection_stamp(repo="/repo", topic="topic", stamp_path=stamp_path)

    assert registry.read_channel_hold(repo="/repo", topic="topic", stamp_path=stamp_path) is None


def test_a_held_nudge_is_released_when_its_idle_episode_ends(*, tmp_path, monkeypatch):
    """Release rule 4: a nudge opens no round, so a round close cannot free it.

    The episode it answered is what bounds it — and the episode can end WITHOUT a
    turn starting, which is what makes this a separate rule rather than a
    restatement of rule 2. Here the session declares `blocked`, so it is no longer
    cleanly idle while never taking a turn.
    """
    import _supervisor_config

    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    channel = HeldChannel(addressed_identity=f"claude:{session}:{session}")
    offer(monkeypatch=monkeypatch, channel=channel)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)  # stamps the continuous-idle clock
        clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
        sup.evaluate(track=track, act=True)
        held = _hold_of(sup=sup, repo=repo, topic=topic)
        assert held is not None and held.message == "keep-going nudge"

        # The episode ends because the session says it is waiting on a human.
        declare(
            repo=repo,
            topic=topic,
            value="blocked: waiting on the maintainer",
            mtime=clock["t"],
        )
        clock["t"] += 60.0
        sup.evaluate(track=track, act=True)

    assert _hold_of(sup=sup, repo=repo, topic=topic) is None
    assert len(channel.sent) == 1
    assert nudge_count(fake=fake) == 0
    assert wrapup_count(fake=fake) == 0


def _nudge_held_by(*, sup, track, clock, channel):
    """Drive the idle episode until its keep-going nudge is held unconfirmed."""
    import _supervisor_config

    sup.evaluate(track=track, act=True)  # stamps the continuous-idle clock
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    sup.evaluate(track=track, act=True)
    assert len(channel.sent) == 1


def test_a_held_nudge_released_as_delivered_marks_its_idle_episode(*, tmp_path, monkeypatch):
    """A nudge released as DELIVERED owes the marker a landed paste would have written.

    The wrap-up's "never again" record is its notified bands, which
    `_mark_held_delivery_landed` already writes. The nudge's is the
    `idle-with-context-left` marker, and without it the freed track re-enters the
    idle branch in the very tick the channel confirmed the message — unmarked, so it
    is nudged again, and again on every tick after that.
    """
    import signals

    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    channel = HeldChannel(addressed_identity=f"claude:{session}:{session}")
    offer(monkeypatch=monkeypatch, channel=channel)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        _nudge_held_by(sup=sup, track=track, clock=clock, channel=channel)
        channel.accepted_late = True
        for _ in range(4):
            clock["t"] += 60.0
            sup.evaluate(track=track, act=True)

    assert _hold_of(sup=sup, repo=repo, topic=topic) is None
    assert len(channel.sent) == 1
    assert nudge_count(fake=fake) == 0
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT


def test_releasing_a_held_nudge_never_overwrites_a_session_declaration(*, tmp_path, monkeypatch):
    """The control for the marker write, and the reason it is guarded at all.

    A landed paste writes the marker from inside the idle branch, which is reached
    only when the session has declared nothing. A release runs in the tick's
    PROLOGUE instead, so the session may have declared `ready` since the nudge was
    sent — and the one token the daemon writes to itself must never clobber one of
    the four the session owns.
    """
    import signals

    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    channel = HeldChannel(addressed_identity=f"claude:{session}:{session}")
    offer(monkeypatch=monkeypatch, channel=channel)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        _nudge_held_by(sup=sup, track=track, clock=clock, channel=channel)
        declare(repo=repo, topic=topic, value="ready", mtime=clock["t"])
        channel.accepted_late = True
        clock["t"] += 60.0
        sup.evaluate(track=track, act=True)

    assert _hold_of(sup=sup, repo=repo, topic=topic) is None
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == "ready"
