"""Forge-side source reader for remote wait-target verification."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from subprocess import CompletedProcess

import jsonio

__all__: list[str] = [
    "forge_pull_request_present_with",
]

_FORGE_TIMEOUT_SECONDS = 5.0


def branch_name(*, branch: str | None) -> str | None:
    if branch is None:
        return None
    return branch.removeprefix("refs/heads/")


def forge_pull_request_present_with(
    *,
    repo: Path,
    branch: str | None,
    run: Callable[..., CompletedProcess[str]],
) -> bool:
    head = branch_name(branch=branch)
    if head is None:
        return False
    try:
        completed = run(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "all",
                "--head",
                head,
                "--json",
                "headRefName,number,state",
            ],
            capture_output=True,
            check=False,
            cwd=repo,
            text=True,
            timeout=_FORGE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if completed.returncode != 0:
        return False
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return False
    records = jsonio.as_list(value=value)
    if records is None:
        return False
    return any(
        record.get("headRefName") == head
        for raw in records
        if (record := jsonio.as_object(value=raw)) is not None
    )
