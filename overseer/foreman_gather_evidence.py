"""Per-row evidence enrichers for the deterministic foreman gatherer."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Protocol, cast

import jsonio
import tmuxio
import wait_premises

__all__: list[str] = [
    "enrich_rows_with_evidence",
    "pane_content_hash",
    "proposed_changes_count",
]

_EXCLUDED_PATH_PREFIXES = (".beads/", ".git/", "plan/", "tmp/")
_GIT_TIMEOUT_SECONDS = 30.0
_GIT_STATUS_PREFIX_LEN = 3


class PaneCaptureSource(Protocol):
    def __call__(self, *, session: str) -> str: ...


def pane_content_hash(*, text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def proposed_changes_count(*, repo: Path) -> int:
    git_count = git_proposed_changes_count(repo=repo)
    if git_count is not None:
        return git_count
    return fallback_proposed_changes_count(repo=repo)


def git_proposed_changes_count(*, repo: Path) -> int | None:
    git = shutil.which("git")
    if git is None:
        return None
    try:
        completed = subprocess.run(  # noqa: S603
            [
                git,
                "-C",
                str(repo),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return sum(
        1
        for line in completed.stdout.splitlines()
        if not proposed_path_excluded(path=git_status_path(line=line))
    )


def fallback_proposed_changes_count(*, repo: Path) -> int:
    count = 0
    try:
        entries = list(repo.rglob("*"))
    except OSError:
        return 0
    for entry in entries:
        if entry.is_file() and not proposed_path_excluded(path=entry.relative_to(repo).as_posix()):
            count += 1
    return count


def git_status_path(*, line: str) -> str:
    path = line[_GIT_STATUS_PREFIX_LEN:] if len(line) > _GIT_STATUS_PREFIX_LEN else ""
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.strip()


def proposed_path_excluded(*, path: str) -> bool:
    return path == "" or path.startswith(_EXCLUDED_PATH_PREFIXES)


def enrich_rows_with_evidence(
    *,
    repo: Path,
    rows: list[dict[str, object]],
    pane_captures: object = None,
) -> list[dict[str, object]]:
    changes = proposed_changes_count(repo=repo)
    return [
        enrich_row_with_evidence(
            row=row,
            proposed_changes=changes,
            pane_captures=pane_captures,
        )
        for row in rows
    ]


def enrich_row_with_evidence(
    *,
    row: dict[str, object],
    proposed_changes: int,
    pane_captures: object,
) -> dict[str, object]:
    enriched = dict(row)
    premises = row_wait_premises(row=row)
    if premises:
        enriched["wait_premises"] = premises
    if not row_supports_evidence(row=row, pane_captures=pane_captures):
        return enriched
    enriched["proposed_changes_count"] = proposed_changes
    enriched["pane_content_hash"] = row_pane_content_hash(
        row=row,
        pane_captures=pane_captures,
    )
    return enriched


def row_wait_premises(*, row: dict[str, object]) -> list[dict[str, object]]:
    repo = row.get("repo")
    topic = row.get("topic")
    if not isinstance(repo, str) or repo == "" or not isinstance(topic, str) or topic == "":
        return []
    return wait_premises.read_wait_premises(repo=repo, topic=topic)


def row_supports_evidence(*, row: dict[str, object], pane_captures: object) -> bool:
    return isinstance(row.get("tmux"), str) and (
        "picker_open" in row
        or "stall_seconds" in row
        or "supervisor_state_age" in row
        or pane_captures is not None
    )


def row_pane_content_hash(*, row: dict[str, object], pane_captures: object) -> str | None:
    tmux_name = row.get("tmux")
    if not isinstance(tmux_name, str) or tmux_name == "":
        return None
    capture = pane_capture_text(session=tmux_name, pane_captures=pane_captures)
    if capture is None:
        return None
    return pane_content_hash(text=capture)


def pane_capture_text(*, session: str, pane_captures: object) -> str | None:
    mapping = jsonio.as_object(value=pane_captures)
    if mapping is not None:
        value = mapping.get(session)
        return value if isinstance(value, str) else None
    if callable(pane_captures):
        return cast("PaneCaptureSource", pane_captures)(session=session)
    return tmuxio.TmuxIO().capture_pane(session=session)
