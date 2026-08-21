"""Integration-tier coverage for foreman-owned daemon attention escalation."""

from __future__ import annotations

import io as _io
import json
from pathlib import Path

from overseer import _supervisor_foreman_escalation as foreman_escalation
from overseer import registry, signals, supervisor
from overseer.test_supervisor_builders import idle_capture, make_plan, make_supervisor, mapped_track
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def write_foreman_escalation(*, repo: Path, topic: str, reason: str) -> None:
    path = repo / "tmp" / "overseer" / "foreman" / "escalations" / f"{topic}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"reason": reason}) + "\n", encoding="utf-8")


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
