"""Repo-level tests for the session-bound daemon-message channel (SPECIFICATION v060).

contracts.md, the daemon-message delivery channel: a wrap-up or keep-going nudge MAY be
delivered through a channel that addresses exactly one session by its live identity,
acknowledges each message, and distinguishes a pre-transmission refusal from a loss
after transmission. Everything here drives that contract through `evaluate`, because
the guards it must keep are the cascade's, not the delivery helper's.
"""

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

    def __init__(self, *, addressed_identity, outcome="delivered"):
        self.name = "test-channel"
        self.addressed_identity = addressed_identity
        self.outcome = outcome
        self.sent: list[str] = []

    def send(self, *, text):
        import _supervisor_channel

        self.sent.append(text)
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
