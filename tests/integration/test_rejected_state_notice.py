"""Integration coverage for the rejected-state recovery notice."""

from __future__ import annotations

import registry
import signals
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _held(*, sup, repo, topic):
    return registry.read_channel_hold(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)


def test_scenario_a_rejected_state_value_is_told_to_its_session_within_one_cycle(*, tmp_path):
    """A settled session hears its rejected declaration without waiting for a wrap-up."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    declare(repo=repo, topic=topic, value="waiting: invented", mtime=1001.0)

    sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    notice = next(text for text in fake.paste_texts() if "REJECTED STATE VALUE" in text)
    assert "'waiting: invented' was not accepted" in notice
    assert "overseer-declare winding-down" in notice
    assert "overseer-declare ready" in notice
    assert "overseer-declare blocked" in notice
    assert "overseer-declare done" in notice


def test_scenario_a_rejected_notice_is_deferred_cancelled_and_retried_after_a_failed_paste(
    *, tmp_path
):
    """The guarded notice waits for an idle pane and is not delivered after cancellation."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture="generating")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    declare(repo=repo, topic=topic, value="waiting: invented", mtime=1001.0)

    sup.evaluate(track=track, act=True)
    assert not any("REJECTED STATE VALUE" in text for text in fake.paste_texts())

    fake.panes[session] = idle_capture(ctx=73)
    fake.paste_ok = False
    sup.evaluate(track=track, act=True)

    fake.paste_ok = True
    sup.evaluate(track=track, act=True)
    assert sum("REJECTED STATE VALUE" in text for text in fake.paste_texts()) == 2

    other_repo, other_topic = make_plan(tmp_path=tmp_path / "cancelled")
    other_session = registry.tmux_id(repo=str(other_repo), topic=other_topic)
    other_fake = FakeTmux()
    other_fake.serve(session=other_session, repo=other_repo, capture="generating")
    other_sup = make_supervisor(tmp_path=tmp_path / "cancelled", fake=other_fake)
    other_track = mapped_track(repo=other_repo, topic=other_topic, session=other_session)
    declare(repo=other_repo, topic=other_topic, value="waiting: invented", mtime=1001.0)
    other_sup.evaluate(track=other_track, act=True)
    declare(repo=other_repo, topic=other_topic, value="blocked: operator", mtime=1002.0)
    other_fake.panes[other_session] = idle_capture(ctx=73)
    other_sup.evaluate(track=other_track, act=True)
    assert not any("REJECTED STATE VALUE" in text for text in other_fake.paste_texts())


def test_an_unconfirmed_channel_notice_stays_held_until_the_session_declares(
    *, tmp_path, monkeypatch
):
    """An uncertain channel send cannot be released by later generation."""
    import _supervisor_channel

    class UnconfirmedChannel:
        name = "test-channel"

        def __init__(self, *, identity):
            self.addressed_identity = identity

        def send(self, *, text):
            del text
            return _supervisor_channel.ChannelSend(outcome="unconfirmed")

        def late_acceptance(self):
            return False

    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    channel = UnconfirmedChannel(identity=f"claude:{session}:{session}")
    monkeypatch.setattr(_supervisor_channel, "channel_provider", lambda **_kwargs: channel)
    declare(repo=repo, topic=topic, value="waiting: invented", mtime=1001.0)

    sup.evaluate(track=track, act=True)
    assert _held(sup=sup, repo=repo, topic=topic) is not None

    fake.panes[session] = idle_capture(ctx=73)
    sup.evaluate(track=track, act=True)
    assert _held(sup=sup, repo=repo, topic=topic) is not None

    fake.panes[session] = "generating"
    sup.evaluate(track=track, act=True)
    assert _held(sup=sup, repo=repo, topic=topic) is not None

    declare(repo=repo, topic=topic, value="winding-down", mtime=1002.0)
    sup.evaluate(track=track, act=True)
    assert _held(sup=sup, repo=repo, topic=topic) is None

    other_repo, other_topic = make_plan(tmp_path=tmp_path / "misaddressed")
    other_session = registry.tmux_id(repo=str(other_repo), topic=other_topic)
    other_fake = FakeTmux()
    other_fake.serve(session=other_session, repo=other_repo, capture=idle_capture(ctx=73))
    other_sup = make_supervisor(tmp_path=tmp_path / "misaddressed", fake=other_fake)
    monkeypatch.setattr(
        _supervisor_channel,
        "channel_provider",
        lambda **_kwargs: UnconfirmedChannel(identity="claude:another:session"),
    )
    declare(repo=other_repo, topic=other_topic, value="waiting: misaddressed", mtime=1001.0)
    other_sup.evaluate(
        track=mapped_track(repo=other_repo, topic=other_topic, session=other_session), act=True
    )
    assert not other_fake.paste_texts()


def test_scenario_a_rejected_state_notice_is_durable_per_rendered_value_and_renoticed_once(
    *, tmp_path
):
    """A value is edge-triggered over restarts, earns one day-later repeat, and new values."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"now": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["now"])
    track = mapped_track(repo=repo, topic=topic, session=session)
    rejected = signals.rejected_state_path(repo=str(repo), topic=topic)
    rejected.parent.mkdir(parents=True)
    rejected.write_text("waiting: first\n", encoding="utf-8")

    sup.evaluate(track=track, act=True)
    assert sum("REJECTED STATE VALUE" in text for text in fake.paste_texts()) == 1

    restarted = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["now"])
    restarted.evaluate(track=track, act=True)
    assert sum("REJECTED STATE VALUE" in text for text in fake.paste_texts()) == 1

    clock["now"] += 24 * 60 * 60
    restarted.evaluate(track=track, act=True)
    restarted.evaluate(track=track, act=True)
    assert sum("REJECTED STATE VALUE" in text for text in fake.paste_texts()) == 2

    rejected.write_text("waiting: second\n", encoding="utf-8")
    restarted.evaluate(track=track, act=True)
    assert sum("REJECTED STATE VALUE" in text for text in fake.paste_texts()) == 3
