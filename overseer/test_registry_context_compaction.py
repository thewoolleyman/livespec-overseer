"""Beside-tests for the durable context-compaction record in the mapping store."""

from __future__ import annotations

import contextlib
import io as _io

import _registry_store_rows
import registry
from test_supervisor_builders import make_plan, mapped_track

__all__: list[str] = []

_LATCHED = registry.ContextCompaction(
    session_identity="codex:019f6a1e-266d-7fc2-8eb2-15ec9d324fb8",
    watermark_ctx=78,
    latched_at=1234.0,
    from_ctx=6,
    to_ctx=78,
)


def _store_with_row(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    store = tmp_path / "map.jsonl"
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=topic), store_path=store
    )
    return repo, topic, store


def _row_for(*, store, topic):
    for track in registry.read_valid_mapping(store_path=store):
        if track.topic == topic:
            return track
    raise AssertionError(f"no mapping row for {topic}")


def test_a_track_with_no_compaction_evidence_carries_no_record():
    track = mapped_track(repo="/x/repo", topic="topic", session="topic")

    # Absent and recorded are the only two states: a never-compacted track must stay
    # indistinguishable from one the daemon has simply never read.
    assert track.context_compaction is None
    assert "context_compaction" not in _registry_store_rows.track_to_row(track=track)


def test_the_latch_survives_a_write_read_round_trip(*, tmp_path):
    repo, topic, store = _store_with_row(tmp_path=tmp_path)

    changed = registry.record_context_compaction(
        repo=str(repo), topic=topic, record=_LATCHED, store_path=store
    )

    assert changed is True
    # Re-read through the ordinary mapping reader — the surface the next daemon
    # generation uses at cold start, so this IS the daemon-restart survival proof.
    assert _row_for(store=store, topic=topic).context_compaction == _LATCHED


def test_recording_an_unchanged_record_rewrites_nothing(*, tmp_path):
    repo, topic, store = _store_with_row(tmp_path=tmp_path)
    _ = registry.record_context_compaction(
        repo=str(repo), topic=topic, record=_LATCHED, store_path=store
    )
    before = store.read_bytes()

    changed = registry.record_context_compaction(
        repo=str(repo), topic=topic, record=_LATCHED, store_path=store
    )

    # A steady-state tick — watermark already at the lowest reading — must not rewrite
    # the store every ten seconds.
    assert changed is False
    assert store.read_bytes() == before


def test_a_cleared_latch_is_persisted_as_a_reopened_record(*, tmp_path):
    repo, topic, store = _store_with_row(tmp_path=tmp_path)
    _ = registry.record_context_compaction(
        repo=str(repo), topic=topic, record=_LATCHED, store_path=store
    )
    successor = registry.ContextCompaction(session_identity="codex:successor", watermark_ctx=95)

    _ = registry.record_context_compaction(
        repo=str(repo), topic=topic, record=successor, store_path=store
    )

    stored = _row_for(store=store, topic=topic).context_compaction
    assert stored == successor
    assert stored is not None and stored.restart_required is False


def test_a_malformed_record_is_dropped_rather_than_half_read(*, tmp_path):
    repo, topic, store = _store_with_row(tmp_path=tmp_path)
    rows = store.read_text(encoding="utf-8").splitlines()
    store.write_text(
        rows[0].replace("}", ', "context_compaction": {"latched_at": "yesterday"}}') + "\n",
        encoding="utf-8",
    )
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        track = _row_for(store=store, topic=topic)

    # Fail-soft in the SAFE direction: a corrupt sidecar must never manufacture a
    # restart obligation the daemon never observed.
    assert track.context_compaction is None
    assert "dropping malformed context_compaction" in err.getvalue()
    assert str(repo) in err.getvalue()


def test_an_unrecognised_member_is_refused_as_malformed(*, tmp_path):
    repo, topic, store = _store_with_row(tmp_path=tmp_path)
    line = store.read_text(encoding="utf-8").splitlines()[0]
    payload = (
        '"context_compaction": {"session_identity": "codex:x", "watermark_ctx": 9, '
        '"latched_at": null, "from_ctx": null, "to_ctx": null, "surprise": 1}'
    )
    store.write_text(line.replace("}", ", " + payload + "}") + "\n", encoding="utf-8")
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        track = _row_for(store=store, topic=topic)

    assert track.context_compaction is None
    assert str(repo) in err.getvalue()


def test_a_non_object_value_is_refused_as_malformed(*, tmp_path):
    _repo, topic, store = _store_with_row(tmp_path=tmp_path)
    line = store.read_text(encoding="utf-8").splitlines()[0]
    store.write_text(line.replace("}", ', "context_compaction": 7}') + "\n", encoding="utf-8")
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        track = _row_for(store=store, topic=topic)

    assert track.context_compaction is None


def test_the_record_rides_a_direct_track_construction(*, tmp_path):
    del tmp_path
    track = registry.Track(
        topic="topic",
        repo="/x/repo",
        tmux="topic",
        epic="overseer-test-epic",
        context_compaction=_LATCHED,
    )

    assert track.context_compaction == _LATCHED
    assert registry.Track(topic="t", repo="/x/r", tmux="t", epic="e").context_compaction is None


def test_an_unassigned_plan_carries_no_compaction_record():
    plan = registry.Track.make_unassigned(repo="/x/repo", topic="topic")

    # A discovered plan with no session has no context generation to have compacted,
    # so the answer is absence rather than an empty record — the same shape every other
    # session-derived field on this variant reports.
    assert plan.context_compaction is None
