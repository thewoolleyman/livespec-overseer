"""Tests for foreman_gather.py — deterministic Phase A composition."""

from __future__ import annotations

import importlib
import json
import sys
from hashlib import sha256
from pathlib import Path

import pytest

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
MODULE_PATH = OVERSEER_DIR / "foreman_gather.py"

__all__: list[str] = []


def foreman_gather():
    assert MODULE_PATH.is_file()
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_gather")


def foreman_gather_collect():
    _ = foreman_gather()
    return importlib.import_module("foreman_gather_collect")


def foreman_gather_sources():
    _ = foreman_gather()
    return importlib.import_module("foreman_gather_sources")


def foreman_gather_snapshot():
    _ = foreman_gather()
    return importlib.import_module("foreman_gather_snapshot")


def foreman_runtime_document():
    _ = foreman_gather()
    return importlib.import_module("foreman_runtime_document")


def write_json(*, path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(*, path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records),
        encoding="utf-8",
    )


def test_composes_canonical_document_from_snapshot_attention_and_journal(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "plan" / "plan-a").mkdir(parents=True)
    snapshot_path = tmp_path / "status.json"
    attention_path = repo / "attention.json"
    journal_path = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    journal_path.parent.mkdir()
    write_json(
        path=snapshot_path,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "written_at": "2026-08-03T08:00:00Z",
            "rows": [
                {
                    "acked": False,
                    "ctx": 42,
                    "human_wait": False,
                    "note": "low context",
                    "progress_now": True,
                    "repo": str(repo),
                    "round_open": True,
                    "runtime": "codex",
                    "session_identity": "codex:abc",
                    "status": "warned",
                    "tmux": "alpha",
                    "topic": "plan-a",
                },
                {
                    "acked": False,
                    "ctx": None,
                    "human_wait": False,
                    "note": None,
                    "progress_now": False,
                    "repo": str(tmp_path / "other"),
                    "round_open": False,
                    "runtime": None,
                    "session_identity": "none:/other:plan-b",
                    "status": "unassigned",
                    "tmux": None,
                    "topic": "plan-b",
                },
            ],
        },
    )
    write_json(
        path=attention_path,
        payload={
            "schema_version": 1,
            "generated_at": "2026-08-03T08:01:00Z",
            "items": [{"id": "overseer-a", "kind": "impl_next", "title": "ship it"}],
        },
    )
    write_jsonl(
        path=journal_path,
        records=[
            {"at": "2026-08-03T07:59:00Z", "action": "impl:old"},
            {"at": "2026-08-03T08:02:00Z", "action": "impl:overseer-a"},
        ],
    )

    document = module.compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        needs_attention_command=["/bin/cat", str(attention_path)],
        journal_path=journal_path,
        now=lambda: "2026-08-03T08:03:00Z",
        journal_limit=1,
    )

    assert document == {
        "schema_version": 1,
        "generated_at": "2026-08-03T08:03:00Z",
        "repo": str(repo),
        "sources": {
            "dispatch_journal": {
                "path": str(journal_path),
                "records_read": 1,
                "status": "ok",
            },
            "needs_attention": {"command": ["/bin/cat", str(attention_path)], "status": "ok"},
            "snapshot": {
                "freshness": {
                    "mtime": pytest.approx(snapshot_path.stat().st_mtime),
                    "tick_generation": 7,
                    "written_at": "2026-08-03T08:00:00Z",
                },
                "mode": "daemon-snapshot",
                "path": str(snapshot_path),
                "rows_total": 2,
                "rows_used": 1,
                "status": "ok",
            },
        },
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "rows": [
                {
                    "acked": False,
                    "ctx": 42,
                    "human_wait": False,
                    "note": "low context",
                    "progress_now": True,
                    "repo": str(repo),
                    "round_open": True,
                    "runtime": "codex",
                    "session_identity": "codex:abc",
                    "status": "warned",
                    "supervisor_handoff": "missing",
                    "tmux": "alpha",
                    "topic": "plan-a",
                }
            ],
            "tick_generation": 7,
            "written_at": "2026-08-03T08:00:00Z",
        },
        "needs_attention": {
            "generated_at": "2026-08-03T08:01:00Z",
            "items": [{"id": "overseer-a", "kind": "impl_next", "title": "ship it"}],
            "schema_version": 1,
        },
        "dispatch_journal": [{"action": "impl:overseer-a", "at": "2026-08-03T08:02:00Z"}],
    }


