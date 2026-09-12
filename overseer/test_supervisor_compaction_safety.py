"""Safety and operator-evidence controls for the context-compaction latch.

The latch is an OBLIGATION, never an authorization. These are the controls that say
so: a latched track that is busy, or idle but undeclared, or carrying a `ready` that
cannot certify, is left exactly as alone as any other track — and the operator
surfaces carry enough evidence to tell the resulting `warned` row from an ordinary
threshold crossing.
"""

from __future__ import annotations

import contextlib
import dataclasses
import io as _io
import pathlib

import _supervisor_evaluate_observation
import _supervisor_observe
import _supervisor_round_recovery
import _supervisor_snapshot
import registry
import signals
from test_supervisor_builders import declare
from test_supervisor_compaction_builders import (
    claude_busy,
    claude_compaction_track,
    claude_idle,
    compaction_record,
    show_pane,
    stored_track,
)

__all__: list[str] = []


def _tick(*, sup, repo, topic, err=None):
    sink = err if err is not None else _io.StringIO()
    with contextlib.redirect_stderr(sink):
        return sup.evaluate(track=stored_track(sup=sup, repo=repo, topic=topic), act=True)


def _latched(*, tmp_path, recovered_ctx=82):
    repo, topic, session, fake, sup = claude_compaction_track(tmp_path=tmp_path, ctx=45)
    _ = _tick(sup=sup, repo=repo, topic=topic)
    show_pane(fake=fake, session=session, capture=claude_busy(ctx=recovered_ctx))
    _ = _tick(sup=sup, repo=repo, topic=topic)
    record = compaction_record(sup=sup, repo=repo, topic=topic)
    assert record is not None and record.restart_required is True
    return repo, topic, session, fake, sup


def test_a_latched_track_is_never_respawned_while_busy(*, tmp_path):
    repo, topic, _session, fake, sup = _latched(tmp_path=tmp_path)

    for _ in range(10):
        assert _tick(sup=sup, repo=repo, topic=topic).status == "working"

    # The obligation is durable and standing, and it buys the daemon nothing: a busy
    # pane may not be pasted into and may certainly not be killed.
    assert not fake.has(method="respawn")
    assert not fake.has(method="paste")


def test_a_latched_track_is_never_respawned_while_idle_and_undeclared(*, tmp_path):
    repo, topic, session, fake, sup = _latched(tmp_path=tmp_path)
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=82))

    for _ in range(10):
        view = _tick(sup=sup, repo=repo, topic=topic)

    assert view.status == "warned"
    # The escalation IS the whole lever. A session that declares nothing is reported,
    # never restarted — the latch does not reopen the force-restart this repo deleted.
    assert fake.has(method="paste")
    assert not fake.has(method="respawn")
    assert not signals.state_path(repo=str(repo), topic=topic).exists()


def test_only_a_fresh_certifiable_ready_reaches_the_restart_surface(*, tmp_path):
    repo, topic, session, fake, sup = _latched(tmp_path=tmp_path)
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=82))
    _ = _tick(sup=sup, repo=repo, topic=topic)
    stamp = registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert stamp is not None

    # A `ready` that PREDATES this round's certification floor is exactly the stale
    # declaration the interlock exists to refuse. A standing latch must not promote it.
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=stamp - 1.0)
    stale = _tick(sup=sup, repo=repo, topic=topic)
    assert stale.status != "restarting"
    assert not fake.has(method="respawn")

    # The discriminating control: the SAME latched track, with a certifiable ready.
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=stamp + 1.0)
    assert _tick(sup=sup, repo=repo, topic=topic).status == "restarting"
    assert fake.has(method="respawn")


def _closes_round(*, sup, track, session):
    return _supervisor_round_recovery.close_recovered_round(
        request=_supervisor_round_recovery.RecoveryRequest(
            sup=sup,
            track=track,
            obs=_supervisor_observe.observe(
                sup=sup,
                track=track,
                session=session,
                target=session,
                key=(registry.norm(repo=track.repo), track.topic),
            ),
            session=session,
            target=session,
            threshold=50,
        )
    )


def _unlatched(*, track):
    """The same track and the same watermark, with the obligation removed."""
    held = track.context_compaction
    assert held is not None
    return dataclasses.replace(
        track,
        context_compaction=registry.ContextCompaction(
            session_identity=held.session_identity, watermark_ctx=held.watermark_ctx
        ),
    )


