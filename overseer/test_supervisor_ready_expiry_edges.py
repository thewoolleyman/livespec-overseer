"""Focused edge coverage for v016 ready-expiry mechanics."""

from __future__ import annotations

import _supervisor_config
import _supervisor_state
import _supervisor_threshold
import codex_sessions
import registry
import signals
from _supervisor_records import InjectState, Observation
from test_supervisor_builders import (
    busy_capture,
    declare,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

MAX_AGE = _supervisor_config.READY_ARM_MAX_AGE


def _aged_round(*, tmp_path, identity="claude:topic:topic"):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    clock = {"t": 1001.0 + MAX_AGE + 1.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=identity,
        stamp_path=sup.stamp_path,
    )
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    return repo, topic, session, sup, track


def test_expiry_whose_floor_record_and_diagnostic_both_fail_is_surfaced(*, tmp_path, monkeypatch):
    """Both writes are fail-soft storage operations. When BOTH fail in the same
    observation the declaration survives with an unraised floor, and that outcome is
    surfaced as an attention condition rather than described as impossible."""
    repo, topic, session, sup, track = _aged_round(tmp_path=tmp_path)
    monkeypatch.setattr(_supervisor_state.registry, "record_ready_expiry", lambda **_kw: False)
    monkeypatch.setattr(_supervisor_state, "write_state_diagnostic", lambda **_kw: False)

    assert _supervisor_state.expire_aged_ready(sup=sup, track=track) is True

    conditions = {key[2] for key in sup.alerted}
    assert "ready-expiry-both-writes-failed" in conditions
    assert signals.read_state(repo=str(repo), topic=topic) is not None


def test_a_floor_record_that_raises_is_logged_and_never_aborts_the_delete(
    *, tmp_path, monkeypatch, capsys
):
    repo, topic, session, sup, track = _aged_round(tmp_path=tmp_path)

    def _raise(**_kw):
        raise OSError("sidecar is read-only")

    monkeypatch.setattr(_supervisor_state.registry, "record_ready_expiry", _raise)

    assert _supervisor_state.expire_aged_ready(sup=sup, track=track) is True

    assert "could not record ready expiry" in capsys.readouterr().err
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_READY_EXPIRED


def test_a_codex_pane_expires_against_its_live_codex_identity(*, tmp_path):
    repo, topic, session, sup, track = _aged_round(tmp_path=tmp_path, identity="codex:live-a")
    sup.live_codex[(session, topic)] = codex_sessions.CodexSession(
        pid=1234, name=topic, cwd=str(repo), session_id="live-a"
    )

    assert _supervisor_state.expire_aged_ready(sup=sup, track=track) is True

    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert record.expired_at == 1001.0 + MAX_AGE


def test_expiry_notice_is_refused_when_the_fresh_re_read_disagrees(*, tmp_path, monkeypatch):
    """The notice re-reads every paste authorization input immediately before acting;
    a pane that is no longer a verified settled-idle prompt refuses the paste."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    record = registry.RoundRecord(
        at=1000.0,
        bands=[],
        expired_at=1000.0 + MAX_AGE,
        session_identity="claude:session:topic",
        malformed_reason=None,
    )
    due = Observation(
        capture=busy_capture(ctx=40),
        busy=False,
        gate=False,
        idle=True,
        is_codex=False,
        runtime="claude",
        codex_fallback=False,
        claude_status="idle",
        current_ctx=40,
        eff_ctx=40,
        ctx_stale_age=None,
        stale_ctx=None,
        injection_stamp=1000.0,
        observed_at=1000.0,
        round_record=record,
        session_identity="claude:session:topic",
        ready_uncertifiable_reason=None,
        istate=InjectState(),
        declared=None,
        malformed=False,
        blocked=None,
        acked=False,
        ready=False,
    )
    monkeypatch.setattr(
        _supervisor_threshold._supervisor_observe, "pane_is_managed", lambda **_kw: False
    )

    sent = _supervisor_threshold.maybe_send_expiry_notice(
        request=_supervisor_threshold.ThresholdRequest(
            sup=sup,
            track=track,
            session=session,
            target=session,
            threshold=40,
            act=True,
            obs=due,
        )
    )

    assert sent is False
    assert fake.paste_texts() == []
