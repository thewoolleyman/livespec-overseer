"""Tests for the scheduled homelab charter scan entry point."""

from __future__ import annotations

import importlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

__all__: list[str] = []

_MODULE_PATH = Path(__file__).resolve().parent.parent / "overseer" / "homelab_charter_scan.py"
_REPO = "thewoolleyman/homelab"
_CHARTERS = (
    ".ai/supervisor-protocol.md",
    "plan/00-3-worker-host-nix-toolchain/supervisor-handoff.md",
    "plan/05-hetzner-fleet-member/supervisor-handoff.md",
    "plan/06-resilience-acceptance/supervisor-handoff.md",
    "plan/07-build-substrate/supervisor-handoff.md",
    "plan/08-pi-onboarding/supervisor-handoff.md",
    "plan/09-tailscale-admin-uplift/supervisor-handoff.md",
    "plan/archive/04-convergence-loop/supervisor-handoff.md",
)


class ScanReport(Protocol):
    repo: str
    default_branch: str
    charter_count: int
    defect_count: int
    defects_by_path: dict[str, list[str]]


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class ScanModule(Protocol):
    def scan_homelab_charters(self, *, runner: CommandRunner) -> ScanReport: ...

    def format_report(self, *, report: ScanReport) -> str: ...


class FakeGh:
    def __init__(self, *, contents: dict[str, str]) -> None:
        self.contents = contents
        self.calls: list[list[str]] = []

    def __call__(self, *, argv: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        if argv == ["gh", "repo", "view", _REPO, "--json", "defaultBranchRef"]:
            return _completed(argv=argv, stdout='{"defaultBranchRef":{"name":"main"}}')
        if argv == ["gh", "api", "repos/thewoolleyman/homelab/git/trees/main?recursive=1"]:
            return _completed(argv=argv, stdout=json.dumps({"tree": _tree()}))
        prefix = "repos/thewoolleyman/homelab/contents/"
        suffix = "?ref=main"
        if len(argv) == 5 and argv[:2] == ["gh", "api"] and argv[2].startswith(prefix):
            path = argv[2][len(prefix) : -len(suffix)]
            return _completed(argv=argv, stdout=self.contents[path])
        return subprocess.CompletedProcess(args=argv, returncode=1, stdout="", stderr="unexpected")


def _completed(*, argv: list[str], stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=argv, returncode=0, stdout=stdout, stderr="")


def _tree() -> list[dict[str, str]]:
    rows = [{"path": path, "type": "blob"} for path in _CHARTERS]
    rows.append({"path": "README.md", "type": "blob"})
    return rows


def _scan_module() -> ScanModule:
    assert _MODULE_PATH.is_file()
    module = importlib.import_module("overseer.homelab_charter_scan")
    return cast(ScanModule, module)


def test_scan_resolves_homelab_default_branch_from_the_forge() -> None:
    module = _scan_module()
    fake = FakeGh(contents={path: "clean charter\n" for path in _CHARTERS})

    report = module.scan_homelab_charters(runner=fake)

    assert report.default_branch == "main"
    assert fake.calls[0] == ["gh", "repo", "view", _REPO, "--json", "defaultBranchRef"]
    assert "git/trees/main?recursive=1" in fake.calls[1][2]


def test_scan_reports_all_eight_homelab_charters_clean() -> None:
    module = _scan_module()
    fake = FakeGh(contents={path: "clean charter\n" for path in _CHARTERS})

    report = module.scan_homelab_charters(runner=fake)

    assert report.repo == _REPO
    assert report.charter_count == 8
    assert report.defect_count == 0
    assert report.defects_by_path == {}
    assert module.format_report(report=report) == (
        "repo: thewoolleyman/homelab\n" "default_branch: main\n" "charters: 8\n" "defects: 0\n"
    )


def test_scan_does_not_drop_archived_plan_charters() -> None:
    module = _scan_module()
    fake = FakeGh(contents={path: "clean charter\n" for path in _CHARTERS})

    _ = module.scan_homelab_charters(runner=fake)

    fetched = {call[2] for call in fake.calls if len(call) == 5 and call[:2] == ["gh", "api"]}
    assert (
        "repos/thewoolleyman/homelab/contents/"
        "plan/archive/04-convergence-loop/supervisor-handoff.md?ref=main"
    ) in fetched


def test_scan_reports_detector_findings_by_path() -> None:
    module = _scan_module()
    contents = {path: "clean charter\n" for path in _CHARTERS}
    contents["plan/05-hetzner-fleet-member/supervisor-handoff.md"] = """
```sh
tmux send-keys -t worker -- 'echo unsafe'
```
"""
    fake = FakeGh(contents=contents)

    report = module.scan_homelab_charters(runner=fake)

    assert report.charter_count == 8
    assert report.defect_count == 1
    assert report.defects_by_path == {
        "plan/05-hetzner-fleet-member/supervisor-handoff.md": [
            "a-bare-tmux-target: tmux send-keys -t worker -- 'echo unsafe'"
        ]
    }


def test_module_import_shape_is_type_checkable() -> None:
    module = _scan_module()

    assert module.format_report