def test_snapshot_rows_carry_supervisor_handoff_presence(*, tmp_path):
    module = foreman_gather()
    collect = foreman_gather_collect()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "plan" / "with-binder").mkdir(parents=True)
    (repo / "plan" / "with-binder" / "supervisor-handoff.md").write_text(
        "supervise this\n", encoding="utf-8"
    )
    (repo / "plan" / "without-binder").mkdir(parents=True)
    snapshot_path = tmp_path / "status.json"
    write_json(
        path=snapshot_path,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "written_at": "2026-08-03T08:00:00Z",
            "rows": [
                {
                    "repo": str(repo),
                    "topic": "with-binder",
                    "status": "session-gone",
                },
                {
                    "repo": str(repo),
                    "topic": "without-binder",
                    "status": "session-gone",
                },
                {
                    "repo": str(repo),
                    "topic": "orphan",
                    "status": "session-gone",
                },
                {
                    "repo": str(repo),
                    "topic": "alpha-supervisor",
                    "status": "session-gone",
                },
            ],
        },
    )

    document = module.compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
        now=lambda: "2026-08-03T08:03:00Z",
    )

    rows = document["snapshot"]["rows"]
    assert rows == [
        {
            "repo": str(repo),
            "status": "session-gone",
            "supervisor_handoff": "present",
            "topic": "with-binder",
        },
        {
            "repo": str(repo),
            "status": "session-gone",
            "supervisor_handoff": "missing",
            "topic": "without-binder",
        },
        {
            "repo": str(repo),
            "status": "session-gone",
            "supervisor_handoff": "not-plan",
            "topic": "orphan",
        },
        {
            "repo": str(repo),
            "status": "session-gone",
            "supervisor_handoff": "supervisor-topic",
            "topic": "alpha-supervisor",
        },
    ]
    assert collect.supervisor_handoff_state(repo=repo, topic=None) == "unknown"
    assert "with-binder | session-gone | ctx=None | human_wait=no | supervisor=present" in (
        module.render_document(document=document)
    )
    assert "without-binder | session-gone | ctx=None | human_wait=no | supervisor=missing" in (
        module.render_document(document=document)
    )
    assert "orphan | session-gone | ctx=None | human_wait=no | supervisor=not-plan" in (
        module.render_document(document=document)
    )
    assert (
        "alpha-supervisor | session-gone | ctx=None | human_wait=no | "
        "supervisor=supervisor-topic"
    ) in module.render_document(document=document)


def test_snapshot_rows_carry_foreman_row_evidence(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "plan" / "plan-a").mkdir(parents=True)
    (repo / "changed.txt").write_text("pending\n", encoding="utf-8")
    pane_text = "Do you want to proceed?\n> 1. Yes\n  2. No\n"
    snapshot_path = tmp_path / "status.json"
    write_json(
        path=snapshot_path,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "written_at": "2026-08-03T08:00:00Z",
            "rows": [
                {
                    "ctx": 42,
                    "human_wait": True,
                    "picker_open": True,
                    "repo": str(repo),
                    "stall_seconds": 185,
                    "status": "blocked:human",
                    "supervisor_state_age": 12.5,
                    "tmux": "alpha",
                    "topic": "plan-a",
                }
            ],
        },
    )

    document = module.compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
        now=lambda: "2026-08-03T08:03:00Z",
        pane_captures={"alpha": pane_text},
    )

    row = document["snapshot"]["rows"][0]
    assert row["picker_open"] is True
    assert row["stall_seconds"] == 185
    assert row["supervisor_state_age"] == 12.5
    assert row["proposed_changes_count"] == 1
    assert row["pane_content_hash"] == sha256(pane_text.encode("utf-8")).hexdigest()
    rendered = module.render_document(document=document)
    assert "picker_open=yes" in rendered
    assert "stall_seconds=185" in rendered
    assert "supervisor_state_age=12.5" in rendered
    assert "proposed_changes=1" in rendered
    assert f"pane_hash={row['pane_content_hash'][:12]}" in rendered


def test_runtime_fingerprint_changes_when_tracked_stall_age_rises(*, tmp_path):
    module = foreman_runtime_document()
    repo = tmp_path / "repo"
    row = {
        "ctx": 42,
        "human_wait": True,
        "pane_content_hash": "same-pane",
        "picker_open": True,
        "progress_now": False,
        "proposed_changes_count": 0,
        "repo": str(repo),
        "round_open": False,
        "session_identity": "codex:alpha",
        "status": "blocked:human",
        "supervisor_state_age": 3.0,
        "tmux": "alpha",
        "topic": "plan-a",
    }
    first = {"snapshot": {"rows": [row]}, "needs_attention": {"items": []}}
    second = {
        "snapshot": {"rows": [{**row, "stall_seconds": 185}]},
        "needs_attention": {"items": []},
    }

    assert module.foreman_document(payload=first).fingerprint != (
        module.foreman_document(payload=second).fingerprint
    )


