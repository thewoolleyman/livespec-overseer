"""CLI and failure-boundary coverage for the homelab charter scan."""

from __future__ import annotations

import subprocess

import pytest

from overseer import homelab_charter_scan as module

__all__: list[str] = []


def _failed(*, argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=argv, returncode=1, stdout="", stderr="gh failed")


def test_scan_surfaces_default_branch_resolution_failure() -> None:
    with pytest.raises(RuntimeError, match="gh failed"):
        _ = module.scan_homelab_charters(runner=_failed)


def test_scan_surfaces_file_fetch_failure() -> None:
    def runner(*, argv: list[str]) -> subprocess.CompletedProcess[str]:
        if argv == ["gh", "repo", "view", module.HOMELAB_REPO, "--json", "defaultBranchRef"]:
            return subprocess.CompletedProcess(
                args=argv,
                returncode=0,
                stdout='{"defaultBranchRef":{"name":"main"}}',
                stderr="",
            )
        if argv == ["gh", "api", "repos/thewoolleyman/homelab/git/trees/main?recursive=1"]:
            return subprocess.CompletedProcess(
                args=argv,
                returncode=0,
                stdout='{"tree":[{"path":".ai/supervisor-protocol.md","type":"blob"}]}',
                stderr="",
            )
        return _failed(argv=argv)

    with pytest.raises(RuntimeError, match="gh failed"):
        _ = module.scan_homelab_charters(runner=runner)


def test_main_returns_zero_for_clean_report(*, monkeypatch, capsys) -> None:
    def scan(*, repo: str) -> module.CharterScanReport:
        return module.CharterScanReport(
            repo=repo,
            default_branch="main",
            charter_count=8,
            defect_count=0,
            defects_by_path={},
        )

    monkeypatch.setattr(module, "scan_homelab_charters", scan)

    assert module.main(argv=["--repo", "demo/homelab"]) == 0
    assert capsys.readouterr().out == (
        "repo: demo/homelab\n" "default_branch: main\n" "charters: 8\n" "defects: 0\n"
    )


def test_main_returns_one_for_defects(*, monkeypatch) -> None:
    def scan(*, repo: str) -> module.CharterScanReport:
        return module.CharterScanReport(
            repo=repo,
            default_branch="main",
            charter_count=8,
            defect_count=1,
            defects_by_path={"charter.md": ["a-bare-tmux-target: bad"]},
        )

    monkeypatch.setattr(module, "scan_homelab_charters", scan)

    assert module.main(argv=[]) == 1
