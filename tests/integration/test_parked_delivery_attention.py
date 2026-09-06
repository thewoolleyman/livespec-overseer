"""Integration-tier coverage for parked-delivery daemon attention.

Tier: `tests.integration` is one of the documented default `scenario_tiers`
prefixes. These tests drive a real Supervisor tick from captured pane text through
row projection and the operator attention surfaces.
"""

from __future__ import annotations

import contextlib
import io as _io
import json
from pathlib import Path

from overseer import _supervisor_snapshot, registry, signals, supervisor
from overseer.test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    write_fresh_supervisor_state,
)
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def parked_delivery_capture(*, ctx: int = 80) -> str:
    return (
        "How do you want to proceed?\n"
        "❯ 1. Dispatch the waiting children\n"
        "  2. Leave the track parked\n"
        "Enter to select · ↑/↓ to navigate · Esc to cancel\n"
        "  @ livespec-console-beads-fabro-foreman❯\n"
        "    Console foreman, decision-relevant update for your open dispatch picker\n"
        "    fleet-ci-runner-pool track has EXECUTED the ClusterQueue resize (2026-08\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def picker_only_capture(*, ctx: int = 80) -> str:
    return (
        "How do you want to proceed?\n"
        "❯ 1. Dispatch the waiting children\n"
        "  2. Leave the track parked\n"
        "Enter to select · ↑/↓ to navigate · Esc to cancel\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def malformed_delivery_capture(*, ctx: int = 80) -> str:
    return (
        "How do you want to proceed?\n"
        "❯ 1. Dispatch the waiting children\n"
        "  2. Leave the track parked\n"
        "  @ sender-topic❯\n"
        "normal prose after the header\n"
        f"  Opus 4.8 (1M context) | /x/repo | Ctx: {ctx}% left\n"
    )


def make_parked_delivery_track(*, tmp_path, capture: str):
    repo, topic = make_plan(tmp_path=tmp_path, topic="parked-delivery")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=capture)
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        now=lambda: 2000.0,
        own_pane="%7",
        watch_repos=[str(repo)],
    )
    track = mapped_track(repo=repo, topic=topic, session=session)
    write_fresh_supervisor_state(repo=repo, topic=topic)
    registry.append_mapping(track=track, store_path=sup.store_path, added_at="t")
    return repo, topic, session, fake, sup, track


def published_row(*, sup, topic: str):
    """The row a snapshot consumer reads, taken from the file the tick wrote."""
    document = json.loads(Path(sup.status_path).read_text(encoding="utf-8"))
    return next(row for row in document["rows"] if row["topic"] == topic)


def sender_row(*, note: str | None, sender: str | None):
    return supervisor.RowView(
        topic="test-and-gate-integrity",
        repo="/repo",
        tmux="test-and-gate-integrity",
        runtime="claude",
        ctx=80,
        status="parked-delivery",
        note=note,
        picker_open=True,
        parked_delivery_sender=sender,
    )


def queued_sender(*, capture: str) -> str | None:
    detector = getattr(signals, "queued_cross_session_delivery_sender", None)
    if detector is None:
        return None
    return detector(capture_text=capture)


def test_queued_delivery_sender_detects_real_parked_delivery_shape():
    assert (
        queued_sender(capture=parked_delivery_capture()) == "livespec-console-beads-fabro-foreman"
    )


def test_queued_delivery_sender_rejects_picker_with_no_delivery():
    assert queued_sender(capture=picker_only_capture()) is None


def test_queued_delivery_sender_requires_continuation_body():
    assert queued_sender(capture=malformed_delivery_capture()) is None


def test_scenario_message_queued_behind_open_picker_is_surfaced_as_attention(*, tmp_path):
    repo, topic, _session, fake, sup, _track = make_parked_delivery_track(
        tmp_path=tmp_path, capture=parked_delivery_capture()
    )
    state_path = signals.state_path(repo=str(repo), topic=topic)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("ready\n", encoding="utf-8")

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        rows = sup.tick(act=True)

    row = next(item for item in rows if item.topic == topic)
    output = sup.out.getvalue()

    assert row.status == "parked-delivery"
    assert row.picker_open is True
    assert row.stall_seconds == 0
    assert row.note == "queued delivery from livespec-console-beads-fabro-foreman"
    assert supervisor.needs_attention(row=row) is True
    assert "NEEDS YOU (1):" in output
    assert "livespec-console-beads-fabro-foreman" in output
    assert fake.window_name == "overseer(1!)"
    assert err.getvalue().count("queued delivery from livespec-console-beads-fabro-foreman") == 1
    assert state_path.read_text(encoding="utf-8") == "ready\n"
    assert not fake.has(method="paste")
    assert not fake.has(method="keys")
    assert not fake.has(method="respawn")
    assert not fake.has(method="new")


