"""Beside-tests for the runtime-neutral in-place compaction detector.

The transition is a pure function of (durable record, live session identity, current
reading), which is what makes it runtime-neutral: nothing below mentions Codex or
Claude, and the cascade tests beside these prove both runtimes drive it.
"""

from __future__ import annotations

import _supervisor_compaction
import registry

__all__: list[str] = []

_IDENTITY = "codex:019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
_SUCCESSOR = "codex:019f7b2f-3771-7ad3-9fc3-26fda0435ca9"


def _fold(*, stored, ctx, identity=_IDENTITY, now=1000.0):
    return _supervisor_compaction.observe_compaction(
        stored=stored, session_identity=identity, current_ctx=ctx, now=now
    )


def _opened(*, ctx, identity=_IDENTITY):
    return _fold(stored=None, ctx=ctx, identity=identity).record


def test_a_first_reading_opens_the_record_without_claiming_a_restart_completed():
    transition = _fold(stored=None, ctx=64)

    assert transition.record.session_identity == _IDENTITY
    assert transition.record.watermark_ctx == 64
    assert transition.restart_required is False
    assert transition.detected is False
    # A record that never had an owner is being opened, not replaced. Calling that a
    # successor would log a completed restart for every track the daemon ever sees.
    assert transition.successor is False


def test_the_watermark_follows_the_reading_down_and_never_back_up_on_noise():
    record = _opened(ctx=64)

    record = _fold(stored=record, ctx=51).record
    # A wobble inside the tolerance band is instrument noise, not a replenished window:
    # the floor stays where the lowest real reading put it.
    transition = _fold(stored=record, ctx=51 + _supervisor_compaction.COMPACTION_CTX_RISE)

    assert transition.record.watermark_ctx == 51
    assert transition.restart_required is False
    assert transition.detected is False


def test_a_rise_past_the_band_under_the_same_session_latches_a_restart_obligation():
    record = _fold(stored=_opened(ctx=64), ctx=6).record

    transition = _fold(stored=record, ctx=78, now=1234.0)

    assert transition.detected is True
    assert transition.restart_required is True
    assert transition.record.latched_at == 1234.0
    assert (transition.record.from_ctx, transition.record.to_ctx) == (6, 78)
    # Re-floored to the post-compaction reading, so a SECOND compaction is still a rise.
    assert transition.record.watermark_ctx == 78


def test_a_healthy_reading_after_the_latch_neither_clears_it_nor_re_reports_it():
    latched = _fold(stored=_fold(stored=_opened(ctx=64), ctx=6).record, ctx=78).record

    transition = _fold(stored=latched, ctx=77)

    assert transition.restart_required is True
    assert transition.detected is False
    assert (transition.record.from_ctx, transition.record.to_ctx) == (6, 78)


def test_a_second_compaction_keeps_the_first_failures_evidence_and_does_not_re_alert():
    latched = _fold(stored=_fold(stored=_opened(ctx=64), ctx=6).record, ctx=78, now=100.0).record
    drained = _fold(stored=latched, ctx=9).record

    transition = _fold(stored=drained, ctx=81, now=900.0)

    assert transition.restart_required is True
    # Already owed: re-dating the obligation would keep moving the failure an operator
    # is trying to read, and re-alerting would make one obligation look like many.
    assert transition.detected is False
    assert transition.record.latched_at == 100.0
    assert (transition.record.from_ctx, transition.record.to_ctx) == (6, 78)


def test_a_new_session_identity_with_a_replenished_window_is_a_completed_restart():
    """THE control: the same replenished reading, under a DIFFERENT session.

    A restart and a compaction present identical context evidence — the number goes
    up. Only the session identity separates them, which is why the detector keys on it
    rather than on the reading alone.
    """
    latched = _fold(stored=_fold(stored=_opened(ctx=64), ctx=6).record, ctx=78).record

    transition = _fold(stored=latched, ctx=95, identity=_SUCCESSOR)

    assert transition.successor is True
    assert transition.detected is False
    assert transition.restart_required is False
    assert transition.record.session_identity == _SUCCESSOR
    assert transition.record.watermark_ctx == 95


def test_an_unprovable_observation_changes_nothing_in_either_direction():
    latched = _fold(stored=_fold(stored=_opened(ctx=64), ctx=6).record, ctx=78).record

    no_identity = _fold(stored=latched, ctx=95, identity=None)
    no_reading = _fold(stored=latched, ctx=None)

    # Fail-closed BOTH ways: an unresolvable session must not clear a real latch, and
    # an unreadable statusline must not manufacture one.
    for transition in (no_identity, no_reading):
        assert transition.record == latched
        assert transition.detected is False
        assert transition.successor is False


def test_the_wind_down_is_owed_below_threshold_or_whenever_the_latch_stands():
    latched = _fold(stored=_fold(stored=_opened(ctx=64), ctx=6).record, ctx=78)
    healthy = _fold(stored=_opened(ctx=64), ctx=64)

    assert _supervisor_compaction.wind_down_owed(compaction=latched, eff_ctx=78, threshold=50)
    assert _supervisor_compaction.wind_down_owed(compaction=healthy, eff_ctx=50, threshold=50)
    assert not _supervisor_compaction.wind_down_owed(compaction=healthy, eff_ctx=64, threshold=50)
    assert not _supervisor_compaction.wind_down_owed(compaction=healthy, eff_ctx=None, threshold=50)


def test_a_latched_track_selects_a_band_by_its_threshold_but_keeps_a_lower_real_one():
    latched = _fold(stored=_fold(stored=_opened(ctx=64), ctx=6).record, ctx=78)
    healthy = _fold(stored=_opened(ctx=64), ctx=64)

    # Unfloored, a replenished 78% selects no escalation band at all and injects nothing.
    assert _supervisor_compaction.injection_ctx(compaction=latched, eff_ctx=78, threshold=50) == 50
    # A latched track that is ALSO genuinely low keeps its sharper band.
    assert _supervisor_compaction.injection_ctx(compaction=latched, eff_ctx=12, threshold=50) == 12
    assert _supervisor_compaction.injection_ctx(compaction=healthy, eff_ctx=78, threshold=50) == 78


def test_the_row_note_and_the_history_evidence_name_the_identity_and_the_transition():
    latched = _fold(stored=_fold(stored=_opened(ctx=64), ctx=6).record, ctx=78)
    healthy = _fold(stored=_opened(ctx=64), ctx=64)

    note = _supervisor_compaction.compaction_note(compaction=latched)
    evidence = _supervisor_compaction.compaction_evidence(record=latched.record)

    assert note is not None and "6%->78%" in note and "restart required" in note
    assert _supervisor_compaction.compaction_note(compaction=healthy) is None
    assert _IDENTITY in evidence
    assert "6% -> 78%" in evidence


def test_the_empty_transition_claims_nothing():
    empty = _supervisor_compaction.NO_COMPACTION_TRANSITION

    assert empty.record == registry.NO_CONTEXT_COMPACTION
    assert empty.restart_required is False
    assert empty.detected is False
    assert empty.successor is False
