"""Edge coverage for remote wait-target liveness helpers."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import _supervisor_wait_target_liveness as liveness

__all__: list[str] = []


@dataclass(frozen=True, kw_only=True)
class Completed:
    returncode: int
    stdout: str = ""


def write_config(*, repo: Path, text: str) -> None:
    _ = (repo / ".livespec.jsonc").write_text(text, encoding="utf-8")


def test_jsonc_config_reader_handles_comments_escapes_and_parse_failures(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write_config(
        repo=repo,
        text='{"literal": "http://example/\\\\\\"still-string"} // trailing\n',
    )

    assert liveness.strip_jsonc_line_comment(line='"http://in-string" // out') == (
        '"http://in-string" '
    )
    assert liveness.parse_repo_config(repo=repo) == {"literal": 'http://example/\\"still-string'}

    missing = tmp_path / "missing"
    assert liveness.parse_repo_config(repo=missing) is None
    write_config(repo=repo, text="{")
    assert liveness.parse_repo_config(repo=repo) is None
    write_config(repo=repo, text="[]")
    assert liveness.parse_repo_config(repo=repo) is None


def test_factory_server_handles_missing_config_shapes(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    assert liveness.factory_server(repo=repo, factory=None) is None
    assert liveness.factory_server(repo=repo, factory="hp") is None
    write_config(repo=repo, text='{"other": {}}')
    assert liveness.factory_server(repo=repo, factory="hp") is None
    write_config(repo=repo, text='{"livespec-orchestrator-beads-fabro": {"other": {}}}')
    assert liveness.factory_server(repo=repo, factory="hp") is None
    write_config(
        repo=repo,
        text='{"livespec-orchestrator-beads-fabro": {"dispatcher": {"factories": []}}}',
    )
    assert liveness.factory_server(repo=repo, factory="hp") is None
    write_config(
        repo=repo,
        text='{"livespec-orchestrator-beads-fabro": {"dispatcher": {"factories": {"vps": {}}}}}',
    )
    assert liveness.factory_server(repo=repo, factory="hp") is None
    write_config(
        repo=repo,
        text='{"livespec-orchestrator-beads-fabro": {"dispatcher": {"factories": {"hp": []}}}}',
    )
    assert liveness.factory_server(repo=repo, factory="hp") is None
    write_config(
        repo=repo,
        text=(
            '{"livespec-orchestrator-beads-fabro": {"dispatcher": {"factories": '
            '{"hp": {"server": 7}}}}}'
        ),
    )
    assert liveness.factory_server(repo=repo, factory="hp") is None


def test_payload_matching_and_active_status_helpers():
    assert liveness.process_records_from_payload(stdout="{") is None
    assert liveness.process_records_from_payload(stdout="[]") is None
    assert liveness.process_records_from_payload(stdout='{"other": []}') is None
    assert liveness.process_records_from_payload(stdout='{"items": [{"id": "run-1"}, 7]}') == [
        {"id": "run-1"}
    ]

    assert liveness.run_matches_target(
        process_record={"id": "run-1"}, target_id="run-1", work_item_id=None
    )
    assert liveness.run_matches_target(
        process_record={"work_item_id": "overseer-x"},
        target_id="dispatch-1",
        work_item_id="overseer-x",
    )
    assert not liveness.run_matches_target(
        process_record={"work_item_id": "overseer-y"},
        target_id="dispatch-1",
        work_item_id="overseer-x",
    )
    assert liveness.active_process(process_record={})
    assert liveness.active_process(process_record={"state": "RUNNING"})
    assert not liveness.active_process(process_record={"conclusion": "FAILED"})


def test_remote_factory_liveness_fail_open_paths(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    write_config(
        repo=repo,
        text=(
            '{"livespec-orchestrator-beads-fabro": {"dispatcher": {"factories": '
            '{"hp": {"server": "https://factory.example"}}}}}'
        ),
    )
    record = {"dispatch_factory": "hp", "work_item_id": "overseer-x"}

    assert (
        liveness.remote_factory_run_present_with(
            repo=repo,
            record={"dispatch_factory": "missing"},
            target_id="dispatch-1",
            run=lambda *args, **kwargs: Completed(returncode=0),
        )
        is False
    )
    assert (
        liveness.remote_factory_run_present_with(
            repo=repo,
            record=record,
            target_id="dispatch-1",
            run=lambda *args, **kwargs: Completed(returncode=1),
        )
        is None
    )
    assert (
        liveness.remote_factory_run_present_with(
            repo=repo,
            record=record,
            target_id="dispatch-1",
            run=lambda *args, **kwargs: Completed(returncode=0, stdout="{"),
        )
        is None
    )

    def raise_oserror(*args, **kwargs):
        raise OSError("unreachable")

    assert (
        liveness.remote_factory_run_present_with(
            repo=repo,
            record=record,
            target_id="dispatch-1",
            run=raise_oserror,
        )
        is None
    )

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="fabro", timeout=1)

    assert (
        liveness.remote_factory_run_present_with(
            repo=repo,
            record=record,
            target_id="dispatch-1",
            run=raise_timeout,
        )
        is None
    )
