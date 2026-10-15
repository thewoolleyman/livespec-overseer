"""Repo-level tests for the session-bound daemon-message channel (SPECIFICATION v060).

contracts.md, the daemon-message delivery channel: a wrap-up or keep-going nudge MAY be
delivered through a channel that addresses exactly one session by its live identity,
acknowledges each message, and distinguishes a pre-transmission refusal from a loss
after transmission. Everything here drives that contract through `evaluate`, because
the guards it must keep are the cascade's, not the delivery helper's.
"""

import contextlib
import io as _io

import registry
from test_supervisor_builders import (
    FakeTmux,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    nudge_count,
    wrapup_count,
)

__all__: list[str] = []


class RecordingChannel:
    """A supported channel double: it addresses one identity and acknowledges sends."""

    def __init__(self, *, addressed_identity, outcome="delivered", on_send=None):
        self.name = "test-channel"
        self.addressed_identity = addressed_identity
        self.outcome = outcome
        self.on_send = on_send
        self.sent: list[str] = []

    def send(self, *, text):
        import _supervisor_channel

        self.sent.append(text)
        if self.on_send is not None:
            self.on_send()
        return _supervisor_channel.ChannelSend(outcome=self.outcome)

    def late_acceptance(self) -> bool:
        return False


def offer(*, monkeypatch, channel):
    """Bind CHANNEL as the one supported channel every runtime resolves."""
    import _supervisor_channel

    def provide(*, sup, runtime, session, topic, identity):
        del sup, runtime, session, topic, identity
        return channel

    monkeypatch.setattr(_supervisor_channel, "channel_provider", provide)


def test_a_wrapup_is_delivered_through_a_supported_channel_without_typing(*, tmp_path, monkeypatch):
    """DoD 1: a runtime offering a supported channel receives its wrap-up through it."""
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    channel = RecordingChannel(addressed_identity=f"claude:{session}:{session}")
    offer(monkeypatch=monkeypatch, channel=channel)

    sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert len(channel.sent) == 1
    assert "Declare your state by writing ONE line" in channel.sent[0]
    assert wrapup_count(fake=fake) == 0


def test_a_keep_going_nudge_is_delivered_through_a_supported_channel(*, tmp_path, monkeypatch):
    """DoD 2: the nudge goes through the channel and still writes its own marker."""
    import _supervisor_config
    import signals

    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    channel = RecordingChannel(addressed_identity=f"claude:{session}:{session}")
    offer(monkeypatch=monkeypatch, channel=channel)
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)  # stamps the continuous-idle clock
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"

    assert len(channel.sent) == 1
    assert "do NOT offer to stop" in channel.sent[0]
    assert nudge_count(fake=fake) == 0
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT


def test_a_channel_delivery_is_named_as_the_delivery_path(*, tmp_path, monkeypatch):
    """DoD 3: the track's row and the daemon log both name the channel that carried it."""
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    offer(
        monkeypatch=monkeypatch,
        channel=RecordingChannel(addressed_identity=f"claude:{session}:{session}"),
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert "via channel test-channel: delivered" in err.getvalue()
    assert getattr(view, "delivery_path", None) == "wrap-up via channel test-channel: delivered"


def test_a_runtime_with_no_supported_channel_pastes_the_wrapup_as_before(*, tmp_path, monkeypatch):
    """DoD 4: no supported channel resolves, so the guarded paste runs unchanged."""
    import _supervisor_channel

    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    # The shipped default: no runtime has a measured channel, so none is offered.
    assert (
        _supervisor_channel.resolve_channel(
            sup=sup, runtime="claude", session=session, topic=topic, identity="claude:x:y"
        )
        is None
    )
    sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert wrapup_count(fake=fake) == 1
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is not None
    )


def test_a_paste_delivery_is_named_as_the_delivery_path(*, tmp_path, monkeypatch):
    """DoD 5: a pasted daemon message names the paste on the row and in the log."""
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert "via paste: delivered" in err.getvalue()
    assert view.delivery_path == "wrap-up via paste: delivered"


def test_a_channel_addressing_another_session_cancels_the_whole_act(*, tmp_path, monkeypatch):
    """DoD 6: an unproven binding sends nothing, pastes nothing, and opens no round."""
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    channel = RecordingChannel(addressed_identity="claude:some-other-session:other-topic")
    offer(monkeypatch=monkeypatch, channel=channel)

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert channel.sent == []
    assert wrapup_count(fake=fake) == 0
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )


def test_a_nudge_whose_channel_binding_is_unprovable_is_cancelled(*, tmp_path, monkeypatch):
    """DoD 6, the nudge half: a channel naming no identity cancels the act and
    leaves the idle episode un-nudged, so a later tick can answer it properly."""
    import _supervisor_config
    import signals

    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    channel = RecordingChannel(addressed_identity=None)
    offer(monkeypatch=monkeypatch, channel=channel)
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    with contextlib.redirect_stderr(_io.StringIO()):
        assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"

    assert channel.sent == []
    assert nudge_count(fake=fake) == 0
    assert signals.read_state(repo=str(repo), topic=topic) is None


