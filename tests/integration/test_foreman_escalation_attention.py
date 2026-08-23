"""Integration-tier coverage for foreman-owned daemon attention escalation."""

from __future__ import annotations

import contextlib
import io as _io
import json
from pathlib import Path

from overseer import _supervisor_foreman_escalation as foreman_escalation
from overseer import foreman_runtime, registry, signals, supervisor
from overseer.test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    wrapup_count,
)
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def write_foreman_escalation(
    *,
    repo: Path,
    topic: str,
    reason: str,
    session_identity: str | None = None,
    resolved: bool = False,
) -> None:
    path = repo / "tmp" / "overseer" / "foreman" / "escalations" / f"{topic}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"reason": reason}
    if session_identity is not None:
        payload["session_identity"] = session_identity
    if resolved:
        payload["resolved"] = True
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def make_foreman_escalation_supervisor(*, tmp_path, repo, fake, now=2000.0):
    return make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        own_pane="%7",
        watch_repos=[str(repo)],
        out=_io.StringIO(),
        now=lambda: now,
        status_writer=lambda *, path, body: None,
    )


def test_scenario_foreman_escalation_is_report_only_attention(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="foreman-decision")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    write_foreman_escalation(repo=repo, topic=topic, reason="choose release path")
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=92, topic=topic))
    sup = make_foreman_escalation_supervisor(tmp_path=tmp_path, repo=repo, fake=fake)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="t",
    )
    state_path = signals.state_path(repo=str(repo), topic=topic)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("ready\n", encoding="utf-8")

    rows = sup.tick(act=True)
    output = sup.out.getvalue()
    row = next(item for item in rows if item.topic == topic)

    assert row.status == "foreman-escalated"
    assert supervisor.needs_attention(row=row) is True
    assert "NEEDS YOU (1):" in output
    assert fake.window_name == "overseer(1!)"
    assert state_path.read_text(encoding="utf-8") == "ready\n"
    assert not fake.has(method="paste")
    assert not fake.has(method="keys")
    assert not fake.has(method="respawn")
    assert not fake.has(method="new")


def test_scenario_foreman_blocking_prompt_tick_is_reportable_violation(*, tmp_path):
    repo, _topic = make_plan(tmp_path=tmp_path)
    runtime = foreman_runtime.ForemanRuntime(repo=repo, now=lambda: 1000.25)
    document = {
        "snapshot": {
            "rows": [
                {
                    "topic": "repo-foreman",
                    "status": "blocked:human",
                    "picker_open": True,
                    "session_identity": "claude:current-foreman-seat",
                }
            ],
        }
    }

    first = runtime.step(document=document)
    result = runtime.step(document=document)

    marker = repo / "tmp" / "overseer" / "foreman" / "escalations" / "repo-foreman.json"
    assert first.blocking_prompt_open is False
    assert result.blocking_prompt_open is True
    assert json.loads(marker.read_text(encoding="utf-8")) == {
        "reason": (
            "foreman tick ended with a blocking prompt; the decision must stay on "
            "the non-blocking attention surface so the loop cadence can continue"
        ),
        "session_identity": "claude:current-foreman-seat",
    }
    assert not (repo / "tmp" / "overseer" / "repo-foreman" / ".overseer-state").exists()


def test_foreman_escalation_clears_for_resolved_marker_while_outstanding_still_fires(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="answered-foreman-decision")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    write_foreman_escalation(
        repo=repo,
        topic=topic,
        reason="choose release path",
        session_identity="claude:current-seat",
    )
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=92, topic=topic))
    sup = make_foreman_escalation_supervisor(tmp_path=tmp_path, repo=repo, fake=fake)
    track = registry.Track(
        repo=str(repo),
        topic=topic,
        tmux=session,
        epic="overseer-test-epic",
        observed_session_identity="claude:current-seat",
    )

    outstanding = sup.evaluate(track=track, act=False)
    assert outstanding.status == "foreman-escalated"
    assert outstanding.note == "foreman needs human decision: choose release path"

    write_foreman_escalation(
        repo=repo,
        topic=topic,
        reason="choose release path",
        session_identity="claude:current-seat",
        resolved=True,
    )

    cleared = sup.evaluate(track=track, act=False)
    assert cleared.status != "foreman-escalated"


