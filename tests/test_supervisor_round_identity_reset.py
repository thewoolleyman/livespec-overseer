"""Round reset coverage for out-of-band session identity turnover."""

from __future__ import annotations

import _supervisor_observe
import _supervisor_round_recovery
import pytest
import registry
import signals

from overseer.test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
)
from overseer.test_supervisor_fakes import FakeTmux

PREDECESSOR = "claude:1521187:354055360:livespec-overseer-foreman"
SUCCESSOR = "claude:2407774:357160598:livespec-overseer-foreman"


def _record(*, repo, topic, sup):
    return registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)


def _open_measured_foreman_round(*, sup, repo, topic):
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1787195850.0,
        session_identity=PREDECESSOR,
        stamp_path=sup.stamp_path,
    )
    registry.add_notified_band(repo=str(repo), topic=topic, band=50, stamp_path=sup.stamp_path)
    assert registry.record_ready_expiry(
        repo=str(repo),
        topic=topic,
        expiry_instant=1787199302.0,
        stamp_path=sup.stamp_path,
    )
    assert registry.mark_expiry_notice_sent(
        repo=str(repo),
        topic=topic,
        stamp_path=sup.stamp_path,
    )


def _entity_track(*, repo, topic, session, kind):
    if kind == "foreman":
        return registry.ForemanSeat(
            topic=topic,
            repo=str(repo),
            tmux=session,
            epic="overseer-foreman-epic",
        )
    if kind == "grooming":
        return registry.GroomingSeat(
            topic=topic,
            repo=str(repo),
            tmux=session,
            epic="overseer-grooming-epic",
        )
    return registry.SupervisorSeat(
        topic=topic,
        repo=str(repo),
        tmux=session,
        epic="overseer-supervisor-epic",
        supervised_topic="topic",
    )


def _entity_fixture(
    *,
    tmp_path,
    kind,
    ctx=80,
    topic=None,
    state_token=None,
    live_identity=None,
):
    repo, topic = make_plan(tmp_path=tmp_path, topic=topic or f"repo-{kind}")
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx, topic=topic))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = _entity_track(repo=repo, topic=topic, session=session, kind=kind)
    _open_measured_foreman_round(sup=sup, repo=repo, topic=topic)
    if state_token is not None:
        declare(repo=repo, topic=topic, value=state_token, mtime=1787201194.0)
    if live_identity is not None:
        sup.claude_identity_by_session[(session, topic)] = live_identity
    obs = _supervisor_observe.observe(
        sup=sup,
        track=track,
        session=session,
        target=session,
        key=(str(repo), topic),
    )
    request = _supervisor_round_recovery.RecoveryRequest(
        sup=sup,
        track=track,
        obs=obs,
        session=session,
        target=session,
        threshold=50,
    )
    return repo, topic, fake, sup, track, request


@pytest.mark.parametrize("kind", ["foreman", "grooming", "supervisor"])
def test_entity_seats_close_recovered_rounds_with_no_session_token(*, tmp_path, kind):
    repo, topic, fake, sup, _track, request = _entity_fixture(
        tmp_path=tmp_path,
        kind=kind,
        state_token=signals.STATE_READY_EXPIRED,
    )

    assert _supervisor_round_recovery.close_recovered_round(request=request) is True

    record = _record(repo=repo, topic=topic, sup=sup)
    assert record.at is None
    assert record.bands == []
    assert record.expired_at is None
    assert record.session_identity is None
    assert record.expiry_notice_sent is False
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")


def test_measured_foreman_successor_identity_resets_stale_daemon_written_round(*, tmp_path):
    repo, topic, _fake, sup, _track, request = _entity_fixture(
        tmp_path=tmp_path,
        kind="foreman",
        ctx=14,
        topic="livespec-overseer-foreman",
        state_token=signals.STATE_READY_EXPIRED,
        live_identity=SUCCESSOR,
    )
    stale = _record(repo=repo, topic=topic, sup=sup)
    assert stale.at == 1787195850.0
    assert stale.bands == [50]
    assert stale.session_identity == PREDECESSOR
    assert stale.expired_at == 1787199302.0
    assert stale.expiry_notice_sent is True

    assert _supervisor_round_recovery.close_recovered_round(request=request) is True

    reset = _record(repo=repo, topic=topic, sup=sup)
    assert reset.at is None
    assert reset.bands == []
    assert reset.session_identity is None
    assert reset.expired_at is None
    assert reset.expiry_notice_sent is False
    assert SUCCESSOR in sup.out.getvalue()
    assert PREDECESSOR in sup.out.getvalue()


def test_below_threshold_identity_reset_opens_current_session_round(*, tmp_path):
    repo, topic, fake, sup, track, _request = _entity_fixture(
        tmp_path=tmp_path,
        kind="foreman",
        ctx=14,
        topic="livespec-overseer-foreman",
        state_token=signals.STATE_READY_EXPIRED,
        live_identity=SUCCESSOR,
    )

    view = sup.evaluate(track=track, act=True)

    record = _record(repo=repo, topic=topic, sup=sup)
    assert view.status == "danger"
    assert record.at == 1000.0
    assert record.bands == [50]
    assert record.expired_at is None
    assert record.session_identity == SUCCESSOR
    assert record.expiry_notice_sent is False
    assert len(fake.paste_texts()) == 1


def test_matching_identity_does_not_reset_below_threshold_round(*, tmp_path):
    repo, topic, _fake, sup, _track, request = _entity_fixture(
        tmp_path=tmp_path,
        kind="foreman",
        ctx=14,
        topic="livespec-overseer-foreman",
        state_token=signals.STATE_READY_EXPIRED,
        live_identity=PREDECESSOR,
    )

    assert _supervisor_round_recovery.close_recovered_round(request=request) is False

    record = _record(repo=repo, topic=topic, sup=sup)
    assert record.at == 1787195850.0
    assert record.bands == [50]
    assert record.session_identity == PREDECESSOR


def test_successor_ready_declaration_keeps_identity_refusal_surface(*, tmp_path):
    repo, topic, _fake, sup, _track, request = _entity_fixture(
        tmp_path=tmp_path,
        kind="foreman",
        ctx=14,
        topic="livespec-overseer-foreman",
        state_token=signals.STATE_READY,
        live_identity=SUCCESSOR,
    )

    assert _supervisor_round_recovery.close_recovered_round(request=request) is False

    record = _record(repo=repo, topic=topic, sup=sup)
    assert record.at == 1787195850.0
    assert record.session_identity == PREDECESSOR
    assert request.obs.ready_uncertifiable_reason is not None
    assert (
        "session identity differs from round-open identity"
        in request.obs.ready_uncertifiable_reason
    )
