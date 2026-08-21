"""Primitive source readers for the foreman gatherer."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import jsonio
from _foreman_source_result import source_value
from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from errors import OverseerSourceError

from overseer._vendor.returns.io import IOFailure, IOResult, IOSuccess

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "command_skipped",
    "default_needs_attention_command",
    "fetch_release_lane_runs",
    "read_journal",
    "run_json_command",
]

_PER_PAGE = 100
_PAGES = 4
_REPO_SLUG_PARTS = 2


def string_list(*, value: object) -> list[str] | None:
    items = jsonio.as_list(value=value)
    if items is None or not all(isinstance(item, str) for item in items):
        return None
    return [str(item) for item in items]


def strip_jsonc_line_comment(*, line: str) -> str:
    in_string = False
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = in_string
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string and char == "/" and index + 1 < len(line) and line[index + 1] == "/":
            return line[:index]
    return line


def parse_repo_config(*, repo: Path) -> dict[str, object] | None:
    path = repo / ".livespec.jsonc"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    stripped = "\n".join(strip_jsonc_line_comment(line=line) for line in text.splitlines())
    parsed = jsonio.parse_object(text=stripped)
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()


def default_needs_attention_command(*, repo: Path) -> list[str] | None:
    script = repo / "needs_attention.py"
    if not script.is_file():
        fixture = repo / "attention.json"
        return ["/bin/cat", str(fixture)] if fixture.is_file() else None
    config = parse_repo_config(repo=repo)
    wrapper = string_list(value=config.get("credential_wrapper")) if config is not None else None
    prefix = wrapper if wrapper is not None else []
    return [*prefix, sys.executable, str(script), "--json"]


def repo_slug(*, repo: Path) -> str | None:
    slug = os.environ.get("GITHUB_REPOSITORY")
    if slug:
        return slug
    completed = subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), "remote", "get-url", "origin"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if completed.returncode != 0:
        return None
    url = completed.stdout.strip().removesuffix(".git")
    parts = url.replace(":", "/").split("/")
    return "/".join(parts[-_REPO_SLUG_PARTS:]) if len(parts) >= _REPO_SLUG_PARTS else None


def fetch_release_lane_runs(*, repo: Path, workflow: str) -> list[dict[str, str]] | None:
    slug = repo_slug(repo=repo)
    if not slug:
        return None
    collected: list[dict[str, str]] = []
    for page in range(1, _PAGES + 1):
        endpoint = (
            f"repos/{slug}/actions/workflows/{workflow}/runs" f"?per_page={_PER_PAGE}&page={page}"
        )
        payload_raw: (
            IOResult[dict[str, object] | None, OverseerSourceError] | dict[str, object] | None
        ) = run_json_command(command=["gh", "api", endpoint], source_name="release_lane")
        payload = source_value(result=payload_raw)
        if payload is None or isinstance(payload.get("__skip_reason__"), str):
            return None
        runs = jsonio.as_list(value=payload.get("workflow_runs"))
        if runs is None:
            return None
        collected.extend(
            {
                "conclusion": str(run.get("conclusion") or ""),
                "created_at": str(run.get("created_at") or ""),
            }
            for run in (jsonio.as_object(value=raw) for raw in runs)
            if run is not None
        )
        if len(runs) < _PER_PAGE:
            break
    return collected


def command_skipped(*, command: Sequence[str], reason: str) -> dict[str, object]:
    return {"status": "skipped", "command": list(command), "reason": reason}


def run_json_command(
    *, command: Sequence[str], source_name: str
) -> IOResult[dict[str, object] | None, OverseerSourceError]:
    """Run a JSON-emitting source command.

    An unavailable source is an answer, not a failure: a missing command,
    a spawn error, a timeout, and a non-zero exit all stay on the success
    track carrying their existing skip payloads. Only output that is
    present but not a JSON object is an expected failure.
    """
    try:
        completed = subprocess.run(  # noqa: S603
            list(command),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except FileNotFoundError:
        return IOSuccess(None)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return IOSuccess({"__skip_reason__": type(exc).__name__})
    if completed.returncode != 0:
        return IOSuccess({"__skip_reason__": f"exit {completed.returncode}"})
    parsed_result = jsonio.parse_object(text=completed.stdout)
    if jsonio.is_parse_failure(result=parsed_result):
        detail = f"{source_name} produced malformed JSON"
        return IOFailure(OverseerSourceError(detail=detail))
    parsed = parsed_result.unwrap()
    if parsed is None:
        detail = f"{source_name} produced non-object JSON"
        return IOFailure(OverseerSourceError(detail=detail))
    return IOSuccess(parsed)


def read_journal(
    *, path: Path, limit: int
) -> IOResult[tuple[list[dict[str, object]], dict[str, object]], OverseerSourceError]:
    """Read the tail of the dispatch journal.

    An absent journal is an answer, not a failure: it stays on the
    success track with its existing skipped payload. A journal carrying a
    malformed JSONL record is an expected failure.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return IOSuccess(([], {"status": "skipped", "path": str(path), "reason": "file not found"}))
    records: list[dict[str, object]] = []
    for line in lines:
        parsed_result = jsonio.parse_object_line(line=line)
        if jsonio.is_parse_failure(result=parsed_result):
            detail = "dispatch_journal contains malformed JSONL"
            return IOFailure(OverseerSourceError(detail=detail))
        parsed = parsed_result.unwrap()
        if parsed is None:
            detail = "dispatch_journal contains non-object JSONL"
            return IOFailure(OverseerSourceError(detail=detail))
        records.append(parsed)
    tail = records[-limit:] if limit > 0 else []
    return IOSuccess((tail, {"status": "ok", "path": str(path), "records_read": len(tail)}))