def test_foreman_escalation_from_superseded_seat_does_not_alert_successor(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="superseded-foreman-decision")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    write_foreman_escalation(
        repo=repo,
        topic=topic,
        reason="choose release path",
        session_identity="claude:dead-seat",
    )
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=92, topic=topic))
    sup = make_foreman_escalation_supervisor(tmp_path=tmp_path, repo=repo, fake=fake)

    view = sup.evaluate(
        track=registry.Track(
            repo=str(repo),
            topic=topic,
            tmux=session,
            epic="overseer-test-epic",
            observed_session_identity="claude:successor-seat",
        ),
        act=False,
    )

    assert view.status != "foreman-escalated"


def test_foreman_escalation_malformed_marker_surfaces_on_read_only_tick(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="malformed-foreman-decision")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    marker = repo / "tmp" / "overseer" / "foreman" / "escalations" / f"{topic}.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("{", encoding="utf-8")
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=92, topic=topic))
    sup = make_foreman_escalation_supervisor(tmp_path=tmp_path, repo=repo, fake=fake)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)

    assert view.status == "foreman-escalated"
    assert view.note == "foreman needs human decision"
    assert sup.alerted == {}


def test_foreman_escalation_reader_treats_unreadable_and_blank_reason_as_present(
    *, tmp_path, monkeypatch
):
    repo, topic = make_plan(tmp_path=tmp_path, topic="blank-foreman-decision")
    marker = repo / "tmp" / "overseer" / "foreman" / "escalations" / f"{topic}.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"reason": "   "}) + "\n", encoding="utf-8")

    blank = foreman_escalation.read_escalation(repo=str(repo), topic=topic)
    assert blank == foreman_escalation.ForemanEscalation(reason=None)

    marker.write_text("[]\n", encoding="utf-8")
    non_object = foreman_escalation.read_escalation(repo=str(repo), topic=topic)
    assert non_object == foreman_escalation.ForemanEscalation(reason=None)

    original_read_text = Path.read_text

    def raising_read_text(self, *args, **kwargs):
        if self == marker:
            raise OSError("boom")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", raising_read_text)

    unreadable = foreman_escalation.read_escalation(repo=str(repo), topic=topic)
    assert unreadable == foreman_escalation.ForemanEscalation(reason=None)


def _open_foreman_round(*, tmp_path, topic, ctx=40):
    """Drive a REAL wrap-up round for a foreman topic and return its handles.

    The round is OPENED by the supervisor rather than seeded with
    `write_injection_stamp`, so the stamp/declaration ordering that certifies a
    `ready` is an observed consequence here, exactly as in the cardinal-rule
    scenarios. That matters for these tests specifically: the defect they pin is
    an INTERACTION between a live escalation and a CERTIFIABLE ready, and a
    declaration that was never certifiable could not tell the two apart.
    """
    repo, topic = make_plan(tmp_path=tmp_path, topic=topic)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: 1000.0, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)
    opened = sup.evaluate(track=track, act=True)

    assert opened.status == "warned"
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is not None
    )
    return repo, topic, session, fake, sup, track


def test_scenario_escalated_foreman_ready_declaration_still_certifies(*, tmp_path):
    """Scenario: an escalated foreman can wind down without retracting its escalation.

    The defect: `active_decision` evaluated the foreman-escalation branch before any
    path that can act on a declaration and RETURNED, carrying `ready` through
    untouched. A foreman's valid declaration could therefore never certify while its
    marker was live, and the seat's only route to a restart was to resolve its own
    unanswered maintainer items.

    Both conditions are required to see it. A test that exercises only one cannot
    distinguish fixed from broken, because the defect lives in their interaction.
    """
    repo, topic, session, fake, sup, track = _open_foreman_round(
        tmp_path=tmp_path, topic="foreman-winddown"
    )
    write_foreman_escalation(repo=repo, topic=topic, reason="ratification authorization")
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=track, act=True)

    assert view.status == "restarting"
    assert [call for call in fake.calls if call[0] == "respawn"] != []


