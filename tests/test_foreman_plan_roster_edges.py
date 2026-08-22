"""Edge coverage for the foreman plan roster helper."""

from __future__ import annotations

import json
from pathlib import Path

import foreman_plan_roster

__all__: list[str] = []


def _plan(*, repo: Path, topic: str) -> None:
    (repo / "plan" / topic).mkdir(parents=True)


def _snapshot(*, path: Path, repo: Path, rows: list[object] | object) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "daemon_instance_id": "daemon-1",
                "tick_generation": 12,
                "rows": rows,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_absent_plan_directory_emits_empty_roster(*, tmp_path):
    roster = foreman_plan_roster.compose_roster(
        repo=tmp_path / "repo",
        snapshot_path=tmp_path / "missing.json",
        tmux_sessions=[],
    )

    assert roster["rows"] == []
    assert roster["name_identity_errors"] == []


def test_malformed_snapshot_rows_fall_back_to_no_daemon_rows(*, tmp_path):
    repo = tmp_path / "repo"
    snapshot_path = tmp_path / "status.json"
    _plan(repo=repo, topic="alpha")
    _snapshot(path=snapshot_path, repo=repo, rows={})

    roster = foreman_plan_roster.compose_roster(
        repo=repo,
        snapshot_path=snapshot_path,
        tmux_sessions=["alpha"],
    )

    assert roster["rows"][0]["status"] == "no-daemon-row"


def test_daemon_row_edges_are_reported_without_adopting_foreign_topics(*, tmp_path):
    repo = tmp_path / "repo"
    snapshot_path = tmp_path / "status.json"
    _plan(repo=repo, topic="alpha")
    _plan(repo=repo, topic="beta")
    _plan(repo=repo, topic="gamma")
    _plan(repo=repo, topic="delta")
    _snapshot(
        path=snapshot_path,
        repo=repo,
        rows=[
            [],
            {"repo": str(repo), "topic": "", "status": "working", "tmux": "ignored"},
            {"repo": str(repo), "topic": "alpha", "status": 7, "tmux": "alpha"},
            {"repo": str(repo), "topic": "beta", "status": "idle", "tmux": "other"},
            {"repo": str(repo), "topic": "gamma", "status": "blocked:human", "tmux": "gamma"},
            {"repo": str(repo), "topic": "delta", "status": "unknown-new", "tmux": "delta"},
        ],
    )

    roster = foreman_plan_roster.compose_roster(
        repo=repo,
        snapshot_path=snapshot_path,
        tmux_sessions=["alpha", "beta", "gamma", "delta"],
    )

    rows = {row["plan"]: row for row in roster["rows"]}
    assert rows["alpha"]["status"] == "daemon-row-missing-status"
    assert rows["alpha"]["status_emoji"] == "🔴"
    assert rows["beta"]["name_identity_verdict"] == "daemon_tmux_name_mismatch"
    assert rows["beta"]["status_emoji"] == "🟡"
    assert rows["gamma"]["status_emoji"] == "🟡"
    assert rows["delta"]["status_emoji"] == "🔴"


def test_main_uses_explicit_tmux_sessions_and_writes_json(*, tmp_path, capsys):
    repo = tmp_path / "repo"
    _plan(repo=repo, topic="alpha")

    result = foreman_plan_roster.main(
        argv=[
            "--repo",
            str(repo),
            "--snapshot-path",
            str(tmp_path / "missing.json"),
            "--tmux-session",
            "alpha",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["rows"][0]["name_identity_verdict"] == "ok"


def test_main_queries_tmux_when_no_test_session_is_supplied(*, tmp_path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    _plan(repo=repo, topic="alpha")

    class FakeTmux:
        def list_sessions(self) -> list[str]:
            return ["alpha"]

    monkeypatch.setattr(foreman_plan_roster.tmuxio, "TmuxIO", FakeTmux)

    result = foreman_plan_roster.main(
        argv=[
            "--repo",
            str(repo),
            "--snapshot-path",
            str(tmp_path / "missing.json"),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["rows"][0]["name_identity_verdict"] == "ok"
