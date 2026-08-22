"""Edge coverage for typed wait-premise records."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import NoReturn

import foreman_gather_evidence
import pytest
import wait_premises

__all__: list[str] = []


def test_reader_returns_empty_when_directory_glob_fails(*, monkeypatch, tmp_path):
    def raise_glob(self: Path, pattern: str) -> NoReturn:
        raise OSError("glob failed")

    monkeypatch.setattr(wait_premises.Path, "glob", raise_glob)

    assert wait_premises.read_wait_premises(repo=tmp_path / "repo", topic="alpha") == []


def test_reader_skips_malformed_and_invalid_records(*, tmp_path):
    directory = wait_premises.wait_premise_dir(repo=tmp_path / "repo", topic="alpha")
    directory.mkdir(parents=True)
    (directory / "malformed.json").write_text("{oops}\n", encoding="utf-8")
    (directory / "non-object.json").write_text("[]\n", encoding="utf-8")
    (directory / "invalid.json").write_text('{"kind": "pr"}\n', encoding="utf-8")

    assert wait_premises.read_wait_premises(repo=tmp_path / "repo", topic="alpha") == []


def test_reader_migrates_legacy_record_and_returns_it_on_the_same_pass(*, tmp_path):
    repo = tmp_path / "repo"
    directory = wait_premises.wait_premise_dir(repo=repo, topic="alpha")
    directory.mkdir(parents=True)
    legacy = {
        "kind": "pr",
        "target_id": "17",
        "evidence_source": "gh pr view 17 --json state",
        "recorded_at": "2026-08-19T02:30:00Z",
        "recheck_by": "2026-08-19T03:00:00Z",
    }
    (directory / "pr-17.json").write_text(json.dumps(legacy) + "\n", encoding="utf-8")

    # The migrated record belongs to the pass that migrated it: withholding it
    # until the next read made a single read report NO premises for a record
    # that plainly exists, and the foreman gather reads exactly once per tick.
    assert wait_premises.read_wait_premises(repo=repo, topic="alpha") == [
        {**legacy, "schema_version": 1}
    ]
    assert not (directory / "pr-17.json").exists()
    migrated_path = wait_premises.wait_premise_path(
        repo=repo,
        topic="alpha",
        kind="pr",
        target_id="17",
    )
    assert migrated_path.name != "pr-17.json"
    assert json.loads(migrated_path.read_text(encoding="utf-8")) == {
        **legacy,
        "schema_version": 1,
    }
    assert wait_premises.read_wait_premises(repo=repo, topic="alpha") == [
        {
            **legacy,
            "schema_version": 1,
        }
    ]


def test_legacy_migration_skips_unreadable_file(*, monkeypatch, tmp_path):
    def raise_read_text(self: Path, *, encoding: str | None = None) -> NoReturn:
        raise OSError("read failed")

    monkeypatch.setattr(wait_premises.Path, "read_text", raise_read_text)

    wait_premises.migrate_legacy_wait_premise(path=tmp_path / "missing.json")


def test_legacy_migration_skips_failed_write(*, monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    directory = wait_premises.wait_premise_dir(repo=repo, topic="alpha")
    directory.mkdir(parents=True)
    (directory / "pr-17.json").write_text(
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

    def raise_write_json_atomic(*, path: Path, payload: dict[str, object]) -> NoReturn:
        raise OSError("write failed")

    monkeypatch.setattr(wait_premises, "write_json_atomic", raise_write_json_atomic)

    wait_premises.migrate_legacy_wait_premise(path=directory / "pr-17.json")
    assert list(directory.glob("*.json")) == [directory / "pr-17.json"]


def test_single_record_reader_returns_none_when_file_disappears(*, tmp_path):
    assert wait_premises.read_wait_premise(path=tmp_path / "missing.json") is None


def test_path_disambiguates_target_fallback_when_identifier_has_no_filename_characters(*, tmp_path):
    path = wait_premises.wait_premise_path(
        repo=tmp_path / "repo",
        topic="alpha",
        kind="pr",
        target_id="///",
    )

    assert path.name.startswith("pr-target-")
    assert path.name.endswith(".json")


def test_writer_rejects_missing_schema_field(*, tmp_path):
    with pytest.raises(ValueError, match="recheck_by"):
        wait_premises.write_wait_premise(
            repo=tmp_path / "repo",
            topic="alpha",
            kind="pr",
            target_id="17",
            evidence_source="gh pr view 17 --json state",
            recorded_at="2026-08-19T02:30:00Z",
        )


def test_atomic_writer_cleans_temp_file_when_replace_fails(*, monkeypatch, tmp_path):
    target = tmp_path / "repo" / "tmp" / "overseer" / "alpha" / "wait-premises" / "pr-17.json"

    def raise_replace(self: Path, *, target: Path) -> NoReturn:
        raise OSError("replace failed")

    monkeypatch.setattr(wait_premises.Path, "replace", raise_replace)

    with pytest.raises(OSError, match="replace failed"):
        wait_premises.write_wait_premise(
            repo=tmp_path / "repo",
            topic="alpha",
            kind="pr",
            target_id="17",
            evidence_source="gh pr view 17 --json state",
            recorded_at="2026-08-19T02:30:00Z",
            recheck_by="2026-08-19T03:00:00Z",
        )

    assert target.parent.is_dir()
    assert list(target.parent.iterdir()) == []


def test_gather_evidence_returns_no_premises_for_malformed_row_identity():
    assert foreman_gather_evidence.row_wait_premises(row={"repo": "", "topic": "alpha"}) == []
    assert foreman_gather_evidence.row_wait_premises(row={"repo": "/repo", "topic": ""}) == []


def test_skip_reader_returns_empty_when_directory_glob_fails(*, monkeypatch, tmp_path):
    wait_premise_skips = importlib.import_module("wait_premise_skips")

    def raise_glob(self: Path, pattern: str) -> NoReturn:
        raise OSError("glob failed")

    monkeypatch.setattr(wait_premises.Path, "glob", raise_glob)

    assert wait_premise_skips.read_wait_premise_skips(repo=tmp_path / "r", topic="alpha") == []


def test_migration_is_a_no_op_when_the_record_already_sits_at_its_own_path(*, tmp_path):
    repo = tmp_path / "repo"
    path = wait_premises.write_wait_premise(
        repo=repo,
        topic="alpha",
        kind="pr",
        target_id="17",
        evidence_source="gh pr view 17 --json state",
        recorded_at="2026-08-19T02:30:00Z",
        recheck_by="2026-08-19T03:00:00Z",
    )
    stripped = {
        key: value
        for key, value in json.loads(path.read_text(encoding="utf-8")).items()
        if key != "schema_version"
    }
    path.write_text(json.dumps(stripped) + "\n", encoding="utf-8")

    assert wait_premises.migrate_legacy_wait_premise(path=path) is None
    assert path.is_file()


def test_migration_drops_a_stale_original_once_the_record_came_forward(*, tmp_path):
    repo = tmp_path / "repo"
    directory = wait_premises.wait_premise_dir(repo=repo, topic="alpha")
    directory.mkdir(parents=True)
    legacy_body = {
        "kind": "pr",
        "target_id": "17",
        "evidence_source": "gh pr view 17 --json state",
        "recorded_at": "2026-08-19T02:30:00Z",
        "recheck_by": "2026-08-19T03:00:00Z",
    }
    stale = directory / "pr-17.json"
    stale.write_text(json.dumps(legacy_body) + "\n", encoding="utf-8")
    current = wait_premises.wait_premise_path(repo=repo, topic="alpha", kind="pr", target_id="17")
    current.write_text(json.dumps({**legacy_body, "schema_version": 1}) + "\n", encoding="utf-8")

    assert wait_premises.migrate_legacy_wait_premise(path=stale) is None
    assert not stale.exists()
    assert current.is_file()


def test_migration_keeps_the_original_when_the_write_fails(*, monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    directory = wait_premises.wait_premise_dir(repo=repo, topic="alpha")
    directory.mkdir(parents=True)
    legacy = directory / "pr-17.json"
    legacy.write_text(
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

    def raise_replace(self: Path, *, target: Path) -> NoReturn:
        raise OSError("replace failed")

    monkeypatch.setattr(wait_premises.Path, "replace", raise_replace)

    assert wait_premises.migrate_legacy_wait_premise(path=legacy) is None
    assert legacy.is_file()
