"""Legacy-record migration and skip surfacing for wait-premise records.

SPECIFICATION contracts.md "The wait-premise record" requires that an
unreadable, malformed, or unknown-or-newer record be skipped AND SURFACED, and
that the directory hold one file per record. These pin both.
"""

from __future__ import annotations

import importlib
import json

import foreman_gather_evidence
import foreman_gather_render
import wait_premises
from _supervisor_snapshot import SCHEMA_VERSION
from foreman_gather_collect import compose_document
from foreman_gather_render import render_document

__all__: list[str] = []


def _skips_module():
    """Import the reading-side module lazily so collection survives its absence."""
    return importlib.import_module("wait_premise_skips")


def _legacy_record(*, target_id: str) -> str:
    return (
        json.dumps(
            {
                "kind": "pr",
                "target_id": target_id,
                "evidence_source": "gh pr view --json state",
                "recorded_at": "2026-08-19T02:30:00Z",
                "recheck_by": "2026-08-19T03:00:00Z",
            }
        )
        + "\n"
    )


def test_a_migrated_legacy_record_is_returned_by_the_same_read(*, tmp_path):
    repo = tmp_path / "repo"
    directory = wait_premises.wait_premise_dir(repo=repo, topic="alpha")
    directory.mkdir(parents=True)
    (directory / "pr-17.json").write_text(_legacy_record(target_id="17"), encoding="utf-8")

    records = wait_premises.read_wait_premises(repo=repo, topic="alpha")

    assert [str(record["target_id"]) for record in records] == ["17"]


def test_migration_removes_the_legacy_file_rather_than_duplicating_it(*, tmp_path):
    repo = tmp_path / "repo"
    directory = wait_premises.wait_premise_dir(repo=repo, topic="alpha")
    directory.mkdir(parents=True)
    legacy = directory / "pr-17.json"
    legacy.write_text(_legacy_record(target_id="17"), encoding="utf-8")

    _ = wait_premises.read_wait_premises(repo=repo, topic="alpha")

    assert not legacy.exists()
    assert len(list(directory.glob("*.json"))) == 1
    assert [
        str(record["target_id"])
        for record in wait_premises.read_wait_premises(repo=repo, topic="alpha")
    ] == ["17"]


def test_an_unknown_or_newer_record_is_skipped_and_surfaced(*, tmp_path):
    repo = tmp_path / "repo"
    directory = wait_premises.wait_premise_dir(repo=repo, topic="alpha")
    directory.mkdir(parents=True)
    newer = directory / "pr-newer.json"
    newer.write_text(
        json.dumps(
            {
                "schema_version": wait_premises.SCHEMA_VERSION + 1,
                "kind": "pr",
                "target_id": "19",
                "evidence_source": "gh pr view 19 --json state",
                "recorded_at": "2026-08-19T02:30:00Z",
                "recheck_by": "2026-08-19T03:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert wait_premises.read_wait_premises(repo=repo, topic="alpha") == []
    skips = _skips_module().read_wait_premise_skips(repo=repo, topic="alpha")
    assert [skip["path"] for skip in skips] == [str(newer)]
    assert [skip["reason"] for skip in skips] == ["schema-version-unknown"]


def test_skip_reasons_name_each_way_a_record_is_unusable(*, tmp_path):
    directory = tmp_path / "premises"
    directory.mkdir()
    unreadable = directory / "unreadable.json"
    unreadable.mkdir()
    malformed = directory / "malformed.json"
    malformed.write_text("{oops}\n", encoding="utf-8")
    non_object = directory / "non-object.json"
    non_object.write_text("[]\n", encoding="utf-8")

    assert _skips_module().skip_reason(path=unreadable) == "unreadable"
    assert _skips_module().skip_reason(path=malformed) == "malformed"
    assert _skips_module().skip_reason(path=non_object) == "malformed"
    assert _skips_module().schema_version_reason(value={}) == "schema-version-absent"
    assert (
        _skips_module().schema_version_reason(value={"schema_version": True})
        == "schema-version-invalid"
    )
    assert (
        _skips_module().schema_version_reason(value={"schema_version": "1"})
        == "schema-version-invalid"
    )
    assert (
        _skips_module().schema_version_reason(
            value={"schema_version": wait_premises.SCHEMA_VERSION}
        )
        == "invalid-fields"
    )


def test_gather_evidence_ignores_a_row_with_no_usable_identity():
    assert foreman_gather_evidence.row_wait_premise_skips(row={"repo": "", "topic": "a"}) == []
    assert foreman_gather_evidence.row_wait_premise_skips(row={"repo": "/r", "topic": ""}) == []


def test_render_reports_skip_reasons_and_stays_quiet_without_them():
    row = {"wait_premise_skips": [{"path": "/p", "reason": "schema-version-unknown"}]}

    assert (
        foreman_gather_render.premise_skips_text(row=row) == "premise_skips=schema-version-unknown"
    )
    assert foreman_gather_render.premise_skips_text(row={}) == ""


def test_foreman_gather_surfaces_an_unusable_premise_on_the_row(*, tmp_path):
    repo = tmp_path / "repo"
    topic = "alpha"
    _ = (repo / "plan" / topic).mkdir(parents=True)
    directory = wait_premises.wait_premise_dir(repo=repo, topic=topic)
    directory.mkdir(parents=True)
    (directory / "pr-newer.json").write_text(
        json.dumps(
            {
                "schema_version": wait_premises.SCHEMA_VERSION + 1,
                "kind": "pr",
                "target_id": "19",
                "evidence_source": "gh pr view 19 --json state",
                "recorded_at": "2026-08-19T02:30:00Z",
                "recheck_by": "2026-08-19T03:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
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

    assert "wait_premises" not in first
    assert [skip["reason"] for skip in first["wait_premise_skips"]] == ["schema-version-unknown"]
    assert "premise_skips=schema-version-unknown" in render_document(document=document)
