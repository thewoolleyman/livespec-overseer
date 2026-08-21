"""Regression coverage for foreman-panel caller-supplied state isolation."""

from pathlib import Path

import foreman_panel
from foreman_consensus_cache import record_panel_result
from foreman_consensus_types import DEFAULT_PANEL_LIMITS, MODEL_IDENTITIES

__all__: list[str] = []


def test_convene_panel_uses_the_supplied_state_dir_for_budget_accounting(
    *, tmp_path: Path, monkeypatch
) -> None:
    exhausted = tmp_path / "exhausted"
    isolated = tmp_path / "isolated"
    for _ in range(DEFAULT_PANEL_LIMITS.daily_panel_budget):
        assert record_panel_result(
            state_dir=exhausted,
            daily_panel_budget=DEFAULT_PANEL_LIMITS.daily_panel_budget,
        )

    monkeypatch.setattr(
        foreman_panel,
        "reviewer_responses",
        lambda **_: {
            "reviewers": [
                {
                    "reviewer_id": identity["reviewer_id"],
                    "verdict": "unblock",
                    "action": {"action_id": "work_item_file", "params": {}},
                }
                for identity in MODEL_IDENTITIES
            ]
        },
    )

    verdict = foreman_panel.convene_panel(
        request={
            "schema_version": 1,
            "blocked_question": "Should the bounded action proceed?",
            "repo": str(tmp_path / "repo"),
            "topic": "alpha",
            "item_id": "overseer-a7c",
            "repo_revision": "abc123",
            "item_revision": "rank:7/status:blocked",
            "handoff_or_work_item": "Implement the bounded formatter step.",
            "repo_context": "Python stdlib-only control-plane repo.",
            "snapshot": {"daemon_instance_id": "daemon-1", "tick_generation": 9},
        },
        state_dir=isolated,
        verdict_path=tmp_path / "verdict.json",
        dossier_dir=tmp_path / "dossier",
    )

    assert verdict["outcome"] == "unanimous"
