"""Beside-style tests for report-only consensus-overdue attention."""

from __future__ import annotations

import contextlib
import io as _io
import json

import _supervisor_attention
import foreman_gather_evidence
import registry
import supervisor
from test_supervisor_builders import declare, idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def write_disposition(*, repo, value: str) -> None:
    (repo / ".livespec.jsonc").write_text(
        json.dumps({"livespec-overseer": {"foreman_valve_disposition": value}}),
        encoding="utf-8",
    )


def write_obligation(*, repo, topic: str, fingerprint: str, **fields: object) -> None:
    path = (
        repo
        / "tmp"
        / "overseer"
        / "foreman"
        / "convene-obligations"
        / topic
        / f"{fingerprint}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "question_fingerprint": fingerprint,
                "observed_at_epoch": 1000.0,
                "action_id": "blocked_session_answer",
                "human_valve": {"category": "ordinary"},
                **fields,
            }
        ),
        encoding="utf-8",
    )


def evaluated_blocked_row(*, tmp_path, repo, topic, capture: str, now: float):
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=capture)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: now)
    track = mapped_track(repo=repo, topic=topic, session=session)
    declare(repo=repo, topic=topic, value="blocked: choose the safe unblock", mtime=900.0)
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        row = sup.evaluate(track=track, act=True)
    return sup, fake, row, err.getvalue()


def test_consensus_overdue_raises_after_convene_bound_without_satisfying_artifact(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    write_disposition(repo=repo, value="consensus")
    capture = idle_capture(ctx=80, body="Should I answer option 1?")
    fingerprint = foreman_gather_evidence.pane_content_hash(text=capture)
    write_obligation(repo=repo, topic=topic, fingerprint=fingerprint)

    sup, fake, row, err = evaluated_blocked_row(
        tmp_path=tmp_path, repo=repo, topic=topic, capture=capture, now=1000.0 + 1801.0
    )

    assert row.status == "consensus-overdue"
    assert supervisor.needs_attention(row=row) is True
    assert "unmet convene obligation" in (row.note or "")
    assert topic in (row.note or "")
    assert "consensus overdue" in err
    assert fingerprint[:12] in err
    assert (str(repo), topic, "consensus-overdue") in sup.alerted
    assert not fake.has(method="paste")
    assert not fake.has(method="respawn")


def test_consensus_overdue_suppresses_when_matching_panel_record_exists(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    write_disposition(repo=repo, value="consensus")
    capture = idle_capture(ctx=80, body="Should I answer option 1?")
    fingerprint = foreman_gather_evidence.pane_content_hash(text=capture)
    write_obligation(repo=repo, topic=topic, fingerprint=fingerprint)
    panel = repo / "tmp" / "overseer" / "foreman" / "panels" / topic / "panel-abc.json"
    panel.parent.mkdir(parents=True)
    panel.write_text(
        json.dumps(
            {
                "kind": "foreman-consensus-panel",
                "request": {"question_fingerprint": fingerprint},
            }
        ),
        encoding="utf-8",
    )

    _sup, _fake, row, err = evaluated_blocked_row(
        tmp_path=tmp_path, repo=repo, topic=topic, capture=capture, now=1000.0 + 1801.0
    )

    assert row.status == "blocked:human"
    assert "unmet convene obligation" not in (row.note or "")
    assert "consensus overdue" not in err


def test_consensus_overdue_alert_condition_clears_when_artifact_appears(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    write_disposition(repo=repo, value="consensus")
    capture = idle_capture(ctx=80, body="Should I answer option 1?")
    fingerprint = foreman_gather_evidence.pane_content_hash(text=capture)
    write_obligation(repo=repo, topic=topic, fingerprint=fingerprint)
    sup, _fake, row, _err = evaluated_blocked_row(
        tmp_path=tmp_path, repo=repo, topic=topic, capture=capture, now=1000.0 + 1801.0
    )
    assert row.status == "consensus-overdue"
    assert (str(repo), topic, "consensus-overdue") in sup.alerted
    panel = repo / "tmp" / "overseer" / "foreman" / "panels" / topic / "panel-abc.json"
    panel.parent.mkdir(parents=True)
    panel.write_text(
        json.dumps({"request": {"question_fingerprint": fingerprint}}),
        encoding="utf-8",
    )

    row = sup.evaluate(
        track=mapped_track(
            repo=repo, topic=topic, session=registry.tmux_id(repo=str(repo), topic=topic)
        ),
        act=True,
    )

    assert row.status == "blocked:human"
    assert (str(repo), topic, "consensus-overdue") not in sup.alerted


def test_consensus_overdue_suppresses_for_report_only_disposition(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    write_disposition(repo=repo, value="report-only")
    capture = idle_capture(ctx=80, body="Should I answer option 1?")
    fingerprint = foreman_gather_evidence.pane_content_hash(text=capture)
    write_obligation(repo=repo, topic=topic, fingerprint=fingerprint)

    _sup, _fake, row, _err = evaluated_blocked_row(
        tmp_path=tmp_path, repo=repo, topic=topic, capture=capture, now=1000.0 + 1801.0
    )

    assert row.status == "blocked:human"


def test_consensus_overdue_suppresses_for_non_panel_or_floor_barred_decisions(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    write_disposition(repo=repo, value="consensus")
    capture = idle_capture(ctx=80, body="Should I answer option 1?")
    fingerprint = foreman_gather_evidence.pane_content_hash(text=capture)

    write_obligation(
        repo=repo,
        topic=topic,
        fingerprint=fingerprint,
        action_id="human_valve",
    )
    _sup, _fake, row, _err = evaluated_blocked_row(
        tmp_path=tmp_path, repo=repo, topic=topic, capture=capture, now=1000.0 + 1801.0
    )
    assert row.status == "blocked:human"

    write_obligation(
        repo=repo,
        topic=topic,
        fingerprint=fingerprint,
        action_id="blocked_session_answer",
        human_valve={"category": "human-gated-by-design"},
    )
    _sup, _fake, row, _err = evaluated_blocked_row(
        tmp_path=tmp_path, repo=repo, topic=topic, capture=capture, now=1000.0 + 1801.0
    )
    assert row.status == "blocked:human"


def test_consensus_overdue_clears_when_question_changes(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    write_disposition(repo=repo, value="consensus")
    old_capture = idle_capture(ctx=80, body="Should I answer option 1?")
    write_obligation(
        repo=repo,
        topic=topic,
        fingerprint=foreman_gather_evidence.pane_content_hash(text=old_capture),
    )

    _sup, _fake, row, _err = evaluated_blocked_row(
        tmp_path=tmp_path,
        repo=repo,
        topic=topic,
        capture=idle_capture(ctx=80, body="A different question"),
        now=1000.0 + 1801.0,
    )

    assert row.status == "blocked:human"


def test_consensus_overdue_module_exists_for_real_assertion_red() -> None:
    assert _supervisor_attention.CONSENSUS_OVERDUE_STATUS == "consensus-overdue"
