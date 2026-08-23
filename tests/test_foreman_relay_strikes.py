"""Tests for foreman relay strike accounting."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"

__all__: list[str] = []


def relay_module():
    assert (OVERSEER_DIR / "foreman_relay_strikes.py").is_file()
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_relay_strikes")


def test_relay_strikes_mark_the_third_full_autonomy_relay_final(*, tmp_path):
    module = relay_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    payload = {"answer_text": "Take option 1.", "question_fingerprint": "question-1"}
    row = {
        "epic": "overseer-plan",
        "session_identity": "claude:pid-one:alpha",
        "branch": "feat/x",
        "branch_head": "abc123",
    }
    records: list[dict[str, object]] = []

    first = module.prepare_relay(
        repo=repo,
        action_id="blocked_session_answer",
        topic="alpha",
        row=row,
        payload=payload,
        full_autonomy=True,
        records=records,
    )
    records.append(first.record)
    second = module.prepare_relay(
        repo=repo,
        action_id="blocked_session_answer",
        topic="alpha",
        row={**row, "session_identity": "claude:pid-two:alpha"},
        payload=payload,
        full_autonomy=True,
        records=records,
    )
    records.append(second.record)
    third = module.prepare_relay(
        repo=repo,
        action_id="blocked_session_answer",
        topic="alpha",
        row={**row, "session_identity": "claude:pid-three:alpha"},
        payload=payload,
        full_autonomy=True,
        records=records,
    )

    assert first.objections_remaining == 2
    assert first.final is False
    assert second.objections_remaining == 1
    assert second.final is False
    assert third.objections_remaining == 0
    assert third.final is True
    assert third.final_sentence == module.FINAL_RELAY_SENTENCE
    assert third.record["final"] is True
    assert third.record["work_item_id"] == "overseer-plan"
    assert third.record["session_identity"] == "claude:pid-three:alpha"


def test_relay_strikes_key_by_epic_and_fingerprint_and_refuse_fourth(*, tmp_path):
    module = relay_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    row = {"epic": "overseer-plan", "session_identity": "claude:pid:alpha"}
    payload = {"answer_text": "Take option 1.", "question_fingerprint": "question-1"}
    other = {"answer_text": "Take option 2.", "question_fingerprint": "question-2"}
    records: list[dict[str, object]] = []
    for _ in range(3):
        relay = module.prepare_relay(
            repo=repo,
            action_id="blocked_session_answer",
            topic="alpha",
            row=row,
            payload=payload,
            full_autonomy=True,
            records=records,
        )
        records.append(relay.record)

    fourth = module.prepare_relay(
        repo=repo,
        action_id="blocked_session_answer",
        topic="alpha",
        row=row,
        payload=payload,
        full_autonomy=True,
        records=records,
    )
    fresh = module.prepare_relay(
        repo=repo,
        action_id="blocked_session_answer",
        topic="alpha",
        row=row,
        payload=other,
        full_autonomy=True,
        records=records,
    )

    assert fourth.refusal == "relay_strike_limit_reached"
    assert fresh.objections_remaining == 2
    assert fresh.final is False


def test_relay_strikes_ignore_non_matching_objection_comments(*, tmp_path):
    module = relay_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    payload = {"answer_text": "Take option 1.", "question_fingerprint": "question-1"}
    fingerprint = module.ruling_fingerprint(payload=payload)
    item = repo / "tmp" / "overseer" / "ledger-items" / "overseer-plan.json"
    item.parent.mkdir(parents=True)
    item.write_text(
        json.dumps(
            {
                "comments": [
                    {"text": f"OBJECTION other-{fingerprint}: wrong ruling"},
                    {"text": f"OBJECTION {fingerprint}: matching ruling"},
                ]
            }
        ),
        encoding="utf-8",
    )

    objections = module.count_objections(
        repo=repo, plan_epic_id="overseer-plan", fingerprint=fingerprint
    )

    assert objections == 1


def test_full_autonomy_false_keeps_count_but_never_marks_final(*, tmp_path):
    module = relay_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    row = {"epic": "overseer-plan", "session_identity": "claude:pid:alpha"}
    payload = {"answer_text": "Take option 1.", "question_fingerprint": "question-1"}
    records: list[dict[str, object]] = []
    for _ in range(2):
        relay = module.prepare_relay(
            repo=repo,
            action_id="blocked_session_answer",
            topic="alpha",
            row=row,
            payload=payload,
            full_autonomy=False,
            records=records,
        )
        records.append(relay.record)

    third = module.prepare_relay(
        repo=repo,
        action_id="blocked_session_answer",
        topic="alpha",
        row=row,
        payload=payload,
        full_autonomy=False,
        records=records,
    )

    assert third.objections_remaining == 0
    assert third.final is False
    assert "final" not in third.record
    assert third.final_sentence is None


def test_blocked_answer_relay_counts_full_journal_not_capped_document(*, tmp_path):
    module = relay_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".livespec.jsonc").write_text(
        json.dumps({"livespec-overseer": {"full_autonomy": True}}),
        encoding="utf-8",
    )
    row = {"epic": "overseer-plan", "session_identity": "claude:pid:alpha"}
    payload = {"answer_text": "Take option 1.", "question_fingerprint": "question-1"}
    fingerprint = module.ruling_fingerprint(payload=payload)
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    journal.parent.mkdir(parents=True)
    old_matching_records = [
        {
            "stage": "foreman-act-relay",
            "work_item_id": "overseer-plan",
            "ruling_fingerprint": fingerprint,
        }
        for _ in range(2)
    ]
    recent_noise = [
        {"stage": "outcome", "outcome": {"work_item_id": f"overseer-noise-{index}"}}
        for index in range(20)
    ]
    journal.write_text(
        "\n".join(json.dumps(record) for record in [*old_matching_records, *recent_noise]) + "\n",
        encoding="utf-8",
    )

    relay = module.prepare_blocked_answer_relay(
        document={"dispatch_journal": recent_noise},
        repo=str(repo),
        topic="alpha",
        row=row,
        payload=payload,
    )

    assert relay.final is True
    assert relay.objections_remaining == 0
    assert relay.final_sentence == module.FINAL_RELAY_SENTENCE
