"""The fail-soft and latch edges of releasing a held channel delivery (v060).

Companion to `test_daemon_message_channel_release`, which drives the four release
RULES through `evaluate`. These are the edges those scenarios cannot reach, because
each is a direction the main path deliberately never takes: a record that did not
survive its round trip, a release asked for when nothing is held, a release that must
also clear a compaction latch, and a runtime whose channel cannot speak for the
message that was held.

Every one of them fails SOFT, and in the same direction — toward not releasing and
not crashing — because the alternative to a conservative answer here is re-sending a
wind-down that may already have landed.
"""

from __future__ import annotations

import json
from pathlib import Path

import registry
from test_supervisor_builders import FakeTmux, make_supervisor, mapped_track

__all__: list[str] = []


def _hold(*, bands=(), latched=None, channel="test-channel"):
    return registry.ChannelHold(
        message="wrap-up",
        channel=channel,
        session_identity="claude:s:t",
        held_at=1000.0,
        pane_was_busy=False,
        bands=bands,
        compaction_latched_at=latched,
    )


def test_a_bands_member_that_did_not_survive_the_round_trip_is_dropped(*, tmp_path):
    """Fail-soft PER MEMBER, not per record.

    A band that came back as something other than an integer is one escalation the
    release cannot mark. Rejecting the whole record over it would discard the hold
    and re-send a message that may have landed — the worse of the two failures — so
    the surviving bands are kept and the junk is dropped.
    """
    stamp_path = tmp_path / "stamps.json"
    stamp_path.write_text(
        json.dumps(
            {
                "/repo\ttopic": {
                    "channel_hold": {
                        "bands": [50, "forty", None, 30],
                        "channel": "test-channel",
                        "held_at": 1000.0,
                        "message": "wrap-up",
                        "pane_was_busy": False,
                        "session_identity": "claude:s:t",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    held = registry.read_channel_hold(repo="/repo", topic="topic", stamp_path=stamp_path)

    assert held is not None
    assert held.bands == (50, 30)


def test_a_bands_value_that_is_not_a_list_at_all_reads_as_no_bands(*, tmp_path):
    """The same fail-soft one level up: a non-list `bands` is simply no bands.

    The hold still stands and is still released by a turn, its round or its episode;
    only the marking it could have completed is lost.
    """
    stamp_path = tmp_path / "stamps.json"
    stamp_path.write_text(
        json.dumps(
            {
                "/repo\ttopic": {
                    "channel_hold": {
                        "bands": "50",
                        "channel": "test-channel",
                        "held_at": 1000.0,
                        "message": "wrap-up",
                        "pane_was_busy": False,
                        "session_identity": "claude:s:t",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    held = registry.read_channel_hold(repo="/repo", topic="topic", stamp_path=stamp_path)

    assert held is not None
    assert held.bands == ()


def test_clearing_a_hold_that_is_not_there_is_a_no_op(*, tmp_path):
    """A release asked for when nothing is held must not disturb the round.

    The round's own stamp and notified bands live in the same sidecar entry, so a
    clear that rewrote the entry on a miss would be a write with no reason to exist.
    """
    stamp_path = tmp_path / "stamps.json"
    registry.write_injection_stamp(
        repo="/repo", topic="topic", ts=1000.0, session_identity="claude:s:t", stamp_path=stamp_path
    )
    before = stamp_path.read_bytes()

    registry.clear_channel_hold(repo="/repo", topic="topic", stamp_path=stamp_path)

    assert stamp_path.read_bytes() == before
    stamped = registry.read_injection_stamp(repo="/repo", topic="topic", stamp_path=stamp_path)
    assert stamped == 1000.0


def test_clearing_a_hold_on_a_track_with_no_sidecar_entry_at_all_is_a_no_op(*, tmp_path):
    """The same miss, one step earlier: no entry for this track in the first place."""
    stamp_path = tmp_path / "stamps.json"
    stamp_path.write_text(json.dumps({}), encoding="utf-8")

    registry.clear_channel_hold(repo="/repo", topic="topic", stamp_path=stamp_path)

    assert registry.read_channel_hold(repo="/repo", topic="topic", stamp_path=stamp_path) is None


def test_a_delivered_release_also_marks_the_compaction_latch(*, tmp_path, monkeypatch):
    """A latched round re-arms its bands ONCE per latch, and the release must say so.

    Marking the bands without marking the latch would leave the next tick free to
    re-arm them — `armed_bands` treats a latched round's bands as unnotified until
    `compaction_rearmed_at` matches the latch — so the wrap-up this release just
    called DELIVERED would come due again immediately.
    """
    import _supervisor_channel
    import _supervisor_channel_hold

    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), now=lambda: 2000.0)
    track = mapped_track(repo=repo, topic="topic", session="topic")
    registry.write_injection_stamp(
        repo=str(repo),
        topic="topic",
        ts=1000.0,
        session_identity="claude:s:t",
        stamp_path=sup.stamp_path,
    )
    registry.record_channel_hold(
        repo=str(repo),
        topic="topic",
        hold=_hold(bands=(50, 40), latched=900.0),
        stamp_path=sup.stamp_path,
    )
    monkeypatch.setattr(
        _supervisor_channel,
        "channel_provider",
        lambda **_: None,  # no channel; the turn-started rule is what releases it
    )

    _supervisor_channel_hold.release_resolved_hold(
        sup=sup, track=track, is_codex=False, pane_busy=True, idle=False
    )

    record = registry.read_round_record(repo=str(repo), topic="topic", stamp_path=sup.stamp_path)
    remaining = registry.read_channel_hold(repo=str(repo), topic="topic", stamp_path=sup.stamp_path)
    assert remaining is None
    assert sorted(record.bands) == [40, 50]
    assert record.compaction_rearmed_at == 900.0


def test_a_channel_that_cannot_speak_for_the_held_message_gives_no_late_answer(
    *, tmp_path, monkeypatch
):
    """Only the channel the hold NAMES may acknowledge it late.

    A runtime that now offers a DIFFERENT channel, or none at all, has no answer
    about a message it never carried — so neither case releases the hold, which then
    waits for a turn, its round or its episode. Asserted through the public release,
    which must leave the hold standing in both shapes.
    """
    import _supervisor_channel
    import _supervisor_channel_hold

    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), now=lambda: 2000.0)
    track = mapped_track(repo=repo, topic="topic", session="topic")

    class OtherChannel:
        name = "a-different-channel"
        addressed_identity = "claude:s:t"

        def send(self, *, text):  # pragma: no cover - never sent through here
            raise AssertionError("the release must not send anything")

        def late_acceptance(self) -> bool:  # pragma: no cover - must never be asked
            raise AssertionError("a channel that did not carry the message is not asked")

    for provider in (lambda **_: OtherChannel(), lambda **_: None):
        registry.record_channel_hold(
            repo=str(repo), topic="topic", hold=_hold(), stamp_path=sup.stamp_path
        )
        monkeypatch.setattr(_supervisor_channel, "channel_provider", provider)

        # Not busy and not idle: no rule can fire except a late acceptance.
        _supervisor_channel_hold.release_resolved_hold(
            sup=sup, track=track, is_codex=False, pane_busy=False, idle=False
        )

        assert (
            registry.read_channel_hold(repo=str(repo), topic="topic", stamp_path=sup.stamp_path)
            is not None
        )
    assert Path(sup.stamp_path).is_file()
