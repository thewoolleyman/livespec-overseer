"""Foreman plan roster helper contract."""

from __future__ import annotations

import json
import re
from pathlib import Path

import foreman_plan_roster

__all__: list[str] = []

FOREMAN_PROSE = Path(__file__).resolve().parents[1] / ".claude-plugin" / "prose" / "foreman.md"


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


def _anchored_plan(*, repo: Path, topic: str, epic: str) -> None:
    _plan(repo=repo, topic=topic)
    (repo / "plan" / topic / "epic.md").write_text(
        f"# Ledger epic anchor\n\n{epic}\n\n",
        encoding="utf-8",
    )


def _write_journal(*, repo: Path, records: list[dict[str, object]]) -> None:
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n",
        encoding="utf-8",
    )


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
    assert rows["alpha"]["session_state"] == "working"
    assert rows["alpha"]["emoji"] == "🟢"
    assert rows["beta"]["name_identity_verdict"] == "ok"
    assert rows["beta"]["session_state"] == "no-session"
    assert rows["beta"]["emoji"] == "⚪"
    assert rows["gamma"]["session_state"] == "no-session"
    assert rows["gamma"]["emoji"] == "⚪"
    assert "foreign" not in rows


def test_roster_emits_separate_session_and_work_state_fields(*, tmp_path):
    repo = tmp_path / "repo"
    snapshot_path = tmp_path / "status.json"
    _anchored_plan(repo=repo, topic="alpha", epic="overseer-alpha")
    _write_snapshot(path=snapshot_path, repo=repo)

    roster = foreman_plan_roster.compose_roster(
        repo=repo,
        snapshot_path=snapshot_path,
        tmux_sessions=["alpha"],
    )

    row = roster["rows"][0]
    assert row["session_state"] == "working"
    assert row["work_state"] == "no-work-in-flight"
    assert "status" not in row
    assert "status_emoji" not in row


def test_work_state_uses_latest_dispatch_id_as_outcome_floor(*, tmp_path):
    repo = tmp_path / "repo"
    snapshot_path = tmp_path / "status.json"
    _anchored_plan(repo=repo, topic="alpha", epic="overseer-alpha")
    _write_snapshot(path=snapshot_path, repo=repo)
    _write_journal(
        repo=repo,
        records=[
            {
                "stage": "dispatch-id",
                "work_item_id": "overseer-alpha.1",
                "dispatch_id": "old-run",
                "at": "2026-08-22T00:00:00Z",
            },
            {
                "stage": "outcome",
                "outcome": {
                    "work_item_id": "overseer-alpha.1",
                    "status": "failed",
                    "stage": "fabro-run",
                },
                "at": "2026-08-22T00:10:00Z",
            },
            {
                "stage": "dispatch-id",
                "work_item_id": "overseer-alpha.1",
                "dispatch_id": "current-run",
                "at": "2026-08-22T01:00:00Z",
            },
        ],
    )

    roster = foreman_plan_roster.compose_roster(
        repo=repo,
        snapshot_path=snapshot_path,
        tmux_sessions=["alpha"],
    )

    assert roster["rows"][0]["work_state"] == "work-in-flight"


def test_remote_dispatch_absent_from_local_process_view_is_still_in_flight(*, tmp_path):
    repo = tmp_path / "repo"
    snapshot_path = tmp_path / "status.json"
    _anchored_plan(repo=repo, topic="alpha", epic="overseer-alpha")
    _write_snapshot(path=snapshot_path, repo=repo)
    _write_journal(
        repo=repo,
        records=[
            {
                "stage": "dispatch-id",
                "work_item_id": "overseer-alpha.2",
                "dispatch_id": "remote-run",
                "dispatch_factory": "hp",
                "at": "2026-08-22T02:00:00Z",
            }
        ],
    )

    roster = foreman_plan_roster.compose_roster(
        repo=repo,
        snapshot_path=snapshot_path,
        tmux_sessions=["alpha"],
    )

    assert roster["rows"][0]["work_state"] == "work-in-flight"


