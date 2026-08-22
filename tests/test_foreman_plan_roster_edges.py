"""Edge coverage for the foreman plan roster helper."""

from __future__ import annotations

import json
from pathlib import Path

import foreman_plan_roster
import foreman_plan_roster_work

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


def _epic_anchor(*, repo: Path, topic: str, anchor: str) -> None:
    (repo / "plan" / topic / "epic.md").write_text(
        f"**Ledger anchor:** epic **`{anchor}`**\n",
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

    assert roster["rows"][0]["session_state"] == "no-session"


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
    assert rows["alpha"]["session_state"] == "no-session"
    assert rows["alpha"]["emoji"] == "⚪"
    assert rows["beta"]["name_identity_verdict"] == "daemon_tmux_name_mismatch"
    assert rows["beta"]["emoji"] == "❗"
    assert rows["gamma"]["session_state"] == "picker-parked"
    assert rows["gamma"]["emoji"] == "🔴"
    assert rows["delta"]["emoji"] == "⚪"


def test_blocked_human_renders_blocked_even_with_work_in_flight(*, tmp_path):
    repo = tmp_path / "repo"
    snapshot_path = tmp_path / "status.json"
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    _plan(repo=repo, topic="gamma")
    _epic_anchor(repo=repo, topic="gamma", anchor="overseer-gamma")
    journal.parent.mkdir(parents=True)
    journal.write_text(
        json.dumps(
            {
                "stage": "dispatch-id",
                "work_item_id": "overseer-gamma.1",
                "dispatch_id": "remote-run",
                "at": "2026-08-22T09:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _snapshot(
        path=snapshot_path,
        repo=repo,
        rows=[{"repo": str(repo), "topic": "gamma", "status": "blocked:human", "tmux": "gamma"}],
    )

    roster = foreman_plan_roster.compose_roster(
        repo=repo,
        snapshot_path=snapshot_path,
        tmux_sessions=["gamma"],
        journal_path=journal,
    )

    assert roster["rows"][0]["session_state"] == "picker-parked"
    assert roster["rows"][0]["work_state"] == "work-in-flight"
    assert roster["rows"][0]["emoji"] == "🔴"


def test_picker_session_state_and_legacy_anchor_work_state_edges(*, tmp_path):
    repo = tmp_path / "repo"
    snapshot_path = tmp_path / "status.json"
    _plan(repo=repo, topic="alpha")
    (repo / "plan" / "alpha" / "epic.md").write_text(
        "**Ledger anchor:** epic **`overseer-alpha`**\n",
        encoding="utf-8",
    )
    _snapshot(
        path=snapshot_path,
        repo=repo,
        rows=[{"repo": str(repo), "topic": "alpha", "status": "picker-stalled", "tmux": "alpha"}],
    )

    roster = foreman_plan_roster.compose_roster(
        repo=repo,
        snapshot_path=snapshot_path,
        tmux_sessions=["alpha"],
    )

    assert roster["rows"][0]["session_state"] == "picker-parked"
    assert roster["rows"][0]["work_state"] == "no-work-in-flight"
    assert foreman_plan_roster_work.plan_epic_anchor(repo=repo, plan="alpha") == "overseer-alpha"


def test_anchorless_and_malformed_journal_records_are_non_running_edges(*, tmp_path):
    repo = tmp_path / "repo"
    _plan(repo=repo, topic="alpha")
    (repo / "plan" / "alpha" / "epic.md").write_text(
        "# Ledger epic anchor\n\nNo anchor yet.\n",
        encoding="utf-8",
    )
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text(
        "\n".join(
            [
                "{not-json",
                "[]",
                json.dumps(
                    {"stage": "dispatch-id", "work_item_id": 7, "at": "2026-08-22T00:00:00Z"}
                ),
                json.dumps({"stage": "ignored", "work_item_id": "overseer-alpha.1"}),
                json.dumps({"stage": "outcome", "outcome": []}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    records = foreman_plan_roster_work.journal_records(path=journal)
    assert foreman_plan_roster_work.plan_epic_anchor(repo=repo, plan="alpha") is None
    assert foreman_plan_roster_work.work_states_by_plan(
        repo=repo,
        plan_names=["alpha"],
        journal_path=journal,
    ) == {"alpha": "no-work-in-flight"}
    assert (
        foreman_plan_roster_work.child_in_flight(
            child_id="overseer-alpha.1",
            dispatch_times=foreman_plan_roster_work.latest_dispatch_times(records=records),
            outcomes=foreman_plan_roster_work.outcome_times(records=records),
        )
        is False
    )
    assert (
        foreman_plan_roster_work.record_work_item_id(record={"stage": "outcome", "outcome": []})
        is None
    )
    assert foreman_plan_roster_work.record_work_item_id(record={"stage": "ignored"}) is None


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
