"""Shared durable paths and JSON helpers for the foreman runtime."""

from __future__ import annotations

import json
from pathlib import Path

import jsonio
import registry

__all__: list[str] = [
    "LOCK_FILE",
    "STATE_FILE",
    "atomic_json",
    "read_json_object",
    "runtime_dir",
    "state_path",
]

STATE_FILE = "runtime.json"
LOCK_FILE = "runtime.lock"


def runtime_dir(*, repo: Path) -> Path:
    return repo / "tmp" / "overseer" / "foreman"


def state_path(*, repo: Path) -> Path:
    return runtime_dir(repo=repo) / STATE_FILE


def read_json_object(*, path: Path) -> dict[str, object]:
    try:
        parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    if jsonio.is_parse_failure(result=parsed):
        return {}
    return parsed.unwrap() or {}


def atomic_json(*, path: Path, payload: dict[str, object]) -> None:
    registry.atomic_write(path=path, body=json.dumps(payload, indent=2, sort_keys=True) + "\n")