def test_a_latched_round_is_not_closed_by_a_healthy_post_compaction_reading(*, tmp_path):
    repo, topic, session, fake, sup = _latched(tmp_path=tmp_path)
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=82))
    _ = _tick(sup=sup, repo=repo, topic=topic)
    track = stored_track(sup=sup, repo=repo, topic=topic)

    latched_closed = _closes_round(sup=sup, track=track, session=session)
    # The discriminating control: the IDENTICAL 82% reading on a track carrying no
    # latch still closes the round as recovered. The recovery arm is gated, not broken
    # — which is the whole difference between this fix and disabling that arm.
    unlatched_closed = _closes_round(sup=sup, track=_unlatched(track=track), session=session)

    assert latched_closed is False
    assert unlatched_closed is True
    assert not fake.has(method="respawn")


def test_the_snapshot_tells_a_latched_failure_from_an_ordinary_threshold_warning(*, tmp_path):
    repo, topic, session, fake, sup = _latched(tmp_path=tmp_path)
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=82))
    view = _tick(sup=sup, repo=repo, topic=topic)

    payload = _supervisor_snapshot.row_payload(sup=sup, row=view)

    assert view.status == "warned"  # indistinguishable from an ordinary crossing here
    compaction = payload["context_compaction"]
    assert isinstance(compaction, dict)
    assert compaction["restart_required"] is True
    assert compaction["from_ctx"] == 45
    assert compaction["to_ctx"] == 82
    # The session identity is what proves the 82% belongs to a DIFFERENT generation
    # than the 45% the daemon had been winding down.
    assert compaction["session_identity"] == f"claude:{session}:{topic}"
    assert compaction["latched_at"] is not None


def test_an_untouched_track_carries_no_compaction_payload(*, tmp_path):
    repo, topic, session, fake, sup = claude_compaction_track(tmp_path=tmp_path, ctx=45)
    show_pane(fake=fake, session=session, capture=claude_idle(ctx=45))
    view = _tick(sup=sup, repo=repo, topic=topic)

    payload = _supervisor_snapshot.row_payload(sup=sup, row=view)

    assert payload["context_compaction"] is not None  # a record is opened on sight
    compaction = payload["context_compaction"]
    assert isinstance(compaction, dict)
    assert compaction["restart_required"] is False
    assert compaction["latched_at"] is None


def test_the_read_only_list_path_never_writes_the_record(*, tmp_path):
    repo, topic, session, fake, sup = claude_compaction_track(tmp_path=tmp_path, ctx=45)
    show_pane(fake=fake, session=session, capture=claude_busy(ctx=82))
    store = pathlib.Path(sup.store_path)
    before = store.read_bytes()

    with contextlib.redirect_stderr(_io.StringIO()):
        _ = sup.evaluate(track=stored_track(sup=sup, repo=repo, topic=topic), act=False)

    # `list` classifies; it must not mutate the operator's store — and it must not
    # silently spend the one detection edge an acting tick would have alerted on.
    assert store.read_bytes() == before
    assert compaction_record(sup=sup, repo=repo, topic=topic) is None
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")
    assert session in sup.tmux.sessions


def test_an_unnameable_session_records_no_identity_but_still_records_the_generation(*, tmp_path):
    """The two durable writes are independent, and they answer different questions.

    `observed_session_identity` is what a dead-track recovery later reads to know which
    runtime to revive, so recording nothing is the honest answer when the daemon cannot
    name the session. The context-generation record is keyed on the LIVE identity the
    fold already resolved, so it is unaffected — and writing one must never be made
    conditional on the other.
    """
    repo, topic, session, fake, sup = claude_compaction_track(tmp_path=tmp_path, ctx=45)
    del fake
    track = stored_track(sup=sup, repo=repo, topic=topic)
    observed = _supervisor_observe.observe(
        sup=sup,
        track=track,
        session=session,
        target=session,
        key=(registry.norm(repo=track.repo), topic),
    )

    _supervisor_evaluate_observation.record_tick_observations(
        request=_supervisor_evaluate_observation.RecordObservationRequest(
            sup=sup,
            track=track,
            obs=dataclasses.replace(observed, session_identity=None),
            session=session,
            pane=session,
            act=True,
        )
    )

    reloaded = stored_track(sup=sup, repo=repo, topic=topic)
    assert reloaded.observed_session_identity is None
    assert reloaded.context_compaction is not None
    assert reloaded.context_compaction.watermark_ctx == 45
