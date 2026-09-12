"""The ruled context-compaction contract, end to end over its durable record.

Maintainer ruling 2026-09-12 (`overseer-nb7ok7`): an in-place context compaction is a
FAILED, exhausted context generation, not a recovery, because its summarized state is
not acceptable as clean continuation. Once detected the track stays restart-required —
for Codex and for Claude alike — at any later context percentage, until the ordinary
cooperative wind-down and a fresh-session restart succeed.

This is the top-of-pyramid statement of that contract: it walks a track's whole
context-generation lifecycle through the DURABLE record, because "survives a daemon
restart" is a property of the store rather than of any one tick. The per-tick cascade
behaviour, both complete runtime sequences, and the zero-respawn safety controls are
driven by the beside-tests in `overseer/test_supervisor_compaction_*.py`.
"""

from __future__ import annotations

import _supervisor_compaction
import registry

__all__: list[str] = []

CODEX_PREDECESSOR = "codex:019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
CODEX_SUCCESSOR = "codex:019f7b2f-3771-7ad3-9fc3-26fda0435ca9"
CLAUDE_PREDECESSOR = "claude:101:12345:topic"
CLAUDE_SUCCESSOR = "claude:4242:67890:topic"
THRESHOLD = 50


def _fold(*, stored, identity, ctx, now=1000.0):
    return _supervisor_compaction.observe_compaction(
        stored=stored, session_identity=identity, current_ctx=ctx, now=now
    )


def _run(*, identity, readings, stored=None):
    """Replay a sequence of readings under one identity, returning the last transition."""
    transition = _supervisor_compaction.observe_compaction(
        stored=stored, session_identity=identity, current_ctx=readings[0], now=1000.0
    )
    for offset, ctx in enumerate(readings[1:], start=1):
        transition = _fold(
            stored=transition.record, identity=identity, ctx=ctx, now=1000.0 + offset
        )
    return transition


def _store_with_track(*, tmp_path, repo="/x/repo", topic="topic"):
    store = tmp_path / "map.jsonl"
    registry.append_mapping(
        track=registry.PlanTrack(repo=repo, topic=topic, tmux=topic, epic="overseer-test-epic"),
        store_path=store,
        added_at="2026-09-12T00:00:00Z",
    )
    return store


def _reload(*, store, topic="topic"):
    for track in registry.read_valid_mapping(store_path=store):
        if track.topic == topic:
            return track
    raise AssertionError(f"no mapping row for {topic}")


def test_an_in_place_compaction_latches_a_restart_for_a_codex_track():
    """The measured 2026-09-11 shape: below the line, compacted, back above it."""
    transition = _run(identity=CODEX_PREDECESSOR, readings=[64, 45, 6, 78])

    assert transition.detected is True
    assert transition.restart_required is True
    assert (transition.record.from_ctx, transition.record.to_ctx) == (6, 78)


def test_an_in_place_compaction_latches_a_restart_for_a_claude_track():
    """The SAME detector, the same ruling — nothing about it is Codex-specific."""
    transition = _run(identity=CLAUDE_PREDECESSOR, readings=[64, 45, 6, 78])

    assert transition.detected is True
    assert transition.restart_required is True
    assert (transition.record.from_ctx, transition.record.to_ctx) == (6, 78)


def test_the_latch_still_owes_a_wind_down_at_a_healthy_percentage():
    latched = _run(identity=CODEX_PREDECESSOR, readings=[64, 6, 78, 77])

    # The whole ruling in one assertion: 77% is far above the threshold and the
    # wind-down is STILL owed, because that 77% describes a summarized generation the
    # daemon never accepted as a continuation.
    assert latched.restart_required is True
    assert _supervisor_compaction.wind_down_owed(
        compaction=latched, eff_ctx=77, threshold=THRESHOLD
    )
    # And it selects a real escalation band rather than none at all.
    assert (
        _supervisor_compaction.injection_ctx(compaction=latched, eff_ctx=77, threshold=THRESHOLD)
        == THRESHOLD
    )


def test_a_new_successor_session_is_a_completed_restart_not_a_compaction():
    """THE control. A restart and a compaction show identical CONTEXT evidence."""
    latched = _run(identity=CODEX_PREDECESSOR, readings=[64, 6, 78])

    successor = _fold(stored=latched.record, identity=CODEX_SUCCESSOR, ctx=95)

    assert successor.successor is True
    assert successor.detected is False
    assert successor.restart_required is False
    assert successor.record.session_identity == CODEX_SUCCESSOR
    assert not _supervisor_compaction.wind_down_owed(
        compaction=successor, eff_ctx=95, threshold=THRESHOLD
    )


def test_the_latch_survives_the_daemon_generation_that_recorded_it(*, tmp_path):
    """Durability is the point: an in-memory latch would die with the daemon."""
    store = _store_with_track(tmp_path=tmp_path)
    latched = _run(identity=CLAUDE_PREDECESSOR, readings=[64, 6, 78])

    changed = registry.record_context_compaction(
        repo="/x/repo", topic="topic", record=latched.record, store_path=store
    )

    assert changed is True
    # Re-read through the ordinary mapping reader — the surface a FRESH daemon
    # generation uses at cold start, which is what makes this the bounce proof.
    reloaded = _reload(store=store).context_compaction
    assert reloaded is not None
    assert reloaded.restart_required is True
    assert (reloaded.from_ctx, reloaded.to_ctx) == (6, 78)
    # And a resumed fold over that reloaded record still owes the restart.
    assert _fold(stored=reloaded, identity=CLAUDE_PREDECESSOR, ctx=76).restart_required is True


def test_adopting_a_fresh_session_discharges_the_persisted_obligation(*, tmp_path):
    store = _store_with_track(tmp_path=tmp_path)
    latched = _run(identity=CLAUDE_PREDECESSOR, readings=[64, 6, 78])
    _ = registry.record_context_compaction(
        repo="/x/repo", topic="topic", record=latched.record, store_path=store
    )

    discharged = _fold(
        stored=_reload(store=store).context_compaction, identity=CLAUDE_SUCCESSOR, ctx=96
    )
    _ = registry.record_context_compaction(
        repo="/x/repo", topic="topic", record=discharged.record, store_path=store
    )

    reloaded = _reload(store=store).context_compaction
    assert reloaded is not None
    assert reloaded.restart_required is False
    assert reloaded.session_identity == CLAUDE_SUCCESSOR
    assert reloaded.watermark_ctx == 96


def test_an_unprovable_observation_neither_latches_nor_clears():
    latched = _run(identity=CODEX_PREDECESSOR, readings=[64, 6, 78])

    blind = _fold(stored=latched.record, identity=None, ctx=95)
    unreadable = _fold(stored=latched.record, identity=CODEX_PREDECESSOR, ctx=None)

    # Fail-closed BOTH ways: an unresolvable session must not discharge a real
    # obligation, and an unreadable statusline must not manufacture one.
    for transition in (blind, unreadable):
        assert transition.record == latched.record
        assert transition.detected is False
        assert transition.successor is False
