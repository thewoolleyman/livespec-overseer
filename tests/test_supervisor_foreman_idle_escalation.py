"""Foreman idle cadence coverage for the generic escalation ladder."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import _supervisor_attention
import _supervisor_foreman
import registry
from test_supervisor_builders import idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _write_heartbeat(
    *, repo, written_at: float, tick_interval_seconds: float, tick_generation: int = 1
) -> None:
    path = _supervisor_foreman.heartbeat_path(repo=str(repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "written_at": datetime.fromtimestamp(written_at, tz=timezone.utc).isoformat(),
        "pid": 123,
        "tick_generation": tick_generation,
        "tick_interval_seconds": tick_interval_seconds,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _foreman_track(*, repo, session: str) -> registry.ForemanSeat:
    return registry.ForemanSeat(
        topic=session,
        repo=str(repo),
        tmux=session,
        epic="overseer-test-epic",
        added_at="2026-08-23T00:00:00Z",
    )


def test_foreman_with_fresh_heartbeat_does_not_enter_idle_escalation(*, tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path)
    session = f"{repo.name}-foreman"
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    _write_heartbeat(repo=repo, written_at=1000.0 - 3599.0, tick_interval_seconds=3600.0)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0)

    view = sup.evaluate(track=_foreman_track(repo=repo, session=session), act=True)

    assert view.status == "idle"
    assert not fake.has(method="paste")
    assert _supervisor_foreman.foreman_row(repo=str(repo), now=sup.now) is None


def test_foreman_past_twice_contract_cadence_is_still_lapsed(*, tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path)
    _write_heartbeat(repo=repo, written_at=1000.0 - 7201.0, tick_interval_seconds=3600.0)

    row = _supervisor_foreman.foreman_row(repo=str(repo), now=lambda: 1000.0)

    assert row is not None
    assert row.status == _supervisor_foreman.FOREMAN_HEARTBEAT_STALE_STATUS
    assert "foreman heartbeat stale 120m" in (row.note or "")


def test_worker_idle_escalation_is_unchanged(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "warned"
    assert fake.has(method="paste")


def test_escalation_exhausted_alert_is_not_resurfaced_by_age_label_only(*, tmp_path, capsys):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    attention = _supervisor_attention.LivenessAttention(
        generating=False,
        shell_only=False,
        escalation_exhausted_now=True,
        escalation_exhausted_due=True,
        starving_now=False,
        starved_due=False,
        shell_due=False,
        escalation_exhausted_age=47.0 * 60.0,
        starvation_age=None,
        shell_age=None,
    )

    first = _supervisor_attention.pre_busy_attention_decision(
        request=_supervisor_attention.AttentionRequest(
            sup=sup,
            track=track,
            session=session,
            pane=session,
            attention=attention,
            idle=True,
            gate=False,
            blocked=None,
            blocked_age=None,
            act=True,
        )
    )
    later_attention = _supervisor_attention.LivenessAttention(
        generating=False,
        shell_only=False,
        escalation_exhausted_now=True,
        escalation_exhausted_due=True,
        starving_now=False,
        starved_due=False,
        shell_due=False,
        escalation_exhausted_age=48.0 * 60.0,
        starvation_age=None,
        shell_age=None,
    )
    second = _supervisor_attention.pre_busy_attention_decision(
        request=_supervisor_attention.AttentionRequest(
            sup=sup,
            track=track,
            session=session,
            pane=session,
            attention=later_attention,
            idle=True,
            gate=False,
            blocked=None,
            blocked_age=None,
            act=True,
        )
    )

    assert first is not None and first.status == "escalation-exhausted"
    assert second is not None and second.status == "escalation-exhausted"
    surfaced = [
        line for line in capsys.readouterr().err.splitlines() if "escalation exhausted" in line
    ]
    assert len(surfaced) == 1
