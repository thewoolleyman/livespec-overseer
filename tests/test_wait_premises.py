"""Regression tests for typed wait-premise records."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from _supervisor_snapshot import SCHEMA_VERSION
from foreman_gather_collect import compose_document
from foreman_gather_render import render_document

__all__: list[str] = []


def test_wait_premise_helper_writes_typed_record_atomically(*, tmp_path):
    module_path = Path(__file__).resolve().parent.parent / "overseer" / "wait_premises.py"
    assert module_path.is_file()
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

    assert path.parent == repo / "tmp" / "overseer" / "alpha" / "wait-premises"
    assert path.name.startswith("fabro-run-01M0RUN-")
    assert path.name.endswith(".json")
    assert list(path.parent.glob("*.tmp")) == []
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "kind": "fabro-run",
        "target_id": "01M0RUN",
        "evidence_source": "fabro ps -a --json",
        "recorded_at": "2026-08-19T02:30:00Z",
        "recheck_by": "2026-08-19T03:00:00Z",
    }


@pytest.mark.parametrize("kind", ["fabro-run", "pr", "ci-run", "work-item-close"])
def test_wait_premise_schema_accepts_declared_kinds(*, kind):
    module_path = Path(__file__).resolve().parent.parent / "overseer" / "wait_premises.py"
    assert module_path.is_file()
    wait_premises = importlib.import_module("wait_premises")

    record = wait_premises.wait_premise_record(
        kind=kind,
        target_id="target-1",
        evidence_source="source to re-query",
        recorded_at="2026-08-19T02:30:00Z",
        recheck_by="2026-08-19T03:00:00Z",
    )

    assert record["kind"] == kind
    assert record["schema_version"] == 1


def test_wait_premise_paths_disambiguate_colliding_target_stems(*, tmp_path):
    wait_premises = importlib.import_module("wait_premises")

    repo = tmp_path / "repo"
    first_path = wait_premises.write_wait_premise(
        repo=repo,
        topic="alpha",
        kind="pr",
        target_id="///",
        evidence_source="gh pr view /// --json state",
        recorded_at="2026-08-19T02:30:00Z",
        recheck_by="2026-08-19T03:00:00Z",
    )
    second_path = wait_premises.write_wait_premise(
        repo=repo,
        topic="alpha",
        kind="pr",
        target_id="!!!",
        evidence_source="gh pr view !!! --json state",
        recorded_at="2026-08-19T02:31:00Z",
        recheck_by="2026-08-19T03:01:00Z",
    )

    assert first_path != second_path
    assert first_path.name.startswith("pr-target-")
    assert second_path.name.startswith("pr-target-")
    records = wait_premises.read_wait_premises(repo=repo, topic="alpha")
    assert {record["target_id"] for record in records} == {"///", "!!!"}
    assert len(records) == 2


def test_wait_premise_reader_skips_absent_or_unknown_schema_versions(*, tmp_path):
    wait_premises = importlib.import_module("wait_premises")

    directory = wait_premises.wait_premise_dir(repo=tmp_path / "repo", topic="alpha")
    directory.mkdir(parents=True)
    (directory / "missing-schema.json").write_text(
        json.dumps(
            {
                "kind": "pr",
                "target_id": "17",
                "evidence_source": "gh pr view 17 --json state",
                "recorded_at": "2026-08-19T02:30:00Z",
                "recheck_by": "2026-08-19T03:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (directory / "newer-schema.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "kind": "pr",
                "target_id": "18",
                "evidence_source": "gh pr view 18 --json state",
                "recorded_at": "2026-08-19T02:31:00Z",
                "recheck_by": "2026-08-19T03:01:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    valid_path = wait_premises.write_wait_premise(
        repo=tmp_path / "repo",
        topic="alpha",
        kind="pr",
        target_id="19",
        evidence_source="gh pr view 19 --json state",
        recorded_at="2026-08-19T02:32:00Z",
        recheck_by="2026-08-19T03:02:00Z",
    )

    assert wait_premises.read_wait_premise(path=directory / "missing-schema.json") is None
    assert wait_premises.read_wait_premise(path=directory / "newer-schema.json") is None
    assert wait_premises.read_wait_premises(repo=tmp_path / "repo", topic="alpha") == [
        json.loads(valid_path.read_text(encoding="utf-8"))
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "branch"),
        ("target_id", ""),
        ("evidence_source", ""),
        ("recorded_at", "not-a-time"),
        ("recheck_by", "not-a-time"),
    ],
)
def test_wait_premise_schema_rejects_malformed_fields(*, field, value):
    module_path = Path(__file__).resolve().parent.parent / "overseer" / "wait_premises.py"
    assert module_path.is_file()
    wait_premises = importlib.import_module("wait_premises")

    kwargs = {
        "kind": "pr",
        "target_id": "17",
        "evidence_source": "gh pr view 17 --json state",
        "recorded_at": "2026-08-19T02:30:00Z",
        "recheck_by": "2026-08-19T03:00:00Z",
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=field):
        wait_premises.wait_premise_record(**kwargs)


@pytest.mark.parametrize(
    ("repo", "topic", "match"), [("", "alpha", "repo"), ("/repo", "", "topic")]
)
def test_wait_premise_writer_fails_closed_on_empty_repo_or_topic(*, repo, topic, match):
    module_path = Path(__file__).resolve().parent.parent / "overseer" / "wait_premises.py"
    assert module_path.is_file()
    wait_premises = importlib.import_module("wait_premises")

    with pytest.raises(ValueError, match=match):
        wait_premises.write_wait_premise(
            repo=repo,
            topic=topic,
            kind="pr",
            target_id="17",
            evidence_source="gh pr view 17 --json state",
            recorded_at="2026-08-19T02:30:00Z",
            recheck_by="2026-08-19T03:00:00Z",
        )


def test_foreman_gather_surfaces_recorded_wait_premises_per_row(*, tmp_path):
    module_path = Path(__file__).resolve().parent.parent / "overseer" / "wait_premises.py"
    assert module_path.is_file()
    wait_premises = importlib.import_module("wait_premises")

    repo = tmp_path / "repo"
    topic = "alpha"
    _ = (repo / "plan" / topic).mkdir(parents=True)
    _ = wait_premises.write_wait_premise(
        repo=repo,
        topic=topic,
        kind="pr",
        target_id="17",
        evidence_source="gh pr view 17 --json state,statusCheckRollup",
        recorded_at="2026-08-19T02:30:00Z",
        recheck_by="2026-08-19T03:00:00Z",
    )
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "daemon_instance_id": "daemon-1",
                "tick_generation": 3,
                "written_at": "2026-08-19T02:31:00Z",
                "rows": [
                    {
                        "topic": topic,
                        "repo": str(repo.resolve()),
                        "tmux": "alpha",
                        "runtime": "codex",
                        "status": "blocked:human",
                        "note": "waiting on PR",
                        "ctx": 72,
                        "human_wait": True,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    document = compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        list_json_command=None,
        needs_attention_command=None,
        now=lambda: "2026-08-19T02:31:30Z",
    )
    snapshot = document["snapshot"]
    assert isinstance(snapshot, dict)
    rows = snapshot["rows"]
    assert isinstance(rows, list)
    first = rows[0]
    assert isinstance(first, dict)

    assert first["wait_premises"] == [
        {
            "schema_version": 1,
            "kind": "pr",
            "target_id": "17",
            "evidence_source": "gh pr view 17 --json state,statusCheckRollup",
            "recorded_at": "2026-08-19T02:30:00Z",
            "recheck_by": "2026-08-19T03:00:00Z",
        }
    ]
    assert "premises=pr:17 recheck_by=2026-08-19T03:00:00Z" in render_document(document=document)
