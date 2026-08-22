"""Focused coverage for fresh guarded paste refusal clauses."""

from __future__ import annotations

from itertools import count

import _supervisor_threshold
import _supervisor_threshold_expiry
import registry
import signals
from _supervisor_records import InjectState, Observation
from test_supervisor_builders import idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_REQUEST_IDS = count()


def _observation(*, eff_ctx: int = 40, **overrides) -> Observation:
    values = {
        "capture": idle_capture(ctx=eff_ctx),
        "busy": False,
        "gate": False,
        "idle": True,
        "is_codex": False,
        "runtime": "claude",
        "codex_fallback": False,
        "claude_status": "idle",
        "current_ctx": eff_ctx,
        "eff_ctx": eff_ctx,
        "ctx_stale_age": None,
        "stale_ctx": None,
        "injection_stamp": None,
        "round_record": registry.RoundRecord(
            at=None,
            bands=[],
            expired_at=None,
            session_identity=None,
            malformed_reason=None,
        ),
        "session_identity": "claude:session:topic",
        "ready_uncertifiable_reason": None,
        "istate": InjectState(),
        "observed_at": 1000.0,
        "declared": None,
        "malformed": False,
        "blocked": None,
        "acked": False,
        "ready": False,
    }
    values.update(overrides)
    return Observation(**values)


def _request(*, tmp_path, obs: Observation) -> _supervisor_threshold.ThresholdRequest:
    repo, topic = make_plan(tmp_path=tmp_path, repo_name=f"repo-{next(_REQUEST_IDS)}")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    return _supervisor_threshold.ThresholdRequest(
        sup=sup,
        track=mapped_track(repo=repo, topic=topic, session=session),
        session=session,
        target=session,
        threshold=40,
        act=True,
        obs=obs,
    )


def _guard_result(*, tmp_path, monkeypatch, obs: Observation, require_below_threshold: bool):
    request = _request(tmp_path=tmp_path, obs=obs)
    monkeypatch.setattr(
        _supervisor_threshold_expiry._supervisor_observe,
        "pane_is_managed",
        lambda **_kw: True,
    )
    monkeypatch.setattr(
        _supervisor_threshold_expiry._supervisor_observe,
        "observe",
        lambda **_kw: obs,
    )
    return _supervisor_threshold_expiry.fresh_guarded_paste_observation(
        request=request,
        require_below_threshold=require_below_threshold,
    )


def _assert_clause_refuses(*, tmp_path, monkeypatch, obs: Observation) -> None:
    assert (
        _guard_result(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            obs=_observation(),
            require_below_threshold=True,
        )
        is not None
    )
    assert (
        _guard_result(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            obs=obs,
            require_below_threshold=True,
        )
        is None
    )


def test_guarded_paste_refuses_context_over_threshold(*, tmp_path, monkeypatch):
    assert (
        _guard_result(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            obs=_observation(eff_ctx=41, current_ctx=41, capture=idle_capture(ctx=41)),
            require_below_threshold=False,
        )
        is not None
    )
    assert (
        _guard_result(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            obs=_observation(eff_ctx=41, current_ctx=41, capture=idle_capture(ctx=41)),
            require_below_threshold=True,
        )
        is None
    )


def test_guarded_paste_refuses_not_idle(*, tmp_path, monkeypatch):
    _assert_clause_refuses(tmp_path=tmp_path, monkeypatch=monkeypatch, obs=_observation(idle=False))


def test_guarded_paste_refuses_gate(*, tmp_path, monkeypatch):
    _assert_clause_refuses(tmp_path=tmp_path, monkeypatch=monkeypatch, obs=_observation(gate=True))


def test_guarded_paste_refuses_generating(*, tmp_path, monkeypatch):
    _assert_clause_refuses(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        obs=_observation(claude_status="busy"),
    )


def test_guarded_paste_refuses_busy_without_shell_only(*, tmp_path, monkeypatch):
    _assert_clause_refuses(tmp_path=tmp_path, monkeypatch=monkeypatch, obs=_observation(busy=True))


def test_guarded_paste_refuses_waiting_status(*, tmp_path, monkeypatch):
    _assert_clause_refuses(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        obs=_observation(claude_status="waiting"),
    )


def test_guarded_paste_refuses_blocked_declaration(*, tmp_path, monkeypatch):
    declared = signals.TrackState(token=signals.STATE_BLOCKED, detail="needs human", mtime=1000.0)
    _assert_clause_refuses(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        obs=_observation(declared=declared),
    )


def test_guarded_paste_refuses_ready_declaration(*, tmp_path, monkeypatch):
    declared = signals.TrackState(token=signals.STATE_READY, detail="", mtime=1000.0)
    _assert_clause_refuses(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        obs=_observation(declared=declared),
    )


def test_guarded_paste_refuses_malformed_declaration(*, tmp_path, monkeypatch):
    _assert_clause_refuses(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        obs=_observation(malformed=True),
    )


def test_guarded_paste_refuses_fresh_ack(*, tmp_path, monkeypatch):
    _assert_clause_refuses(tmp_path=tmp_path, monkeypatch=monkeypatch, obs=_observation(acked=True))
