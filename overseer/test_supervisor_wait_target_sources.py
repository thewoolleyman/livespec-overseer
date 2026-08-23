"""Beside-tests for wait-target authoritative source readers."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import _supervisor_wait_target_sources as sources
from _supervisor_records import WaitTargetCacheEntry

__all__: list[str] = []


def _write_local_runs(*, repo: Path, records: list[dict[str, object]]) -> None:
    path = repo / "tmp" / "overseer" / "fabro-ps-a.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records) + "\n", encoding="utf-8")


def _write_journal(*, repo: Path, records: list[dict[str, object]]) -> None:
    path = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


@dataclass(frozen=True, kw_only=True)
class Completed:
    returncode: int
    stdout: str = ""


def test_wait_target_source_readers_fail_soft_on_unusable_inputs(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    assert sources.json_records_from_file(path=repo / "missing.json") is None
    malformed = repo / "malformed.json"
    malformed.parent.mkdir()
    malformed.write_text("{", encoding="utf-8")
    assert sources.json_records_from_file(path=malformed) is None
    scalar = repo / "scalar.json"
    scalar.write_text("{}", encoding="utf-8")
    assert sources.json_records_from_file(path=scalar) is None
    mixed = repo / "mixed.json"
    mixed.write_text(json.dumps([{"id": "run-1"}, []]), encoding="utf-8")
    assert sources.json_records_from_file(path=mixed) == [{"id": "run-1"}]

    def raise_oserror(*args, **kwargs):
        raise OSError("no fabro")

    monkeypatch.setattr(sources.subprocess, "run", raise_oserror)
    assert sources.local_process_records(repo=repo) == []


def test_wait_target_local_process_reader_accepts_command_shapes(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    calls = []

    def run_nonzero(*args, **kwargs):
        calls.append((args, kwargs))
        return Completed(returncode=1)

    monkeypatch.setattr(sources.subprocess, "run", run_nonzero)
    assert sources.local_process_records(repo=repo) == []

    def run_malformed(*args, **kwargs):
        return Completed(returncode=0, stdout="{")

    monkeypatch.setattr(sources.subprocess, "run", run_malformed)
    assert sources.local_process_records(repo=repo) == []

    def run_nonobject(*args, **kwargs):
        return Completed(returncode=0, stdout="[]")

    monkeypatch.setattr(sources.subprocess, "run", run_nonobject)
    assert sources.local_process_records(repo=repo) == []

    def run_items(*args, **kwargs):
        return Completed(returncode=0, stdout=json.dumps({"items": [{"run_id": "run-1"}]}))

    monkeypatch.setattr(sources.subprocess, "run", run_items)
    assert sources.local_process_records(repo=repo) == [{"run_id": "run-1"}]
    assert calls[0][1]["cwd"] == repo


def test_wait_target_source_helpers_cover_identity_and_journal_edges(*, tmp_path):
    repo = tmp_path / "repo"
    assert sources.record_id(record={}) is None
    assert sources.record_id(record={"run_id": "run-2"}) == "run-2"
    assert sources.record_id(record={"dispatch_id": "run-3"}) == "run-3"
    assert sources.record_status(record={}) is None
    assert sources.record_status(record={"state": "FAILED"}) == "failed"
    assert sources.record_status(record={"conclusion": "success"}) == "success"
    assert sources.remote_record(
        record={"evidence_source": "fabro ps --factory=hp", "target_id": "run-1"}
    )
    assert sources.remote_record(
        record={"evidence_source": "fabro ps --factory=vps", "target_id": "run-1"}
    )

    assert sources.read_journal(repo=repo) == []
    _write_journal(repo=repo, records=[{"stage": "dispatch-id", "dispatch_id": "run-1"}])
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    journal.write_text('{}\nnot-json\nnull\n{"stage":"outcome"}\n', encoding="utf-8")
    assert sources.read_journal(repo=repo) == [{}, {"stage": "outcome"}]

    records = [
        {"stage": "ignored", "dispatch_id": "run-1", "at": "2026-08-19T00:00:00Z"},
        {"stage": "dispatch-id", "dispatch_id": "other", "at": "2026-08-19T00:00:00Z"},
        {
            "stage": "dispatch-id",
            "dispatch_id": "run-1",
            "work_item_id": "wrong",
            "at": "2026-08-19T00:00:00Z",
        },
        {
            "stage": "dispatch-id",
            "dispatch_id": "run-1",
            "work_item_id": "wi",
            "at": "2026-08-19T01:00:00Z",
        },
    ]
    assert (
        sources.journal_dispatch_at(records=records, target_id="run-1", work_item_id="wi")
        == "2026-08-19T01:00:00Z"
    )


def test_wait_target_journal_outcomes_are_floored_and_matched():
    records = [
        {
            "stage": "dispatch-id",
            "dispatch_id": "run-1",
            "work_item_id": "wi",
            "at": "2026-08-19T02:00:00Z",
        },
        {"stage": "outcome", "outcome": {"work_item_id": "wi"}, "at": "2026-08-19T01:00:00Z"},
        {"stage": "outcome", "outcome": [], "at": "2026-08-19T03:00:00Z"},
        {
            "stage": "outcome",
            "outcome": {"work_item_id": "other"},
            "at": "2026-08-19T03:00:00Z",
        },
        {
            "stage": "outcome",
            "outcome": {"work_item_id": "wi", "status": "succeeded"},
            "at": "2026-08-19T03:00:00Z",
        },
    ]
    assert sources.journal_outcomes(records=records, target_id="run-1", work_item_id="wi") == [
        {"work_item_id": "wi", "status": "succeeded"}
    ]
    assert sources.journal_outcomes(
        records=[
            {"stage": "outcome", "outcome": {"dispatch_id": "other"}},
            {"stage": "outcome", "outcome": {"dispatch_id": "run-1"}},
        ],
        target_id="run-1",
        work_item_id=None,
    ) == [{"dispatch_id": "run-1"}]


def test_wait_target_publish_branch_probe_fail_soft_and_success(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    assert not sources.publish_branch_present(repo=repo, branch=None)

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=1)

    monkeypatch.setattr(sources.subprocess, "run", raise_timeout)
    assert not sources.publish_branch_present(repo=repo, branch="feat/x")

    def run_empty(*args, **kwargs):
        return Completed(returncode=0, stdout="")

    monkeypatch.setattr(sources.subprocess, "run", run_empty)
    assert not sources.publish_branch_present(repo=repo, branch="feat/x")

    def run_success(*args, **kwargs):
        return Completed(returncode=0, stdout="abc\trefs/heads/feat/x\n")

    monkeypatch.setattr(sources.subprocess, "run", run_success)
    assert sources.publish_branch_present(repo=repo, branch="refs/heads/feat/x")


def test_wait_target_verdict_edges(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _write_local_runs(repo=repo, records=[{"dispatch_id": "run-1", "status": "running"}])
    assert sources.local_verdict(repo=repo, target_id="run-1") == ("present", None)
    assert sources.local_verdict(repo=repo, target_id="other") == (
        "wait-target-missing",
        "fabro-run other absent from every mandatory leg",
    )

    monkeypatch.setattr(sources, "publish_branch_present", lambda *, repo, branch: True)
    assert sources.remote_verdict(
        repo=repo, record={"publish_branch": "feat/x"}, target_id="r"
    ) == (
        "present",
        None,
    )
    monkeypatch.setattr(sources, "publish_branch_present", lambda *, repo, branch: False)
    monkeypatch.setattr(
        sources,
        "read_journal",
        lambda *, repo: [
            {
                "stage": "outcome",
                "outcome": {"dispatch_id": "r", "status": "failed"},
                "at": "2026-08-19T03:00:00Z",
            }
        ],
    )
    assert sources.remote_verdict(repo=repo, record={}, target_id="r") == (
        "wait-target-missing",
        "fabro-run r present with terminal state failed",
    )
    monkeypatch.setattr(
        sources,
        "read_journal",
        lambda *, repo: [
            {
                "stage": "outcome",
                "outcome": {"dispatch_id": "r", "status": "custom-delivered"},
                "at": "2026-08-19T03:00:00Z",
            }
        ],
    )
    assert sources.remote_verdict(repo=repo, record={}, target_id="r") == ("present", None)
    monkeypatch.setattr(
        sources,
        "read_journal",
        lambda *, repo: [
            {
                "stage": "outcome",
                "outcome": {"dispatch_id": "r"},
                "at": "2026-08-19T03:00:00Z",
            }
        ],
    )
    assert sources.remote_verdict(repo=repo, record={}, target_id="r") == (
        "wait-target-missing",
        "fabro-run r absent from every mandatory leg",
    )
    monkeypatch.setattr(sources, "read_journal", lambda *, repo: [])
    assert sources.remote_verdict(repo=repo, record={}, target_id="r") == (
        "wait-target-missing",
        "fabro-run r absent from every mandatory leg",
    )


def test_wait_target_verify_uses_cache_and_skips_malformed_target(*, tmp_path):
    cached = WaitTargetCacheEntry(checked_at=10.0, status="cached", note="cached note")
    assert (
        sources.verify_wait_target_record(repo=tmp_path, record={}, cache=cached, now=10.0)
        is cached
    )
    fresh = sources.verify_wait_target_record(repo=tmp_path, record={}, cache=cached, now=11.0)
    assert fresh == WaitTargetCacheEntry(checked_at=11.0, status="present", note=None)