def test_escalated_foreman_without_a_declaration_is_never_restartable(*, tmp_path):
    """The discriminating control for the fix above, and the cardinal rule's guard.

    A branch reorder that simply let the escalation fall through would satisfy the
    scenario above while making every escalated foreman look restartable. An
    escalated foreman that has NOT declared must still resolve to `foreman-escalated`,
    must stay in NEEDS YOU, and must never be respawned.
    """
    repo, topic, session, fake, sup, track = _open_foreman_round(
        tmp_path=tmp_path, topic="escalated-foreman-no-ready"
    )
    write_foreman_escalation(repo=repo, topic=topic, reason="ratification authorization")

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=track, act=True)

    assert view.status == "foreman-escalated"
    assert supervisor.needs_attention(row=view) is True
    assert not fake.has(method="respawn")


def test_escalated_foreman_without_a_declaration_still_gets_a_wrapup_round(*, tmp_path):
    """A foreman escalation is an attention state, not a paste-suppression state.

    This maps the historical ``round_delivered`` fixture field to the current
    observable surface: a real wrap-up paste plus an injection stamp. The row must
    still stay ``foreman-escalated`` and non-restartable in the same run.
    """
    repo, topic = make_plan(tmp_path=tmp_path, topic="escalated-foreman-first-round")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    write_foreman_escalation(repo=repo, topic=topic, reason="ratification authorization")
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40, topic=topic))
    sup = make_foreman_escalation_supervisor(tmp_path=tmp_path, repo=repo, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=track, act=True)

    assert view.status == "foreman-escalated"
    assert supervisor.needs_attention(row=view) is True
    assert wrapup_count(fake=fake) == 1
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is not None
    )
    assert not fake.has(method="respawn")


def test_escalation_survives_the_restart_it_now_permits(*, tmp_path):
    """The escalation must outlive the restart that certifying its `ready` triggers.

    A marker is bound to the seat that raised it, and a marker whose identity differs
    from the LIVE session identity reads as SUPERSEDED. A restart necessarily replaces
    the seat, so permitting the restart without re-binding would let the successor see
    no escalation at all: the unanswered items would sit on disk with `resolved` false
    and surface nowhere. That is the same loss as blanking the marker, reached by a
    different route — and reached by the fix meant to prevent it.

    The daemon therefore UNBINDS the marker when it performs the restart. An unbound
    marker is never superseded, so the successor inherits the escalation and it keeps
    surfacing until a human answers it. A marker bound to a DIFFERENT LIVE seat is
    still superseded, which is the stale-predecessor case that binding exists for.
    """
    repo, topic, session, fake, sup, track = _open_foreman_round(
        tmp_path=tmp_path, topic="escalated-foreman-continuity"
    )
    seat = "claude:2359296:380695986:escalated-foreman-continuity"
    write_foreman_escalation(
        repo=repo,
        topic=topic,
        reason="sixteen unanswered maintainer items",
        session_identity=seat,
    )
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    track = registry.Track(
        repo=str(repo),
        topic=topic,
        tmux=session,
        epic=track.epic,
        observed_session_identity=seat,
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=track, act=True)

    assert view.status == "restarting"

    marker = Path(repo) / "tmp" / "overseer" / "foreman" / "escalations" / f"{topic}.json"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload.get("resolved") is not True
    assert "sixteen unanswered maintainer items" in payload["reason"]

    successor = foreman_escalation.read_escalation(
        repo=str(repo), topic=topic, live_session_identity="claude:9999:1234:successor"
    )
    assert successor is not None