def test_parked_delivery_attention_is_edge_triggered_and_clears(*, tmp_path):
    _repo, topic, session, fake, sup, track = make_parked_delivery_track(
        tmp_path=tmp_path, capture=parked_delivery_capture()
    )

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        first = sup.evaluate(track=track, act=True)
        second = sup.evaluate(track=track, act=True)
        fake.panes[session] = picker_only_capture()
        consumed = sup.evaluate(track=track, act=True)
        fake.panes[session] = parked_delivery_capture()
        rearmed = sup.evaluate(track=track, act=True)
        fake.panes[session] = idle_capture(ctx=80, topic=topic)
        resolved = sup.evaluate(track=track, act=True)

    assert first.status == "parked-delivery"
    assert second.status == "parked-delivery"
    assert consumed.status == "blocked:human"
    assert rearmed.status == "parked-delivery"
    assert resolved.status == "idle-with-context-left"
    assert err.getvalue().count("queued delivery from livespec-console-beads-fabro-foreman") == 2
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")


def test_scenario_open_picker_with_nothing_queued_is_not_parked_delivery_attention(*, tmp_path):
    _repo, topic, _session, fake, sup, _track = make_parked_delivery_track(
        tmp_path=tmp_path, capture=picker_only_capture()
    )

    rows = sup.tick(act=True)
    row = next(item for item in rows if item.topic == topic)
    output = sup.out.getvalue()

    assert row.status == "blocked:human"
    assert row.picker_open is True
    assert row.note is None
    assert supervisor.needs_attention(row=row) is True
    assert "queued delivery" not in output
    assert fake.window_name == "overseer(1!)"
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")


# --------------------------------------------------------------------------- #
# The SENDER reaches a snapshot consumer (overseer-zljboi).
#
# The detector already extracts the sender and the daemon's own pane renders it in
# full; what a snapshot consumer got was the sender's fate inside the elided
# `note`, which is prose bounded by a DISPLAY width. These are the two-way control
# over the same real captured panes the detector was built from: a parked pane WITH
# a queued delivery must expose the sender, and a parked pane with a picker and NO
# delivery must expose none.
# --------------------------------------------------------------------------- #


def test_scenario_parked_delivery_sender_reaches_a_snapshot_consumer(*, tmp_path):
    _repo, topic, _session, _fake, sup, _track = make_parked_delivery_track(
        tmp_path=tmp_path, capture=parked_delivery_capture()
    )

    rows = sup.tick(act=True)
    row = next(item for item in rows if item.topic == topic)
    published = published_row(sup=sup, topic=topic)

    assert row.status == "parked-delivery"
    assert published["status"] == "parked-delivery"
    assert published.get("parked_delivery_sender") == "livespec-console-beads-fabro-foreman"


def test_scenario_open_picker_with_nothing_queued_publishes_no_sender(*, tmp_path):
    _repo, topic, _session, _fake, sup, _track = make_parked_delivery_track(
        tmp_path=tmp_path, capture=picker_only_capture()
    )

    rows = sup.tick(act=True)
    row = next(item for item in rows if item.topic == topic)
    published = published_row(sup=sup, topic=topic)

    assert row.status == "blocked:human"
    assert published["status"] == "blocked:human"
    assert "parked_delivery_sender" in published
    assert published["parked_delivery_sender"] is None


def test_the_sender_field_survives_a_note_elision_that_destroys_the_attribution():
    assert "parked_delivery_sender" in supervisor.RowView.__dataclass_fields__

    sender = "livespec-console-beads-fabro-foreman"
    full_note = f"picker stalled 15h; queued delivery from {sender}"
    payload = _supervisor_snapshot.row_payload(
        sup=object(), row=sender_row(note=full_note, sender=sender)
    )

    note = payload["note"]
    assert isinstance(note, str)
    assert len(note) <= _supervisor_snapshot.SNAPSHOT_NOTE_LIMIT
    assert note != full_note
    assert sender not in note
    assert payload["parked_delivery_sender"] == sender


def test_a_pane_derived_sender_is_length_bounded_before_it_reaches_the_snapshot():
    assert "SNAPSHOT_SENDER_LIMIT" in _supervisor_snapshot.__all__

    limit = _supervisor_snapshot.SNAPSHOT_SENDER_LIMIT
    payload = _supervisor_snapshot.row_payload(
        sup=object(), row=sender_row(note=None, sender="x" * (limit + 40))
    )

    published = payload["parked_delivery_sender"]
    assert isinstance(published, str)
    assert len(published) == limit
    assert limit > _supervisor_snapshot.SNAPSHOT_NOTE_LIMIT
