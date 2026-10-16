"""The acts that are NOT daemon messages keep their paste forms (SPECIFICATION v060).

contracts.md, the daemon-message delivery channel, first paragraph: the wrap-up and
the keep-going nudge are daemon messages and MAY travel through a supported channel.
"The resume prompt a restart delivers to its successor, the pair nudge to a
supervisor, and the picker-stall relay act are NOT: each keeps its paste form and its
own submission, retry and attention rules."

This is a REGRESSION PIN, and it passed the moment it was written — neither act was
ever wired to the channel. It is here because the reason they must not be is not
visible from the delivery code, and a future reader generalising "deliver daemon
messages through the channel" would have no signal that these two are excluded on
purpose:

- the RESUME PROMPT is retried by re-sending its submission against the COMPOSER, and
  both self-heal and attention key on the composer holding the exact resume text. A
  channel delivery satisfies none of those, which is why routing it through one is an
  explicit deferral needing its own ratified rules rather than an oversight.
- the PICKER-STALL RELAY deliberately pastes WITHOUT submitting, so the maintainer
  answers their own picker. A channel delivers a turn to the model; using one here
  would answer an open picker on the human's behalf, which the contract forbids
  outright.

Both tests offer a channel that would accept anything, so a regression shows up as a
message on the channel rather than as a missing paste.
"""

from __future__ import annotations

import contextlib
import io as _io
from pathlib import Path

import registry
import signals
from test_supervisor_builders import (
    arm_ready_marker,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


class EagerChannel:
    """A supported channel that would carry ANY message it is handed."""

    def __init__(self, *, addressed_identity: str) -> None:
        self.name = "test-channel"
        self.addressed_identity = addressed_identity
        self.sent: list[str] = []

    def send(self, *, text: str):
        import _supervisor_channel

        self.sent.append(text)
        return _supervisor_channel.ChannelSend(outcome=_supervisor_channel.CHANNEL_DELIVERED)

    def late_acceptance(self) -> bool:
        return False


def _offer_everywhere(*, monkeypatch, channel: EagerChannel) -> None:
    import _supervisor_channel

    def provide(*, sup, runtime, session, topic, identity):
        del sup, runtime, session, topic, identity
        return channel

    monkeypatch.setattr(_supervisor_channel, "channel_provider", provide)


def _pasted(*, fake: FakeTmux) -> list[str]:
    """Every bracketed-paste payload this fake saw, in order.

    `FakeTmux.calls` holds variable-length tuples (one per tmux verb), so the arity
    is checked rather than unpacked blind.
    """
    return [call[2] for call in fake.calls if call[0] == "paste" and len(call) > 2]


def test_a_restarts_resume_prompt_is_pasted_even_when_a_channel_exists(
    *, tmp_path: Path, monkeypatch
) -> None:
    """The resume prompt reaches the successor's composer, not the channel."""
    import _supervisor_prompts

    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30), cmd="node")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    channel = EagerChannel(addressed_identity=f"claude:{session}:{session}")
    _offer_everywhere(monkeypatch=monkeypatch, channel=channel)
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=f"claude:{session}:{session}",
        stamp_path=sup.stamp_path,
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=track, act=True)

    expected = _supervisor_prompts.resume_for_track(track=track)
    assert view.status == "restarting"
    assert expected is not None
    assert expected in _pasted(fake=fake)
    assert channel.sent == []


def test_the_picker_stall_relay_is_pasted_even_when_a_channel_exists(
    *, tmp_path: Path, monkeypatch
) -> None:
    """The charter reminder is pasted into the stalled picker and never submitted.

    Driven through the nudge act directly, because the point is the ROUTE the act
    takes rather than the stall arithmetic that decides when it is due.
    """
    import _supervisor_nudge
    import _supervisor_prompts_nudges
    from _supervisor_records import InjectState

    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=70), cmd="node")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    channel = EagerChannel(addressed_identity=f"claude:{session}:{session}")
    _offer_everywhere(monkeypatch=monkeypatch, channel=channel)

    with contextlib.redirect_stderr(_io.StringIO()):
        _supervisor_nudge.nudge_charter_authorized_picker_stall(
            sup=sup, track=track, target=session, stall_seconds=900, istate=InjectState()
        )

    expected = _supervisor_prompts_nudges.charter_authorized_unblock_nudge_message()
    assert expected in _pasted(fake=fake)
    assert channel.sent == []
    # Pasted, never submitted: answering the picker stays the maintainer's act.
    assert not any(call[0] == "send_keys" for call in fake.calls)


def test_neither_paste_only_act_records_a_delivery_path(*, tmp_path: Path, monkeypatch) -> None:
    """Only a DAEMON MESSAGE acquires a delivery-path record.

    The row and the log name the route for the wrap-up and the nudge because the
    contract requires it of those two. A resume prompt that started reporting one
    would be the visible symptom of it having become a daemon message.
    """
    import _supervisor_nudge
    from _supervisor_config import track_key
    from _supervisor_records import InjectState

    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=70), cmd="node")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    _offer_everywhere(
        monkeypatch=monkeypatch,
        channel=EagerChannel(addressed_identity=f"claude:{session}:{session}"),
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        _supervisor_nudge.nudge_charter_authorized_picker_stall(
            sup=sup, track=track, target=session, stall_seconds=900, istate=InjectState()
        )

    istate = sup.inject.get(track_key(repo=str(repo), topic=topic))
    assert istate is None or istate.last_delivery is None
    assert signals.read_state(repo=str(repo), topic=topic) is None