def test_supervisor_handoff_uses_shipped_reserved_topic_predicate(*, tmp_path, monkeypatch):
    collect = foreman_gather_collect()
    repo = tmp_path / "repo"
    (repo / "plan" / "synthetic-worker").mkdir(parents=True)

    def reserved_override(*, topic: str) -> bool:
        return topic == "synthetic-worker"

    monkeypatch.setattr(collect.signals, "topic_reserved_for_supervisor", reserved_override)

    assert collect.supervisor_handoff_state(repo=repo, topic="synthetic-worker") == (
        "supervisor-topic"
    )


def test_snapshot_rows_accept_migrated_ledger_backed_supervisor_state(*, tmp_path):
    module = foreman_gather()
    collect = foreman_gather_collect()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "plan" / "legacy-binder").mkdir(parents=True)
    (repo / "plan" / "legacy-binder" / "supervisor-handoff.md").write_text(
        "supervise this\n", encoding="utf-8"
    )
    (repo / "plan" / "migrated-binder").mkdir(parents=True)
    (repo / "plan" / "migrated-binder" / "epic.md").write_text(
        "# Plan Epic\n\n"
        "Ledger epic: `overseer-test-epic`\n\n"
        "The supervisor binder is read from attributed ledger comments.\n",
        encoding="utf-8",
    )
    (repo / "plan" / "not-ledger-backed").mkdir(parents=True)
    (repo / "plan" / "not-ledger-backed" / "epic.md").write_text(
        "# Plan Epic\n\n" "This file names planning context but no migrated supervisor state.\n",
        encoding="utf-8",
    )
    snapshot_path = tmp_path / "status.json"
    write_json(
        path=snapshot_path,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "written_at": "2026-08-03T08:00:00Z",
            "rows": [
                {"repo": str(repo), "topic": "legacy-binder", "status": "session-gone"},
                {"repo": str(repo), "topic": "migrated-binder", "status": "session-gone"},
                {"repo": str(repo), "topic": "not-ledger-backed", "status": "session-gone"},
            ],
        },
    )

    document = module.compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
        now=lambda: "2026-08-03T08:03:00Z",
    )

    rows = document["snapshot"]["rows"]
    assert [row["supervisor_handoff"] for row in rows] == ["present", "present", "missing"]
    assert collect.supervisor_handoff_state(repo=repo, topic="migrated-binder") == "present"
    rendered = module.render_document(document=document)
    assert "legacy-binder | session-gone | ctx=None | human_wait=no | supervisor=present" in (
        rendered
    )
    assert "migrated-binder | session-gone | ctx=None | human_wait=no | supervisor=present" in (
        rendered
    )
    assert "not-ledger-backed | session-gone | ctx=None | human_wait=no | supervisor=missing" in (
        rendered
    )


def test_snapshot_fallback_is_marked_observation_only(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    fallback_path = tmp_path / "list.json"
    write_json(
        path=fallback_path,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "cli",
            "tick_generation": 1,
            "written_at": "2026-08-03T08:00:00Z",
            "rows": [],
        },
    )

    document = module.compose_document(
        repo=repo,
        snapshot_path=tmp_path / "missing.json",
        list_json_command=["/bin/cat", str(fallback_path)],
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
        now=lambda: "2026-08-03T08:03:00Z",
    )

    assert document["sources"]["snapshot"]["mode"] == "list-json-observation-only"
    assert document["snapshot"]["daemon_instance_id"] == "cli"


def test_embedded_and_fixture_attention_feed_needs_you_render(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    snapshot_path = tmp_path / "status.json"
    attention = {
        "schema_version": 1,
        "items": [{"id": "overseer-b", "kind": "approve", "tmux": "beta", "title": "approve me"}],
    }
    write_json(
        path=snapshot_path,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "daemon-1",
            "tick_generation": 1,
            "rows": [{"repo": str(repo), "topic": "beta", "tmux": "beta"}],
            "needs_attention": attention,
        },
    )

    embedded = module.compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
    )

    assert embedded["needs_attention"] == attention
    assert "\nNEEDS YOU:\n  overseer-b | beta | approve | approve me\n" in (
        module.render_document(document=embedded)
    )

    (repo / "attention.json").write_text(json.dumps(attention), encoding="utf-8")
    fixture = module.compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
    )
    assert fixture["needs_attention"] == attention


