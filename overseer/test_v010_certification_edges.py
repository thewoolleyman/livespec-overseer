"""Focused edge coverage for v010 ready certification-floor mechanics."""

from __future__ import annotations

import json
from pathlib import Path

import _supervisor_ready
import _supervisor_state
import _supervisor_threshold
import codex_sessions
import registry
import signals
from _supervisor_records import InjectState, Observation
from test_supervisor_builders import (
    busy_capture,
    codex_busy_capture,
    declare,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _declared_ready(*, repo, topic, mtime=1001.0):
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=mtime)
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    return state


def test_ready_session_identity_unknown_runtime_fails_closed(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    assert (
        _supervisor_ready.session_identity(
            sup=sup, session="session", topic=topic, runtime="unknown"
        )
        is None
    )
    assert repo.exists()


def test_ready_uncertifiable_names_malformed_round_record(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    stamp_path = Path(sup.stamp_path)
    stamp_path.write_text(
        json.dumps({f"{repo}\t{topic}": {"at": 1000.0, "bands": []}}),
        encoding="utf-8",
    )

    obs = _supervisor_ready.round_observation(
        sup=sup,
        repo=str(repo),
        topic=topic,
        session="session",
        runtime="claude",
        declared=_declared_ready(repo=repo, topic=topic),
    )

    assert obs.ready is False
    assert obs.ready_uncertifiable_reason == "round record missing session identity"


def test_ready_uncertifiable_names_missing_live_codex_identity(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity="codex:abc",
        stamp_path=sup.stamp_path,
    )

    obs = _supervisor_ready.round_observation(
        sup=sup,
        repo=str(repo),
        topic=topic,
        session="session",
        runtime="codex",
        declared=_declared_ready(repo=repo, topic=topic),
    )

    assert obs.ready is False
    assert obs.ready_uncertifiable_reason == "session identity cannot be determined"


def test_codex_ready_void_records_floor_for_matching_live_identity(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=codex_busy_capture(ctx=40), cmd="bun")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=100,
            name=topic,
            cwd=str(repo),
            session_id="codex-session",
        )
    }
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=700.0,
        session_identity="codex:codex-session",
        stamp_path=sup.stamp_path,
    )
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=800.0)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "working"
    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert record.voided_at is not None


def test_ready_void_without_round_identity_skips_live_identity_comparison(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    stamp_path = Path(sup.stamp_path)
    stamp_path.write_text(json.dumps({f"{repo}\t{topic}": 700.0}), encoding="utf-8")
    state = _declared_ready(repo=repo, topic=topic, mtime=800.0)

    assert _supervisor_state._record_ready_void(sup=sup, track=track, state=state) is False


def test_threshold_settles_when_fresh_authorization_check_fails_closed(*, tmp_path, monkeypatch):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    record = registry.RoundRecord(
        at=None,
        bands=[],
        voided_at=None,
        session_identity=None,
        malformed_reason=None,
    )
    base = Observation(
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
        injection_stamp=None,
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
    fresh = Observation(
        capture=base.capture,
        busy=False,
        gate=False,
        idle=True,
        is_codex=False,
        runtime="claude",
        codex_fallback=False,
        claude_status="idle",
        current_ctx=None,
        eff_ctx=None,
        ctx_stale_age=None,
        stale_ctx=None,
        injection_stamp=None,
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
    monkeypatch.setattr(_supervisor_threshold._supervisor_observe, "observe", lambda **_kw: fresh)
    monkeypatch.setattr(
        _supervisor_threshold._supervisor_observe,
        "pane_is_managed",
        lambda **_kw: True,
    )

    decision = _supervisor_threshold.threshold(
        request=_supervisor_threshold.ThresholdRequest(
            sup=sup,
            track=track,
            session=session,
            target=session,
            threshold=40,
            act=True,
            obs=base,
        )
    )

    assert decision.status == "settling"
