"""Beside-tests for remote wait-target authoritative source readers."""
# livespec-lloc-soft-band-owner: overseer-tdfe.13

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


def test_wait_target_forge_probe_runs_all_states_and_fails_closed(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    calls = []
    assert hasattr(sources, "forge_pull_request_present")
    assert not sources.forge_pull_request_present(repo=repo, branch=None)

    def raise_timeout(*args, **kwargs):
        calls.append((args, kwargs))
        raise subprocess.TimeoutExpired(cmd="gh", timeout=1)

    monkeypatch.setattr(sources.subprocess, "run", raise_timeout)
    assert not sources.forge_pull_request_present(repo=repo, branch="feat/x")

    def run_nonzero(*args, **kwargs):
        return Completed(returncode=1)

    monkeypatch.setattr(sources.subprocess, "run", run_nonzero)
    assert not sources.forge_pull_request_present(repo=repo, branch="feat/x")

    def run_malformed(*args, **kwargs):
        return Completed(returncode=0, stdout="{")

    monkeypatch.setattr(sources.subprocess, "run", run_malformed)
    assert not sources.forge_pull_request_present(repo=repo, branch="feat/x")

    def run_nonlist(*args, **kwargs):
        return Completed(returncode=0, stdout="{}")

    monkeypatch.setattr(sources.subprocess, "run", run_nonlist)
    assert not sources.forge_pull_request_present(repo=repo, branch="feat/x")

    def run_empty(*args, **kwargs):
        return Completed(returncode=0, stdout="[]")

    monkeypatch.setattr(sources.subprocess, "run", run_empty)
    assert not sources.forge_pull_request_present(repo=repo, branch="feat/x")

    def run_match(*args, **kwargs):
        calls.append((args, kwargs))
        return Completed(returncode=0, stdout=json.dumps([{"headRefName": "feat/x"}]))

    monkeypatch.setattr(sources.subprocess, "run", run_match)
    assert sources.forge_pull_request_present(repo=repo, branch="refs/heads/feat/x")
    assert calls[-1][0][0] == [
        "gh",
        "pr",
        "list",
        "--state",
        "all",
        "--head",
        "feat/x",
        "--json",
        "headRefName,number,state",
    ]
    assert calls[-1][1]["cwd"] == repo
    assert calls[-1][1]["timeout"] > 0


def test_wait_target_remote_verdict_edges(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    monkeypatch.setattr(sources, "publish_branch_present", lambda *, repo, branch: True)
    forge_calls: list[str | None] = []
    monkeypatch.setattr(
        sources,
        "forge_pull_request_present",
        lambda *, repo, branch: forge_calls.append(branch) or False,
    )
    assert sources.remote_verdict(
        repo=repo, record={"publish_branch": "feat/x"}, target_id="r"
    ) == (
        "present",
        None,
    )
    assert forge_calls == []
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
    monkeypatch.setattr(
        sources, "forge_pull_request_present", lambda *, repo, branch: branch == "feat/x"
    )
    assert sources.remote_verdict(
        repo=repo, record={"publish_branch": "feat/x"}, target_id="r"
    ) == ("present", None)
    assert sources.remote_verdict(repo=repo, record={}, target_id="r") == (
        "wait-target-missing",
        "fabro-run r absent from every mandatory leg",
    )
