"""Edge coverage for typed wait-premise records."""

from __future__ import annotations

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


def test_single_record_reader_returns_none_when_file_disappears(*, tmp_path):
    assert wait_premises.read_wait_premise(path=tmp_path / "missing.json") is None


def test_path_uses_target_fallback_when_identifier_has_no_filename_characters(*, tmp_path):
    path = wait_premises.wait_premise_path(
        repo=tmp_path / "repo",
        topic="alpha",
        kind="pr",
        target_id="///",
    )

    assert path.name == "pr-target.json"


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