def test_caller_supplied_emoji_is_ignored_and_idle_in_flight_waits(*, tmp_path):
    repo = tmp_path / "repo"
    snapshot_path = tmp_path / "status.json"
    _anchored_plan(repo=repo, topic="alpha", epic="overseer-alpha")
    snapshot_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "daemon_instance_id": "daemon-1",
                "tick_generation": 12,
                "rows": [
                    {
                        "repo": str(repo),
                        "topic": "alpha",
                        "tmux": "alpha",
                        "runtime": "codex",
                        "status": "idle",
                        "emoji": "🟢",
                        "status_emoji": "🟢",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _write_journal(
        repo=repo,
        records=[
            {
                "stage": "dispatch-id",
                "work_item_id": "overseer-alpha.3",
                "dispatch_id": "remote-run",
                "at": "2026-08-22T02:00:00Z",
            }
        ],
    )

    roster = foreman_plan_roster.compose_roster(
        repo=repo,
        snapshot_path=snapshot_path,
        tmux_sessions=["alpha"],
    )

    row = roster["rows"][0]
    assert row["session_state"] == "idle"
    assert row["work_state"] == "work-in-flight"
    assert row["emoji"] == "⏳"


def test_idle_without_work_is_stalled_not_waiting(*, tmp_path):
    repo = tmp_path / "repo"
    snapshot_path = tmp_path / "status.json"
    _anchored_plan(repo=repo, topic="alpha", epic="overseer-alpha")
    snapshot_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "daemon_instance_id": "daemon-1",
                "tick_generation": 12,
                "rows": [
                    {
                        "repo": str(repo),
                        "topic": "alpha",
                        "tmux": "alpha",
                        "runtime": "codex",
                        "status": "idle",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    roster = foreman_plan_roster.compose_roster(
        repo=repo,
        snapshot_path=snapshot_path,
        tmux_sessions=["alpha"],
    )

    row = roster["rows"][0]
    assert row["session_state"] == "idle"
    assert row["work_state"] == "no-work-in-flight"
    assert row["emoji"] == "⚪"


def test_picker_parked_and_idle_without_work_use_distinct_emojis() -> None:
    assert foreman_plan_roster.emoji_for_pair(
        session_state="picker-parked",
        work_state="no-work-in-flight",
    ) != foreman_plan_roster.emoji_for_pair(
        session_state="idle",
        work_state="no-work-in-flight",
    )


def test_pair_emoji_mapping_is_total() -> None:
    assert hasattr(foreman_plan_roster, "SESSION_STATES")
    assert hasattr(foreman_plan_roster, "WORK_STATES")
    assert hasattr(foreman_plan_roster, "emoji_for_pair")
    pairs = {
        (session_state, work_state)
        for session_state in foreman_plan_roster.SESSION_STATES
        for work_state in foreman_plan_roster.WORK_STATES
    }

    resolved = {
        pair: foreman_plan_roster.emoji_for_pair(
            session_state=pair[0],
            work_state=pair[1],
        )
        for pair in pairs
    }

    assert set(resolved) == pairs
    assert all(emoji in {"🔵", "🟢", "🔴", "⏳", "⚪"} for emoji in resolved.values())
    assert resolved[("idle", "work-in-flight")] == "⏳"
    assert resolved[("no-session", "work-in-flight")] == "⏳"
    assert resolved[("idle", "no-work-in-flight")] == "⚪"
    assert resolved[("no-session", "no-work-in-flight")] == "⚪"


def test_unmapped_pair_returns_incoherent_symbol() -> None:
    assert (
        foreman_plan_roster.emoji_for_pair(
            session_state="future-session-state",
            work_state="work-in-flight",
        )
        == "❗"
    )


def test_name_identity_mismatch_yields_incoherent_emoji(*, tmp_path):
    repo = tmp_path / "repo"
    snapshot_path = tmp_path / "status.json"
    _plan(repo=repo, topic="alpha")
    snapshot_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "daemon_instance_id": "daemon-1",
                "tick_generation": 12,
                "rows": [
                    {
                        "repo": str(repo),
                        "topic": "alpha",
                        "tmux": "wrong-name",
                        "runtime": "codex",
                        "status": "working",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    roster = foreman_plan_roster.compose_roster(
        repo=repo,
        snapshot_path=snapshot_path,
        tmux_sessions=["wrong-name"],
    )

    row = roster["rows"][0]
    assert row["name_identity_verdict"] == "daemon_tmux_name_mismatch"
    assert row["emoji"] == "❗"


def test_helper_and_prose_legend_symbols_match_mechanically() -> None:
    text = FOREMAN_PROSE.read_text(encoding="utf-8")
    legend_match = re.search(r"The legend is one line and names every symbol:\n([^\n]+)", text)
    assert legend_match is not None
    legend_symbols = set(re.findall(r"[🔵🔴🟢⏳⚪❗]", legend_match.group(1)))
    helper_symbols = {
        foreman_plan_roster.emoji_for_pair(
            session_state=session_state,
            work_state=work_state,
        )
        for session_state in foreman_plan_roster.SESSION_STATES
        for work_state in foreman_plan_roster.WORK_STATES
    }
    helper_symbols.add(
        foreman_plan_roster.emoji_for_pair(
            session_state="future-session-state",
            work_state="work-in-flight",
        )
    )

    assert helper_symbols == legend_symbols


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
    assert row["session_state"] == "no-session"
    assert roster["name_identity_errors"] == [
        {
            "kind": "tmux_session_without_plan",
            "tmux": "tmux-only",
        }
    ]


def test_roster_emits_once_per_tick_identity_and_again_for_a_new_tick(*, tmp_path, capsys):
    repo = tmp_path / "repo"
    _plan(repo=repo, topic="alpha")

    base_args = [
        "--repo",
        str(repo),
        "--snapshot-path",
        str(tmp_path / "missing.json"),
        "--tmux-session",
        "alpha",
        "--tick-identity",
    ]

    assert foreman_plan_roster.main(argv=[*base_args, "daemon-1:7"]) == 0
    assert foreman_plan_roster.main(argv=[*base_args, "daemon-1:7"]) == 0
    assert foreman_plan_roster.main(argv=[*base_args, "daemon-1:8"]) == 0

    emissions = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert [emission["tick_identity"] for emission in emissions] == [
        "daemon-1:7",
        "daemon-1:8",
    ]


def test_unactioned_counter_persists_across_processes_and_resets_on_action(*, tmp_path, capsys):
    repo = tmp_path / "repo"
    _plan(repo=repo, topic="alpha")

    base_args = [
        "--repo",
        str(repo),
        "--snapshot-path",
        str(tmp_path / "missing.json"),
        "--tmux-session",
        "alpha",
    ]

    assert foreman_plan_roster.main(argv=[*base_args, "--tick-identity", "daemon-1:1"]) == 0
    assert foreman_plan_roster.main(argv=[*base_args, "--tick-identity", "daemon-1:2"]) == 0
    assert (
        foreman_plan_roster.main(
            argv=[
                *base_args,
                "--tick-identity",
                "daemon-1:3",
                "--actioned-plan",
                "alpha",
            ]
        )
        == 0
    )

    emissions = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert [emission["rows"][0]["consecutive_unactioned_ticks"] for emission in emissions] == [
        1,
        2,
        0,
    ]

    state_path = repo / "tmp" / "overseer" / "foreman" / "plan-roster-state.json"
    assert state_path.is_file()
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "emitted_tick_identities": ["daemon-1:1", "daemon-1:2", "daemon-1:3"],
        "plans": {"alpha": {"consecutive_unactioned_ticks": 0}},
        "schema_version": 1,
    }
    assert not list((repo / "plan" / "alpha").glob("*roster*"))
