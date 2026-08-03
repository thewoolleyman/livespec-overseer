"""Primitive source readers for the foreman gatherer."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import jsonio

__all__: list[str] = [
    "command_skipped",
    "default_needs_attention_command",
    "read_journal",
    "run_json_command",
]


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
    return jsonio.parse_object(text=stripped)


def default_needs_attention_command(*, repo: Path) -> list[str] | None:
    script = repo / "needs_attention.py"
    if not script.is_file():
        return None
    config = parse_repo_config(repo=repo)
    wrapper = string_list(value=config.get("credential_wrapper")) if config is not None else None
    prefix = wrapper if wrapper is not None else []
    return [*prefix, sys.executable, str(script), "--json"]


def command_skipped(*, command: Sequence[str], reason: str) -> dict[str, object]:
    return {"status": "skipped", "command": list(command), "reason": reason}


def run_json_command(*, command: Sequence[str], source_name: str) -> dict[str, object] | None:
    try:
        completed = subprocess.run(  # noqa: S603
            list(command),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except FileNotFoundError:
        return None
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"__skip_reason__": type(exc).__name__}
    if completed.returncode != 0:
        return {"__skip_reason__": f"exit {completed.returncode}"}
    parsed = jsonio.parse_object(text=completed.stdout)
    if parsed is None:
        msg = f"{source_name} produced malformed or non-object JSON"
        raise ValueError(msg)
    return parsed


def read_journal(*, path: Path, limit: int) -> tuple[list[dict[str, object]], dict[str, object]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], {"status": "skipped", "path": str(path), "reason": "file not found"}
    records: list[dict[str, object]] = []
    for line in lines:
        parsed = jsonio.parse_object_line(line=line)
        if parsed is None:
            msg = "dispatch_journal contains malformed or non-object JSONL"
            raise ValueError(msg)
        records.append(parsed)
    tail = records[-limit:] if limit > 0 else []
    return tail, {"status": "ok", "path": str(path), "records_read": len(tail)}