def test_an_unconfirmed_channel_delivery_keeps_the_round_open_and_stamped(*, tmp_path, monkeypatch):
    """DoD 9: an unconfirmed send may have landed, so its round stands unchanged."""
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    offer(
        monkeypatch=monkeypatch,
        channel=RecordingChannel(
            addressed_identity=f"claude:{session}:{session}", outcome="unconfirmed"
        ),
    )
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)
    stamped = registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)

    assert stamped == 1000.0
    clock["t"] += 60.0
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 1000.0
    )


def test_a_refused_channel_delivery_falls_back_to_the_guarded_paste(*, tmp_path, monkeypatch):
    """DoD 7: a pre-transmission refusal is rescued by the paste in the same act,
    and the channel's failure does not un-open the round the paste then answers."""
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    channel = RecordingChannel(addressed_identity=f"claude:{session}:{session}", outcome="failed")
    offer(monkeypatch=monkeypatch, channel=channel)

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert len(channel.sent) == 1
    assert wrapup_count(fake=fake) == 1
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is not None
    )


def test_a_refused_channel_delivery_with_no_fallback_unopens_its_round(*, tmp_path, monkeypatch):
    """DoD 13: when the pre-paste re-read refuses, nothing follows the refusal and
    no stamped round is left standing behind an undelivered wrap-up."""
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    def pane_drops_to_a_shell():
        fake.cmds[session] = "zsh"

    channel = RecordingChannel(
        addressed_identity=f"claude:{session}:{session}",
        outcome="failed",
        on_send=pane_drops_to_a_shell,
    )
    offer(monkeypatch=monkeypatch, channel=channel)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert wrapup_count(fake=fake) == 0
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )
    assert "channel test-channel: failed" in err.getvalue()


def test_a_refused_nudge_channel_does_not_fall_back_to_a_paste(*, tmp_path, monkeypatch):
    """The fallback is the WRAP-UP's, because the re-read it repeats is the wrap-up's
    own guarded-paste predicate. A refused nudge is simply retried next episode."""
    import _supervisor_config
    import signals

    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    offer(
        monkeypatch=monkeypatch,
        channel=RecordingChannel(
            addressed_identity=f"claude:{session}:{session}", outcome="failed"
        ),
    )
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)

    assert nudge_count(fake=fake) == 0
    assert signals.read_state(repo=str(repo), topic=topic) is None


def test_a_failed_channel_attempt_and_its_fallback_paste_are_both_named(*, tmp_path, monkeypatch):
    """DoD 8: naming only the paste that rescued the act would read as though the
    channel had never been tried, so the row and the log name both legs in order."""
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    offer(
        monkeypatch=monkeypatch,
        channel=RecordingChannel(
            addressed_identity=f"claude:{session}:{session}", outcome="failed"
        ),
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    expected = "wrap-up via channel test-channel: failed, then paste: delivered"
    assert view.delivery_path == expected
    assert expected in err.getvalue()


def test_an_unconfirmed_delivery_is_never_sent_again_by_either_path(*, tmp_path, monkeypatch):
    """DoD 10: a send that may already have landed is held, not repeated — not
    through the channel that swallowed it and not by typing it into the pane."""
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    channel = RecordingChannel(
        addressed_identity=f"claude:{session}:{session}", outcome="unconfirmed"
    )
    offer(monkeypatch=monkeypatch, channel=channel)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)
        assert len(channel.sent) == 1
        clock["t"] += 60.0
        sup.evaluate(track=track, act=True)
        clock["t"] += 60.0
        sup.evaluate(track=track, act=True)

    assert len(channel.sent) == 1
    assert wrapup_count(fake=fake) == 0


def test_no_later_daemon_message_reaches_a_session_while_a_delivery_is_held(
    *, tmp_path, monkeypatch
):
    """DoD 11: the hold is against the SESSION, not against one message — a later
    wrap-up band is withheld too, by either path, until the hold is released."""
    monkeypatch.chdir(tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    channel = RecordingChannel(
        addressed_identity=f"claude:{session}:{session}", outcome="unconfirmed"
    )
    offer(monkeypatch=monkeypatch, channel=channel)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=track, act=True)
        assert len(channel.sent) == 1
        # The session keeps burning context, so a LOWER escalation band comes due.
        fake.panes[session] = idle_capture(ctx=20)
        clock["t"] += 600.0
        sup.evaluate(track=track, act=True)

    assert len(channel.sent) == 1
    assert wrapup_count(fake=fake) == 0


def test_a_malformed_hold_record_reads_as_no_hold(*, tmp_path):
    """Fail-soft toward NO hold: an unreadable record must not wedge a track's
    daemon messages forever, so the delivery it guarded is re-attempted."""
    import json

    import _registry_channel_hold

    stamp_path = tmp_path / "stamps.json"
    stamp_path.write_text(
        json.dumps({"/repo\ttopic": {"channel_hold": {"message": 7, "channel": "c"}}}),
        encoding="utf-8",
    )

    assert (
        _registry_channel_hold.read_channel_hold(repo="/repo", topic="topic", stamp_path=stamp_path)
        is None
    )
