"""Read-only scheduled charter scan for the homelab repository."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streams
from livespec_dev_tooling.charters import defects_in

__all__: list[str] = [
    "CharterScanReport",
    "format_report",
    "main",
    "scan_homelab_charters",
]

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]

HOMELAB_REPO: Final[str] = "thewoolleyman/homelab"
_SHARED_CHARTER = ".ai/supervisor-protocol.md"
_PLAN_CHARTER_SUFFIX = "/supervisor-handoff.md"


@dataclass(frozen=True, kw_only=True)
class CharterScanReport:
    repo: str
    default_branch: str
    charter_count: int
    defect_count: int
    defects_by_path: dict[str, list[str]]


def _run_command(*, argv: list[str]) -> subprocess.CompletedProcess[str]:  # pragma: no cover
    return subprocess.run(argv, capture_output=True, text=True, check=False, timeout=60)  # noqa: S603


def _gh_json(*, runner: CommandRunner, argv: list[str]) -> dict[str, object]:
    completed = runner(argv=argv)
    if completed.returncode != 0:
        msg = completed.stderr.strip() or f"gh exited {completed.returncode}"
        raise RuntimeError(msg)
    return cast(dict[str, object], json.loads(completed.stdout))


def _gh_text(*, runner: CommandRunner, argv: list[str]) -> str:
    completed = runner(argv=argv)
    if completed.returncode != 0:
        msg = completed.stderr.strip() or f"gh exited {completed.returncode}"
        raise RuntimeError(msg)
    return completed.stdout


def _default_branch(*, runner: CommandRunner, repo: str) -> str:
    payload = _gh_json(
        runner=runner, argv=["gh", "repo", "view", repo, "--json", "defaultBranchRef"]
    )
    default_branch = cast(dict[str, str], payload["defaultBranchRef"])
    return default_branch["name"]


def _is_charter_path(*, path: str) -> bool:
    return path == _SHARED_CHARTER or (
        path.startswith("plan/") and path.endswith(_PLAN_CHARTER_SUFFIX)
    )


def _tree_paths(*, runner: CommandRunner, repo: str, branch: str) -> list[str]:
    payload = _gh_json(
        runner=runner,
        argv=["gh", "api", f"repos/{repo}/git/trees/{branch}?recursive=1"],
    )
    rows = cast(list[dict[str, str]], payload["tree"])
    return sorted(row["path"] for row in rows if row.get("type") == "blob")


def _charter_paths(*, runner: CommandRunner, repo: str, branch: str) -> list[str]:
    return [
        path
        for path in _tree_paths(runner=runner, repo=repo, branch=branch)
        if _is_charter_path(path=path)
    ]


def _read_repo_file(*, runner: CommandRunner, repo: str, branch: str, path: str) -> str:
    return _gh_text(
        runner=runner,
        argv=[
            "gh",
            "api",
            f"repos/{repo}/contents/{path}?ref={branch}",
            "--header",
            "Accept: application/vnd.github.raw",
        ],
    )


def scan_homelab_charters(
    *,
    runner: CommandRunner = _run_command,
    repo: str = HOMELAB_REPO,
) -> CharterScanReport:
    branch = _default_branch(runner=runner, repo=repo)
    paths = _charter_paths(runner=runner, repo=repo, branch=branch)
    defects = {
        path: found
        for path in paths
        if (
            found := defects_in(
                text=_read_repo_file(runner=runner, repo=repo, branch=branch, path=path)
            )
        )
    }
    return CharterScanReport(
        repo=repo,
        default_branch=branch,
        charter_count=len(paths),
        defect_count=sum(len(found) for found in defects.values()),
        defects_by_path=defects,
    )


def format_report(*, report: CharterScanReport) -> str:
    lines = [
        f"repo: {report.repo}",
        f"default_branch: {report.default_branch}",
        f"charters: {report.charter_count}",
        f"defects: {report.defect_count}",
    ]
    for path, findings in report.defects_by_path.items():
        lines.append(f"{path}:")
        lines.extend(f"  - {finding}" for finding in findings)
    return "\n".join(lines) + "\n"


def main(*, argv: Sequence[str] | None = None) -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(prog="overseer-scan-homelab-charters")
    _ = parser.add_argument("--repo", default=HOMELAB_REPO)
    args = parser.parse_args(argv)
    report = scan_homelab_charters(repo=args.repo)
    streams.write_stdout(text=format_report(report=report))
    return 1 if report.defect_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
