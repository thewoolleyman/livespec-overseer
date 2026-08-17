"""Repo-level coverage for Lane B liveness attention."""

import contextlib
import io as _io

import _supervisor_attention
import _supervisor_attention_exhausted
import _supervisor_config
import _supervisor_state
import pytest
import registry
import signals
from _supervisor_records import InjectState
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_starvation_decision_can_report_without_alerting(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    track = mapped_track(repo=repo, topic=topic, session=session)

    decision = _supervisor_attention.pre_busy_attention_decision(
        request=_supervisor_attention.AttentionRequest(
            sup=sup,
            track=track,
            session=session,
            pane=session,
            attention=_supervisor_attention.LivenessAttention(
                generating=False,
                shell_only=False,
                escalation_exhausted_now=False,
                escalation_exhausted_due=False,
                starving_now=True,
                starved_due=True,
                shell_due=False,
                escalation_exhausted_age=None,
                starvation_age=_supervisor_config.WINDDOWN_STARVED_AFTER,
                shell_age=None,
            ),
            idle=False,
            gate=False,
            blocked=None,
            blocked_age=None,
            act=False,
        )
    )

    assert decision is not None
    assert decision.status == "winddown-starved"
    assert decision.active_conditions == {"winddown-starved"}


def test_escalation_exhausted_decision_can_report_without_alerting(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    track = mapped_track(repo=repo, topic=topic, session=session)

    decision = _supervisor_attention.pre_busy_attention_decision(
        request=_supervisor_attention.AttentionRequest(
            sup=sup,
            track=track,
            session=session,
            pane=session,
            attention=_supervisor_attention.LivenessAttention(
                generating=False,
                shell_only=False,
                escalation_exhausted_now=True,
                escalation_exhausted_due=True,
                starving_now=False,
                starved_due=False,
                shell_due=False,
                escalation_exhausted_age=_supervisor_config.ESCALATION_EXHAUSTED_AFTER,
                starvation_age=None,
                shell_age=None,
            ),
            idle=True,
            gate=False,
            blocked=None,
            blocked_age=None,
            act=False,
        )
    )

    assert decision is not None
    assert decision.status == "escalation-exhausted"
    assert decision.active_conditions == {"escalation-exhausted"}


def test_escalation_exhaustion_observer_requires_a_complete_idle_delivered_round(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session="topic")
    registry.write_injection_stamp(repo=str(repo), topic=topic, ts=900.0, stamp_path=sup.stamp_path)
    registry.add_notified_band(repo=str(repo), topic=topic, band=50, stamp_path=sup.stamp_path)
    registry.add_notified_band(repo=str(repo), topic=topic, band=40, stamp_path=sup.stamp_path)
    base = {
        "sup": sup,
        "track": track,
        "eff_ctx": 40,
        "threshold": 50,
        "idle": True,
        "busy": False,
        "generating": False,
        "shell_only": False,
        "declared": None,
        "round_record": registry.read_round_record(
            repo=str(repo), topic=topic, stamp_path=sup.stamp_path
        ),
    }

    first = _supervisor_attention_exhausted.observe_escalation_exhaustion(
        request=_supervisor_attention_exhausted.ObserveEscalationExhaustionRequest(
            **base, istate=InjectState()
        )
    )
    assert first.active_now is True
    assert first.due is False

    episode = InjectState()
    _supervisor_attention_exhausted.observe_escalation_exhaustion(
        request=_supervisor_attention_exhausted.ObserveEscalationExhaustionRequest(
            **base, istate=episode
        )
    )
    clock["t"] += _supervisor_config.ESCALATION_EXHAUSTED_AFTER
    due = _supervisor_attention_exhausted.observe_escalation_exhaustion(
        request=_supervisor_attention_exhausted.ObserveEscalationExhaustionRequest(
            **base, istate=episode
        )
    )
    assert due.due is True

    missing_ctx = _supervisor_attention_exhausted.observe_escalation_exhaustion(
        request=_supervisor_attention_exhausted.ObserveEscalationExhaustionRequest(
            **(base | {"eff_ctx": None}), istate=InjectState()
        )
    )
    assert missing_ctx.active_now is False


def test_starvation_alert_enumerates_blocked_gate_and_shell_evidence(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "shell"}
    track = mapped_track(repo=repo, topic=topic, session=session)
    declare(repo=repo, topic=topic, value="blocked: need a decision", mtime=900.0)

    sup.evaluate(track=track, act=True)
    for _ in range(9):
        clock["t"] += 800.0
        sup.evaluate(track=track, act=True)
    fake.panes[session] = "Do you want to proceed?\n❯ 1. Yes\n  2. No\nCtx: 40% left\n"
    clock["t"] += 800.0

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track=track, act=True)

    assert view.status == "blocked:human"
    assert "winddown starved" in (view.note or "")
    assert "blocked" in view.note
    assert "need a decision" in view.note
    assert "visible gate" in view.note
    assert "background shell" in view.note
    assert "wind-down starved (2h)" in err.getvalue()


def test_shell_only_above_threshold_surfaces_after_long_floor(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "shell"}
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "working"
    for _ in range(35):
        clock["t"] += 800.0
        sup.evaluate(track=track, act=True)
    clock["t"] += 801.0

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track=track, act=True)

    assert view.status == "shell-prolonged"
    assert view.note == "background shell 8h"
    assert "background shell prolonged (8h)" in err.getvalue()


def test_stale_blocked_unlink_failure_is_logged_and_does_not_restore_block(
    *, tmp_path, monkeypatch
):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    declare(repo=repo, topic=topic, value="blocked: stale", mtime=100.0)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), now=lambda: 1000.0)
    track = mapped_track(repo=repo, topic=topic, session=session)

    def unlink_raises(self, *, missing_ok=False):
        raise OSError("simulated unlink failure")

    monkeypatch.setattr(signals.Path, "unlink", unlink_raises)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        blocked = _supervisor_state.void_stale_blocked(
            sup=sup,
            track=track,
            blocked="stale",
            generating=True,
        )

    assert blocked is None
    assert "could not delete state file" in err.getvalue()
    assert signals.read_state(repo=str(repo), topic=topic) is not None
