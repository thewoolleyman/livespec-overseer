"""Foreman plan roster helper contract."""

from __future__ import annotations

import json
from pathlib import Path

import foreman_plan_roster

__all__: list[str] = []


def _write_snapshot(*, path: Path, repo: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "daemon_instance_id": "daemon-1",
                "tick_generation": 11,
                "written_at": "2026-08-22T00:00:00Z",
                "rows": [
                    {
                        "repo": str(repo),
                        "topic": "alpha",
                        "tmux": "alpha",
                        "runtime": "codex",
                        "status": "working",
                    },
                    {
                        "repo": str(repo),
                        "topic": "beta",
                        "tmux": None,
                        "runtime": "codex",
                        "status": "session-gone",
                    },
                    {
                        "repo": str(repo.parent / "other-repo"),
                        "topic": "foreign",
                        "tmux": "foreign",
                        "runtime": "codex",
                        "status": "working",
                    },
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _plan(*, repo: Path, topic: str) -> None:
    (repo / "plan" / topic).mkdir(parents=True)


def test_roster_is_driven_by_plan_directories_and_left_joins_daemon_snapshot(*, tmp_path):
    repo = tmp_path / "repo"
    snapshot_path = tmp_path / "status.json"
    _plan(repo=repo, topic="alpha")
    _plan(repo=repo, topic="beta")
    _plan(repo=repo, topic="gamma")
    (repo / "plan" / "archive").mkdir(parents=True)
    (repo / "plan" / "archive" / "closed").mkdir()
    _write_snapshot(path=snapshot_path, repo=repo)

    roster = foreman_plan_roster.compose_roster(
        repo=repo,
        snapshot_path=snapshot_path,
        tmux_sessions=["alpha", "beta", "foreign"],
    )

    rows = {row["plan"]: row for row in roster["rows"]}
    assert list(rows) == ["alpha", "beta", "gamma"]
    assert rows["alpha"]["status"] == "working"
    assert rows["alpha"]["status_emoji"] == "🟢"
    assert rows["beta"]["name_identity_verdict"] == "ok"
    assert rows["beta"]["status"] == "session-gone"
    assert rows["beta"]["status_emoji"] == "🔴"
    assert rows["gamma"]["status"] == "no-daemon-row"
    assert rows["gamma"]["status_emoji"] == "🔴"
    assert "foreign" not in rows


def test_roster_reports_distinct_plan_only_and_tmux_only_name_identity_errors(*, tmp_path):
    repo = tmp_path / "repo"
    snapshot_path = tmp_path / "status.json"
    _plan(repo=repo, topic="plan-only")
    snapshot_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "daemon_instance_id": "daemon-1",
                "tick_generation": 12,
                "rows": [
                    {
                        "repo": str(repo),
                        "topic": "tmux-only",
                        "tmux": "tmux-only",
                        "runtime": "codex",
                        "status": "working",
                    },
                    {
                        "repo": str(repo.parent / "other-repo"),
                        "topic": "foreign",
                        "tmux": "foreign",
                        "runtime": "codex",
                        "status": "working",
                    },
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    roster = foreman_plan_roster.compose_roster(
        repo=repo,
        snapshot_path=snapshot_path,
        tmux_sessions=["tmux-only", "foreign"],
    )

    row = roster["rows"][0]
    assert row["plan"] == "plan-only"
    assert row["name_identity_verdict"] == "plan_without_tmux_session"
    assert row["status"] == "no-daemon-row"
    assert roster["name_identity_errors"] == [
        {
            "kind": "tmux_session_without_plan",
            "tmux": "tmux-only",
        }
    ]