def test_release_lane_replay_routes_detector_finding_to_attention_surface(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    snapshot_path = tmp_path / "status.json"
    write_json(
        path=snapshot_path,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "daemon-1",
            "tick_generation": 1,
            "written_at": "2026-08-20T08:00:00Z",
            "rows": [],
        },
    )
    history = json.loads((Path(__file__).resolve().parent / "release-tag-history.json").read_text())
    window = [
        row
        for row in history
        if "2026-08-03T03:38:02Z" <= row["created_at"] <= "2026-08-19T12:11:08Z"
    ]

    document = module.compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
        now=lambda: "2026-08-20T08:03:00Z",
        release_lane_enabled=True,
        release_lane_workflow="release-tag",
        release_lane_runs=window,
    )

    assert document["sources"]["release_lane"] == {
        "mode": "provided-history",
        "runs_considered": 124,
        "status": "ok",
        "workflow": "release-tag",
    }
    assert document["needs_attention"]["items"] == [
        {
            "id": "release-lane:release-tag",
            "kind": "release-lane",
            "title": (
                "release-tag: FAILING — 123 consecutive runs since "
                "2026-08-03T05:31:01Z; last green 2026-08-03T03:38:02Z"
            ),
        }
    ]
    assert (
        "\nneeds attention:\n  release-lane:release-tag | release-lane | " "release-tag: FAILING"
    ) in module.render_document(document=document)


def test_healthy_release_lane_stays_silent_on_attention_surface(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    snapshot_path = tmp_path / "status.json"
    write_json(
        path=snapshot_path,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "daemon-1",
            "tick_generation": 1,
            "written_at": "2026-08-20T08:00:00Z",
            "rows": [],
        },
    )

    document = module.compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
        release_lane_enabled=True,
        release_lane_workflow="release-tag",
        release_lane_runs=[
            {"conclusion": "success", "created_at": "2026-08-20T08:19:21Z"},
            {"conclusion": "success", "created_at": "2026-08-20T09:46:04Z"},
        ],
    )

    assert document["sources"]["release_lane"]["status"] == "ok"
    assert document["needs_attention"] == {"items": []}
    assert "\nneeds attention:\n  none\n" in module.render_document(document=document)


def test_unreachable_release_lane_source_surfaces_unknown_with_staleness(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    snapshot_path = tmp_path / "status.json"
    cache_path = repo / "tmp" / "overseer" / "release-lane-watch.json"
    cache_path.parent.mkdir(parents=True)
    write_json(
        path=snapshot_path,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "daemon-1",
            "tick_generation": 1,
            "written_at": "2026-08-20T08:00:00Z",
            "rows": [],
        },
    )
    write_json(
        path=cache_path,
        payload={
            "measured_at": "2026-08-20T07:00:00Z",
            "workflow": "release-tag",
            "state": {"healthy": True, "runs_considered": 12},
        },
    )

    document = module.compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
        now=lambda: "2026-08-20T08:03:00Z",
        release_lane_enabled=True,
        release_lane_workflow="release-tag",
        release_lane_fetcher=lambda: None,
        release_lane_cache_path=cache_path,
    )

    assert document["sources"]["release_lane"] == {
        "last_successful_measurement_at": "2026-08-20T07:00:00Z",
        "reason": "forge unreachable or unavailable",
        "status": "unknown",
        "workflow": "release-tag",
    }
    assert document["needs_attention"]["items"] == [
        {
            "id": "release-lane:release-tag",
            "kind": "release-lane-unknown",
            "title": (
                "release-tag: UNKNOWN — could not measure release lane; "
                "last successful measurement 2026-08-20T07:00:00Z"
            ),
        }
    ]


def test_snapshot_reader_distinguishes_malformed_from_non_object_json(*, tmp_path):
    module = foreman_gather_snapshot()
    repo = tmp_path / "repo"
    repo.mkdir()
    snapshot_path = tmp_path / "status.json"

    snapshot_path.write_text("{oops}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="snapshot produced malformed JSON"):
        module.read_snapshot(
            repo=repo,
            snapshot_path=snapshot_path,
            list_json_command=None,
        )

    snapshot_path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="snapshot produced non-object JSON"):
        module.read_snapshot(
            repo=repo,
            snapshot_path=snapshot_path,
            list_json_command=None,
        )


