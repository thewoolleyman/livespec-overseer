"""Integration edges for the rejected-state recovery notice."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import registry
import signals
from test_supervisor_builders import idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _notice_module():
    module_path = Path(__file__).parents[2] / "overseer" / "_supervisor_rejected_notice.py"
    assert module_path.is_file()
    return importlib.import_module("_supervisor_rejected_notice")


def _rejected_copy(*, repo, topic, value):
    path = signals.rejected_state_path(repo=str(repo), topic=topic)
    path.parent.mkdir(parents=True)
    path.write_text(f"{value}\n", encoding="utf-8")


def test_rejected_notice_fresh_gate_rechecks_every_delivery_guard(*, tmp_path, monkeypatch):
    """A notice is cancelled when a fresh observation withdraws its authorization."""
    notice = _notice_module()
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    _rejected_copy(repo=repo, topic=topic, value="waiting: invalid")

    monkeypatch.setattr(notice._supervisor_launch, "pane_settled", lambda **_kwargs: False)
    assert (
        notice._fresh_eligible(
            sup=sup, track=track, session=session, target=session, value="waiting: invalid"
        )
        is None
    )

    monkeypatch.setattr(notice._supervisor_launch, "pane_settled", lambda **_kwargs: True)
    monkeypatch.setattr(notice._supervisor_observe, "pane_is_managed", lambda **_kwargs: False)
    assert (
        notice._fresh_eligible(
            sup=sup, track=track, session=session, target=session, value="waiting: invalid"
        )
        is None
    )

    monkeypatch.setattr(notice._supervisor_observe, "pane_is_managed", lambda **_kwargs: True)
    assert (
        notice._fresh_eligible(
            sup=sup, track=track, session=session, target=session, value="waiting: changed"
        )
        is None
    )

    state = signals.state_path(repo=str(repo), topic=topic)
    state.write_text("ready\n", encoding="utf-8")
    assert (
        notice._fresh_eligible(
            sup=sup, track=track, session=session, target=session, value="waiting: invalid"
        )
        is None
    )


def test_rejected_notice_surfaces_a_standing_unconfirmed_hold(*, tmp_path):
    """A possibly landed channel notice blocks a second send until its release rule fires."""
    notice = _notice_module()
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    _rejected_copy(repo=repo, topic=topic, value="waiting: invalid")
    registry.record_channel_hold(
        repo=str(repo),
        topic=topic,
        hold=registry.ChannelHold(
            message="rejected-state notice",
            channel="test",
            session_identity=None,
            held_at=sup.now(),
            pane_was_busy=False,
            rejected_value="waiting: invalid",
        ),
        stamp_path=sup.stamp_path,
    )
    observation = importlib.import_module("_supervisor_observe").observe(
        sup=sup,
        track=track,
        session=session,
        target=session,
        key=f"{repo}::{topic}",
    )

    notice.maybe_send_rejected_state_notice(
        sup=sup, track=track, obs=observation, session=session, target=session, act=True
    )

    assert not fake.paste_texts()


def test_rejected_notice_ignores_an_unusable_durable_record(*, tmp_path):
    """A corrupt durable record cannot suppress recovery from the rejected copy."""
    _notice_module()
    repo, topic = make_plan(tmp_path=tmp_path)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    key = f"{repo}::{topic}"
    Path(sup.stamp_path).write_text(
        json.dumps({key: {"rejected_state_notice": {"digest": 3}}}), encoding="utf-8"
    )

    assert (
        registry.read_rejected_state_notice(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )
