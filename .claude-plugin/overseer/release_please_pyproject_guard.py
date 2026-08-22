"""Release-please pyproject.toml stale-snapshot guard."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

__all__: list[str] = [
    "assert_release_pyproject_diff_is_version_only",
    "is_release_subject",
    "non_version_pyproject_diff_lines",
]

_RELEASE_SUBJECT = re.compile(r"^chore\(master\): release \d+\.\d+\.\d+$")


def is_release_subject(*, subject: str) -> bool:
    return _RELEASE_SUBJECT.match(subject) is not None


def non_version_pyproject_diff_lines(*, diff: str) -> list[str]:
    offenders: list[str] = []
    for line in diff.splitlines():
        if not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
            continue
        if line[1:].strip().startswith("version = "):
            continue
        offenders.append(line)
    return offenders


def assert_release_pyproject_diff_is_version_only(*, repo_root: Path, ref: str) -> None:
    subject = _git("show", "-s", "--format=%s", ref, repo_root=repo_root).stdout.strip()
    if not is_release_subject(subject=subject):
        return

    diff = _git(
        "show",
        "--unified=0",
        "--format=",
        ref,
        "--",
        "pyproject.toml",
        repo_root=repo_root,
    ).stdout
    offenders = non_version_pyproject_diff_lines(diff=diff)
    if offenders:
        msg = (
            f"{ref} is a release-please commit, but its pyproject.toml diff changes "
            "lines outside the owned project.version edit. This is the stale-snapshot "
            "clobber shape from 356b68b; first offending lines: "
            f"{offenders[:8]}"
        )
        raise AssertionError(msg)


def _git(*args: str, repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