def test_unreachable_inputs_are_skipped_and_named(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()

    document = module.compose_document(
        repo=repo,
        snapshot_path=tmp_path / "missing-status.json",
        list_json_command=None,
        needs_attention_command=["/definitely/missing/needs_attention.py", "--json"],
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
        now=lambda: "2026-08-03T08:03:00Z",
    )

    assert document["sources"]["snapshot"] == {
        "path": str(tmp_path / "missing-status.json"),
        "reason": "snapshot unavailable and no list --json fallback configured",
        "status": "skipped",
    }
    assert document["sources"]["needs_attention"] == {
        "command": ["/definitely/missing/needs_attention.py", "--json"],
        "reason": "command not found",
        "status": "skipped",
    }
    assert document["sources"]["dispatch_journal"] == {
        "path": str(repo / "tmp" / "fabro-dispatch-journal.jsonl"),
        "reason": "file not found",
        "status": "skipped",
    }

    fallback_missing = module.compose_document(
        repo=repo,
        snapshot_path=tmp_path / "missing-status.json",
        list_json_command=["/definitely/missing/overseer", "list", "--json"],
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
    )
    assert fallback_missing["sources"]["snapshot"] == {
        "command": ["/definitely/missing/overseer", "list", "--json"],
        "reason": "command not found",
        "status": "skipped",
    }


def test_malformed_primitive_output_is_rejected(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    primitive_path = tmp_path / "primitive.json"
    primitive_path.write_text("17\n", encoding="utf-8")

    with pytest.raises(module.ValidationError, match="needs_attention"):
        module.compose_document(
            repo=repo,
            snapshot_path=tmp_path / "missing.json",
            needs_attention_command=["/bin/cat", str(primitive_path)],
            journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
        )


def test_render_is_stable_and_token_free(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    document = {
        "schema_version": 1,
        "generated_at": "2026-08-03T08:03:00Z",
        "repo": str(repo),
        "sources": {
            "snapshot": {"status": "ok", "mode": "daemon-snapshot", "rows_used": 1},
            "needs_attention": {"status": "skipped", "reason": "command not configured"},
            "dispatch_journal": {"status": "ok", "records_read": 1},
        },
        "snapshot": {
            "rows": [
                {
                    "topic": "plan-a",
                    "status": "warned",
                    "ctx": 42,
                    "human_wait": False,
                    "note": "low context",
                }
            ]
        },
        "needs_attention": None,
        "dispatch_journal": [{"action": "impl:overseer-a"}],
    }

    assert module.render_document(document=document) == (
        "foreman-gather 2026-08-03T08:03:00Z\n"
        f"repo: {repo}\n"
        "sources: snapshot=ok daemon-snapshot rows=1; needs_attention=skipped "
        "command not configured; dispatch_journal=ok records=1\n"
        "\n"
        "snapshot rows:\n"
        "  plan-a | warned | ctx=42 | human_wait=no | low context\n"
        "\n"
        "needs attention:\n"
        "  none\n"
        "\n"
        "dispatch journal:\n"
        "  impl:overseer-a\n"
    )


def test_render_lists_attention_items_and_empty_sections(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()

    assert module.render_document(
        document={
            "schema_version": 1,
            "generated_at": "2026-08-03T08:03:00Z",
            "repo": str(repo),
            "sources": {
                "snapshot": {"status": "ok", "mode": "daemon-snapshot", "rows_used": 0},
                "needs_attention": {"status": "ok"},
                "dispatch_journal": {"status": "skipped"},
            },
            "snapshot": {"rows": []},
            "needs_attention": {
                "items": [{"id": "overseer-b", "kind": "approve", "title": "approve me"}]
            },
            "dispatch_journal": [],
        }
    ) == (
        "foreman-gather 2026-08-03T08:03:00Z\n"
        f"repo: {repo}\n"
        "sources: snapshot=ok daemon-snapshot rows=0; needs_attention=ok; "
        "dispatch_journal=skipped records=None\n"
        "\n"
        "snapshot rows:\n"
        "  none\n"
        "\n"
        "needs attention:\n"
        "  overseer-b | approve | approve me\n"
        "\n"
        "dispatch journal:\n"
        "  none\n"
    )


def test_snapshot_validation_rejects_malformed_primitives(*, tmp_path):
    module = foreman_gather_collect()
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(ValueError, match="primitive"):
        module.compose_document(
            repo=repo,
            snapshot_path=tmp_path / "missing_rows.json",
            list_json_command=["/bin/echo", '{"schema_version": 1, "tick_generation": 1}'],
            needs_attention_command=None,
        )
    with pytest.raises(TypeError, match="tick_generation"):
        module.compose_document(
            repo=repo,
            snapshot_path=tmp_path / "bad_generation.json",
            list_json_command=[
                "/bin/echo",
                '{"schema_version": 1, "tick_generation": true, "rows": []}',
            ],
            needs_attention_command=None,
        )
    with pytest.raises(ValueError, match="row"):
        module.compose_document(
            repo=repo,
            snapshot_path=tmp_path / "bad_row.json",
            list_json_command=[
                "/bin/echo",
                '{"schema_version": 1, "tick_generation": 1, "rows": [17]}',
            ],
            needs_attention_command=None,
        )


def test_snapshot_fallback_command_failures_are_skip_annotations(*, tmp_path):
    module = foreman_gather_collect()
    repo = tmp_path / "repo"
    repo.mkdir()

    document = module.compose_document(
        repo=repo,
        snapshot_path=tmp_path / "missing.json",
        list_json_command=["/bin/sh", "-c", "exit 7"],
        needs_attention_command=None,
        journal_path=repo / "tmp" / "fabro-dispatch-journal.jsonl",
    )

    assert document["sources"]["snapshot"] == {
        "command": ["/bin/sh", "-c", "exit 7"],
        "reason": "exit 7",
        "status": "skipped",
    }

    attention_failed = module.compose_document(
        repo=repo,
        snapshot_path=tmp_path / "missing.json",
        needs_attention_command=["/bin/sh", "-c", "exit 8"],
        journal_path=str(repo / "tmp" / "fabro-dispatch-journal.jsonl"),
    )
    assert attention_failed["sources"]["needs_attention"] == {
        "command": ["/bin/sh", "-c", "exit 8"],
        "reason": "exit 8",
        "status": "skipped",
    }


def test_invalid_options_are_rejected(*, tmp_path):
    module = foreman_gather_collect()
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(TypeError, match="now"):
        module.compose_document(repo=repo, needs_attention_command=None, now="soon")
    with pytest.raises(TypeError, match="journal_limit"):
        module.compose_document(repo=repo, needs_attention_command=None, journal_limit=True)
    with pytest.raises(TypeError, match="journal_path"):
        module.compose_document(repo=repo, needs_attention_command=None, journal_path=17)


def test_attention_without_items_renders_as_empty(*, tmp_path):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()

    rendered = module.render_document(
        document={
            "schema_version": 1,
            "generated_at": "2026-08-03T08:03:00Z",
            "repo": str(repo),
            "sources": {
                "snapshot": {"status": "ok", "mode": "daemon-snapshot", "rows_used": 0},
                "needs_attention": {"status": "ok"},
                "dispatch_journal": {"status": "ok", "records_read": 0},
            },
            "snapshot": {"rows": []},
            "needs_attention": {},
            "dispatch_journal": [],
        }
    )

    assert "\nneeds attention:\n  none\n" in rendered


def test_default_needs_attention_command_uses_repo_credential_wrapper(*, tmp_path):
    module = foreman_gather_sources()
    repo = tmp_path / "repo"
    repo.mkdir()
    script = repo / "needs_attention.py"
    script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    (repo / ".livespec.jsonc").write_text(
        '{\n  "credential_wrapper": ["/wrap", "--"],\n'
        '  "url": "https://example.test//kept"\n}\n',
        encoding="utf-8",
    )

    assert module.default_needs_attention_command(repo=repo) == [
        "/wrap",
        "--",
        sys.executable,
        str(script),
        "--json",
    ]
    assert module.strip_jsonc_line_comment(line='"//kept" // dropped') == '"//kept" '
    assert module.strip_jsonc_line_comment(line='"quote \\" // kept" // dropped') == (
        '"quote \\" // kept" '
    )


def test_default_needs_attention_command_handles_absent_or_bad_config(*, tmp_path):
    module = foreman_gather_sources()
    repo = tmp_path / "repo"
    repo.mkdir()

    assert module.default_needs_attention_command(repo=repo) is None
    script = repo / "needs_attention.py"
    script.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    assert module.default_needs_attention_command(repo=repo) == [
        sys.executable,
        str(script),
        "--json",
    ]
    (repo / ".livespec.jsonc").write_text('{"credential_wrapper": "bad"}\n', encoding="utf-8")
    assert module.default_needs_attention_command(repo=repo) == [
        sys.executable,
        str(script),
        "--json",
    ]


def test_run_json_command_fail_soft_edges(*, monkeypatch):
    vendor_root = OVERSEER_DIR / "_vendor"
    assert (vendor_root / "returns").is_dir()
    assert (vendor_root / "typing_extensions").is_dir()
    assert not (vendor_root / "returns" / "contrib").exists()

    module = foreman_gather_sources()
    returns_io = importlib.import_module("overseer._vendor.returns.io")
    returns_pipeline = importlib.import_module("overseer._vendor.returns.pipeline")
    returns_unsafe = importlib.import_module("overseer._vendor.returns.unsafe")

    def boom(*args, **kwargs):
        del args, kwargs
        raise OSError

    monkeypatch.setattr(module.subprocess, "run", boom)
    skipped = module.run_json_command(command=["tool"], source_name="demo")
    assert isinstance(skipped, returns_io.IOSuccess)
    assert returns_unsafe.unsafe_perform_io(skipped.unwrap()) == {"__skip_reason__": "OSError"}
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: module.subprocess.CompletedProcess(
            args=args, returncode=0, stdout="[]\n", stderr=""
        ),
    )
    malformed = module.run_json_command(command=["tool"], source_name="demo")
    assert not returns_pipeline.is_successful(malformed)
    error = returns_unsafe.unsafe_perform_io(malformed.failure())
    assert error.detail == "demo produced non-object JSON"
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: module.subprocess.CompletedProcess(
            args=args, returncode=0, stdout="{oops}\n", stderr=""
        ),
    )
    malformed_json = module.run_json_command(command=["tool"], source_name="demo")
    assert not returns_pipeline.is_successful(malformed_json)
    error = returns_unsafe.unsafe_perform_io(malformed_json.failure())
    assert error.detail == "demo produced malformed JSON"


def test_journal_reader_rejects_malformed_records_and_limits_to_zero(*, tmp_path):
    module = foreman_gather_sources()
    returns_io = importlib.import_module("overseer._vendor.returns.io")
    returns_pipeline = importlib.import_module("overseer._vendor.returns.pipeline")
    returns_unsafe = importlib.import_module("overseer._vendor.returns.unsafe")
    journal = tmp_path / "journal.jsonl"
    write_jsonl(path=journal, records=[{"action": "one"}])

    limited = module.read_journal(path=journal, limit=0)
    assert isinstance(limited, returns_io.IOSuccess)
    assert returns_unsafe.unsafe_perform_io(limited.unwrap()) == (
        [],
        {"path": str(journal), "records_read": 0, "status": "ok"},
    )
    journal.write_text("{}\nnot-json\n", encoding="utf-8")
    malformed = module.read_journal(path=journal, limit=20)
    assert not returns_pipeline.is_successful(malformed)
    error = returns_unsafe.unsafe_perform_io(malformed.failure())
    assert error.detail == "dispatch_journal contains malformed JSONL"
    journal.write_text("{}\n[]\n", encoding="utf-8")
    non_object = module.read_journal(path=journal, limit=20)
    assert not returns_pipeline.is_successful(non_object)
    error = returns_unsafe.unsafe_perform_io(non_object.failure())
    assert error.detail == "dispatch_journal contains non-object JSONL"


def test_cli_emits_json_render_and_errors(*, tmp_path, capsys):
    module = foreman_gather()
    repo = tmp_path / "repo"
    repo.mkdir()
    snapshot = tmp_path / "status.json"
    write_json(
        path=snapshot,
        payload={
            "schema_version": 1,
            "daemon_instance_id": "daemon-1",
            "tick_generation": 1,
            "written_at": "2026-08-03T08:00:00Z",
            "rows": [],
        },
    )

    assert module.default_list_json_command()[-2:] == ["list", "--json"]
    assert (
        module.main(
            argv=[
                "--repo",
                str(repo),
                "--snapshot-path",
                str(snapshot),
                "--no-list-json-fallback",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["schema_version"] == 1

    assert (
        module.main(
            argv=[
                "--repo",
                str(repo),
                "--snapshot-path",
                str(snapshot),
                "--no-list-json-fallback",
                "--render",
            ]
        )
        == 0
    )
    assert "snapshot rows:\n  none" in capsys.readouterr().out

    bad_snapshot = tmp_path / "bad.json"
    bad_snapshot.write_text("17\n", encoding="utf-8")
    assert (
        module.main(
            argv=[
                "--repo",
                str(repo),
                "--snapshot-path",
                str(bad_snapshot),
                "--no-list-json-fallback",
            ]
        )
        == 1
    )
    assert "foreman-gather:" in capsys.readouterr().err


def test_unreadable_epic_is_distinguishable_from_a_topic_that_lacks_ledger_markers(*, tmp_path):
    """An epic.md the function could not read must not answer 'not migrated'.

    'Not migrated' is a definite negative about the topic — it is the answer that
    says this handoff still needs migrating. Returning it for a file that was
    never inspected asserts something about work the function did not look at.
    """
    collect = foreman_gather_collect()
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "plan" / "no-markers").mkdir(parents=True)
    (repo / "plan" / "no-markers" / "epic.md").write_text(
        "# Plan Epic\n\nPlanning context with no migrated supervisor state.\n",
        encoding="utf-8",
    )
    (repo / "plan" / "not-utf8").mkdir(parents=True)
    (repo / "plan" / "not-utf8" / "epic.md").write_bytes(b"\xff\xfe ledger entry\n")
    (repo / "plan" / "epic-is-a-directory").mkdir(parents=True)
    (repo / "plan" / "epic-is-a-directory" / "epic.md").mkdir()

    lacks_markers = collect.migrated_supervisor_handoff_state(repo=repo, topic="no-markers")
    not_utf8 = collect.migrated_supervisor_handoff_state(repo=repo, topic="not-utf8")
    is_a_directory = collect.migrated_supervisor_handoff_state(
        repo=repo, topic="epic-is-a-directory"
    )

    assert lacks_markers == "not-migrated"
    assert not_utf8 == "unreadable"
    assert is_a_directory == "unreadable"
    assert not_utf8 != lacks_markers
    assert is_a_directory != lacks_markers


def test_missing_epic_is_a_state_of_the_topic_not_a_fault(*, tmp_path):
    """A topic with no epic.md at all is an ordinary state, not an I/O fault.

    The two took the same branch before this split: a missing file and an
    unreadable one both raised OSError and both returned False. They are
    different facts and are reported differently.
    """
    collect = foreman_gather_collect()
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "plan" / "no-epic-file").mkdir(parents=True)
    (repo / "plan" / "not-utf8").mkdir(parents=True)
    (repo / "plan" / "not-utf8" / "epic.md").write_bytes(b"\xff\xfe ledger entry\n")

    absent = collect.migrated_supervisor_handoff_state(repo=repo, topic="no-epic-file")
    unreadable = collect.migrated_supervisor_handoff_state(repo=repo, topic="not-utf8")

    assert absent == "not-migrated"
    assert unreadable == "unreadable"
    assert absent != unreadable


def test_migrated_and_not_migrated_verdicts_are_unchanged(*, tmp_path):
    """Regression: the two happy paths keep their meaning through the widening."""
    collect = foreman_gather_collect()
    snapshot = foreman_gather_snapshot()
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "plan" / "migrated").mkdir(parents=True)
    (repo / "plan" / "migrated" / "epic.md").write_text(
        "# Plan Epic\n\nLedger epic: read the attributed comment stream.\n",
        encoding="utf-8",
    )
    (repo / "plan" / "plain").mkdir(parents=True)
    (repo / "plan" / "plain" / "epic.md").write_text(
        "# Plan Epic\n\nNothing here names the migrated shape.\n", encoding="utf-8"
    )

    for module in (collect, snapshot):
        assert module.migrated_supervisor_handoff_state(repo=repo, topic="migrated") == "migrated"
        assert module.migrated_supervisor_handoff_state(repo=repo, topic="plain") == "not-migrated"
        assert module.supervisor_handoff_state(repo=repo, topic="migrated") == "present"
        assert module.supervisor_handoff_state(repo=repo, topic="plain") == "missing"


def test_collect_reexports_snapshot_supervisor_handoff_predicates() -> None:
    collect = foreman_gather_collect()
    snapshot = foreman_gather_snapshot()

    assert collect.supervisor_handoff_state is snapshot.supervisor_handoff_state
    assert collect.migrated_supervisor_handoff_state is snapshot.migrated_supervisor_handoff_state


def test_supervisor_handoff_state_surfaces_unreadable_rather_than_claiming_missing(*, tmp_path):
    """The caller must not re-collapse what the widened predicate separated.

    'missing' is the row value that makes `supervisor_pair_start` a warranted
    proposal, so reporting it for an epic.md nobody could read would propose
    starting a supervisor pair on the strength of an unread file. The foreman
    contract routes every value other than 'missing' to report-only, so the new
    value fails safe without a contract change.
    """
    collect = foreman_gather_collect()
    snapshot = foreman_gather_snapshot()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "plan" / "not-utf8").mkdir(parents=True)
    (repo / "plan" / "not-utf8" / "epic.md").write_bytes(b"\xff\xfe ledger entry\n")

    for module in (collect, snapshot):
        assert module.supervisor_handoff_state(repo=repo, topic="not-utf8") == "unreadable"

    row = snapshot.row_with_supervisor_handoff(
        repo=repo, row={"repo": str(repo), "topic": "not-utf8", "status": "session-gone"}
    )
    assert row["supervisor_handoff"] == "unreadable"
