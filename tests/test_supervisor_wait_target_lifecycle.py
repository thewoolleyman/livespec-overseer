"""Repo-level mirror for wait-premise target lifecycle cleanup."""

from __future__ import annotations

import importlib

__all__: list[str] = []


def test_wait_premise_remover_deletes_record_and_ignores_absent_target(*, tmp_path):
    wait_premises = importlib.import_module("wait_premises")

    repo = tmp_path / "repo"
    path = wait_premises.write_wait_premise(
        repo=repo,
        topic="alpha",
        kind="fabro-run",
        target_id="01M0RUN",
        evidence_source="fabro ps -a --json",
        recorded_at="2026-08-19T02:30:00Z",
        recheck_by="2026-08-19T03:00:00Z",
    )

    removed = wait_premises.remove_wait_premise(
        repo=repo,
        topic="alpha",
        kind="fabro-run",
        target_id="01M0RUN",
    )
    removed_again = wait_premises.remove_wait_premise(
        repo=repo,
        topic="alpha",
        kind="fabro-run",
        target_id="01M0RUN",
    )

    assert removed == path
    assert removed_again == path
    assert not path.exists()
    assert wait_premises.read_wait_premises(repo=repo, topic="alpha") == []


def test_wait_target_source_marks_delivered_remote_run_satisfied(tmp_path):
    sources = importlib.import_module("_supervisor_wait_target_sources")
    journal = tmp_path / "tmp" / "fabro-dispatch-journal.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text(
        "\n".join(
            [
                '{"at":"2026-08-19T02:31:00Z","dispatch_id":"remote-run",'
                '"stage":"dispatch-id","work_item_id":"overseer-x"}',
                '{"at":"2026-08-19T02:41:00Z","outcome":{"dispatch_id":"remote-run",'
                '"status":"succeeded","work_item_id":"overseer-x"},"stage":"outcome"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = sources.verify_wait_target_record(
        repo=tmp_path,
        record={
            "kind": "fabro-run",
            "target_id": "remote-run",
            "execution_location": "remote",
            "work_item_id": "overseer-x",
        },
        cache=None,
        now=1.0,
    )

    assert result.status == "satisfied"


def test_wait_target_lifecycle_statuses_are_distinct():
    status = importlib.import_module("_supervisor_wait_target_status")

    assert status.WAIT_TARGET_EXPIRED_STATUS == "expired"
    assert status.WAIT_TARGET_SATISFIED_STATUS == "satisfied"
