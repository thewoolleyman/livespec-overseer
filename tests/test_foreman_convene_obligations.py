# livespec-lloc-soft-band-owner: overseer-tdfe.2
"""Regression tests for foreman convene-obligation records."""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import foreman_gather_evidence
import pytest
import registry
from _supervisor_consensus_overdue import (
    CONSENSUS_OVERDUE_STATUS,
    ConsensusOverdueRequest,
    consensus_overdue_decision,
)

__all__: list[str] = []


@dataclass(frozen=True, kw_only=True)
class _FakeSupervisor:
    now_value: float
    alerts: list[dict[str, object]] = field(default_factory=list)

    def now(self) -> float:
        return self.now_value

    def alert(
        self,
        *,
        repo: str,
        topic: str,
        session: str,
        pane: str,
        message: str,
        condition: str,
    ) -> None:
        self.alerts.append(
            {
                "repo": repo,
                "topic": topic,
                "session": session,
                "pane": pane,
                "message": message,
                "condition": condition,
            }
        )


def test_convene_obligation_helper_writes_reader_matching_record(*, tmp_path):
    module_path = (
        Path(__file__).resolve().parent.parent / "overseer" / "foreman_convene_obligations.py"
    )
    assert module_path.is_file()
    obligations = importlib.import_module("foreman_convene_obligations")

    path = obligations.write_convene_obligation(
        repo=tmp_path,
        topic="alpha",
        question_fingerprint="f" * 64,
        action_id="blocked_session_answer",
        observed_at_epoch=1000.0,
        human_valve_category="needs-judgment",
        request={"question_fingerprint": "f" * 64, "summary": "blocked row"},
    )

    assert (
        path.parent == tmp_path / "tmp" / "overseer" / "foreman" / "convene-obligations" / "alpha"
    )
    assert path.name.startswith("blocked_session_answer-")
    assert path.name.endswith(".json")
    assert list(path.parent.glob("*.tmp")) == []
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "kind": "foreman-convene-obligation",
        "question_fingerprint": "f" * 64,
        "action_id": "blocked_session_answer",
        "human_valve": {"category": "needs-judgment"},
        "observed_at_epoch": 1000.0,
        "request": {"question_fingerprint": "f" * 64, "summary": "blocked row"},
    }


def test_convene_obligation_paths_do_not_collide_for_distinct_targets(*, tmp_path):
    module_path = (
        Path(__file__).resolve().parent.parent / "overseer" / "foreman_convene_obligations.py"
    )
    assert module_path.is_file()
    obligations = importlib.import_module("foreman_convene_obligations")

    first = obligations.convene_obligation_path(
        repo=tmp_path,
        topic="alpha",
        action_id="act",
        question_fingerprint="a" * 64,
    )
    second = obligations.convene_obligation_path(
        repo=tmp_path,
        topic="alpha",
        action_id="act",
        question_fingerprint="b" * 64,
    )

    assert first != second
    assert first.parent == second.parent


@pytest.mark.integration
def test_convene_obligation_writer_supports_discharge_and_escalation_roots(*, tmp_path):
    module_path = (
        Path(__file__).resolve().parent.parent / "overseer" / "foreman_convene_obligations.py"
    )
    assert module_path.is_file()
    obligations = importlib.import_module("foreman_convene_obligations")

    discharge = obligations.write_convene_discharge(
        repo=tmp_path,
        topic="alpha",
        question_fingerprint="d" * 64,
        reason="panel_convened",
        observed_at_epoch=1100.0,
        request={"question_fingerprint": "d" * 64},
    )
    escalation = obligations.write_convene_escalation(
        repo=tmp_path,
        topic="alpha",
        question_fingerprint="e" * 64,
        reason="convene_failed",
        observed_at_epoch=1200.0,
        request={"question_fingerprint": "e" * 64},
    )

    assert (
        discharge.parent
        == tmp_path / "tmp" / "overseer" / "foreman" / "convene-discharges" / "alpha"
    )
    assert (
        escalation.parent
        == tmp_path / "tmp" / "overseer" / "foreman" / "convene-escalations" / "alpha"
    )
    assert json.loads(discharge.read_text(encoding="utf-8"))["kind"] == "foreman-convene-discharge"
    assert (
        json.loads(escalation.read_text(encoding="utf-8"))["kind"] == "foreman-convene-escalation"
    )


def test_reader_raises_only_after_producer_written_obligation(*, tmp_path):
    module_path = (
        Path(__file__).resolve().parent.parent / "overseer" / "foreman_convene_obligations.py"
    )
    assert module_path.is_file()
    obligations = importlib.import_module("foreman_convene_obligations")

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".livespec.jsonc").write_text(
        '{"livespec-overseer": {"foreman_valve_disposition": "consensus"}}\n',
        encoding="utf-8",
    )
    capture = "blocked row payload"
    question_fingerprint = foreman_gather_evidence.pane_content_hash(text=capture)
    sup = _FakeSupervisor(now_value=3700.0)
    request = ConsensusOverdueRequest(
        sup=sup,
        track=registry.Track(topic="alpha", repo=str(repo), tmux="repo-alpha"),
        session="repo-alpha",
        pane="%1",
        capture=capture,
        blocked_age=3700.0,
        note=None,
        act=True,
    )

    assert consensus_overdue_decision(request=request) is None

    _ = obligations.write_convene_obligation(
        repo=repo,
        topic="alpha",
        question_fingerprint=question_fingerprint,
        action_id="blocked_session_answer",
        observed_at_epoch=1000.0,
        human_valve_category="needs-judgment",
        request={"question_fingerprint": question_fingerprint},
    )

    decision = consensus_overdue_decision(request=request)

    assert decision is not None
    assert decision.status == CONSENSUS_OVERDUE_STATUS
    assert decision.active_conditions == {CONSENSUS_OVERDUE_STATUS}
    assert sup.alerts[-1]["condition"] == CONSENSUS_OVERDUE_STATUS


def test_reader_matches_nested_request_fingerprint_written_by_producer(*, tmp_path):
    module_path = (
        Path(__file__).resolve().parent.parent / "overseer" / "foreman_convene_obligations.py"
    )
    assert module_path.is_file()
    obligations = importlib.import_module("foreman_convene_obligations")

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".livespec.jsonc").write_text(
        '{"livespec-overseer": {"foreman_valve_disposition": "consensus"}}\n',
        encoding="utf-8",
    )
    capture = "nested fingerprint payload"
    question_fingerprint = foreman_gather_evidence.pane_content_hash(text=capture)
    path = obligations.write_convene_obligation(
        repo=repo,
        topic="alpha",
        question_fingerprint=question_fingerprint,
        action_id="blocked_session_answer",
        observed_at_epoch=1000.0,
        human_valve_category="needs-judgment",
        request={"question_fingerprint": question_fingerprint},
    )
    record = json.loads(path.read_text(encoding="utf-8"))
    del record["question_fingerprint"]
    path.write_text(json.dumps(record), encoding="utf-8")

    decision = consensus_overdue_decision(
        request=ConsensusOverdueRequest(
            sup=_FakeSupervisor(now_value=3700.0),
            track=registry.Track(topic="alpha", repo=str(repo), tmux="repo-alpha"),
            session="repo-alpha",
            pane="%1",
            capture=capture,
            blocked_age=3700.0,
            note=None,
            act=False,
        )
    )

    assert decision is not None
    assert decision.status == CONSENSUS_OVERDUE_STATUS
