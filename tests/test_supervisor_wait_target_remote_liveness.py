"""Regression coverage for remote wait-target in-flight process liveness."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

import _supervisor_wait_target_sources as sources

__all__: list[str] = []


@dataclass(frozen=True, kw_only=True)
class Completed:
    returncode: int
    stdout: str = ""


def test_remote_verdict_treats_running_factory_row_as_present(*, tmp_path, monkeypatch):
    assert hasattr(sources, "remote_factory_run_present")
    monkeypatch.setattr(sources, "publish_branch_present", lambda *, repo, branch: False)
    monkeypatch.setattr(sources, "read_journal", lambda *, repo: [])
    monkeypatch.setattr(sources, "forge_pull_request_present", lambda *, repo, branch: False)
    monkeypatch.setattr(
        sources,
        "remote_factory_run_present",
        lambda *, repo, record, target_id: True,
    )

    assert sources.remote_verdict(
        repo=tmp_path,
        record={"dispatch_factory": "hp", "work_item_id": "overseer-1a31.3"},
        target_id="dispatch-1",
    ) == ("present", None)


def test_remote_verdict_still_reports_evaporated_target(*, tmp_path, monkeypatch):
    assert hasattr(sources, "remote_factory_run_present")
    monkeypatch.setattr(sources, "publish_branch_present", lambda *, repo, branch: False)
    monkeypatch.setattr(sources, "read_journal", lambda *, repo: [])
    monkeypatch.setattr(sources, "forge_pull_request_present", lambda *, repo, branch: False)
    monkeypatch.setattr(
        sources,
        "remote_factory_run_present",
        lambda *, repo, record, target_id: False,
    )

    assert sources.remote_verdict(repo=tmp_path, record={}, target_id="dispatch-1") == (
        "wait-target-missing",
        "fabro-run dispatch-1 absent from every mandatory leg",
    )


def test_remote_verdict_fails_open_when_factory_liveness_is_unknown(*, tmp_path, monkeypatch):
    assert hasattr(sources, "remote_factory_run_present")
    monkeypatch.setattr(sources, "publish_branch_present", lambda *, repo, branch: False)
    monkeypatch.setattr(sources, "read_journal", lambda *, repo: [])
    monkeypatch.setattr(sources, "forge_pull_request_present", lambda *, repo, branch: False)
    monkeypatch.setattr(
        sources,
        "remote_factory_run_present",
        lambda *, repo, record, target_id: None,
    )

    assert sources.remote_verdict(
        repo=tmp_path, record={"dispatch_factory": "hp"}, target_id="dispatch-1"
    ) == ("present", None)


def test_remote_factory_liveness_resolves_server_and_matches_active_run(*, tmp_path, monkeypatch):
    assert hasattr(sources, "remote_factory_run_present")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".livespec.jsonc").write_text(
        """
        {
          "livespec-overseer": {
            "dispatcher": {
              "factories": {
                "hp": { "server": "https://factory.example" }
              }
            }
          }
        }
        """,
        encoding="utf-8",
    )
    calls = []

    def run(*args, **kwargs):
        calls.append((args, kwargs))
        return Completed(
            returncode=0,
            stdout=json.dumps(
                {
                    "runs": [
                        {
                            "run_id": "run-1",
                            "work_item_id": "overseer-1a31.3",
                            "status": "RUNNING",
                        }
                    ]
                }
            ),
        )

    monkeypatch.setattr(sources.subprocess, "run", run)

    assert sources.remote_factory_run_present(
        repo=repo,
        record={"dispatch_factory": "hp", "work_item_id": "overseer-1a31.3"},
        target_id="dispatch-1",
    )
    assert calls[-1][0][0] == [
        "fabro",
        "ps",
        "-a",
        "--json",
        "--server",
        "https://factory.example",
    ]
    assert calls[-1][1]["timeout"] > 5


def test_remote_factory_liveness_distinguishes_absent_from_unreachable(*, tmp_path, monkeypatch):
    assert hasattr(sources, "remote_factory_run_present")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".livespec.jsonc").write_text(
        """
        {
          "livespec-overseer": {
            "dispatcher": {
              "factories": {
                "hp": { "server": "https://factory.example" }
              }
            }
          }
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sources.subprocess,
        "run",
        lambda *args, **kwargs: Completed(returncode=0, stdout='{"runs": []}'),
    )
    assert (
        sources.remote_factory_run_present(
            repo=repo,
            record={"dispatch_factory": "hp", "work_item_id": "overseer-1a31.3"},
            target_id="dispatch-1",
        )
        is False
    )

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="fabro", timeout=1)

    monkeypatch.setattr(sources.subprocess, "run", raise_timeout)
    assert (
        sources.remote_factory_run_present(
            repo=repo,
            record={"dispatch_factory": "hp", "work_item_id": "overseer-1a31.3"},
            target_id="dispatch-1",
        )
        is None
    )
