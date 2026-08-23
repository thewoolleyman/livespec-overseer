"""Lifecycle tests for typed wait-premise records."""

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
