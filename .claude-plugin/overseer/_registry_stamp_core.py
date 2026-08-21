"""Shared helpers for the injection-stamp sidecar."""

from __future__ import annotations

import json
from pathlib import Path

import jsonio
from _registry_core import norm, warn

__all__: list[str] = ["read_stamp_data", "stamp_key"]


def stamp_key(*, repo: str, topic: str) -> str:
    return f"{norm(repo=repo)}\t{topic}"


def read_stamp_data(*, path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    # ValueError subsumes BOTH json.JSONDecodeError and the UnicodeDecodeError a
    # non-UTF-8 sidecar raises.
    except (OSError, ValueError) as exc:
        warn(message=f"unreadable injection-stamp sidecar {path}: {exc}")
        return {}
    stamp = jsonio.as_object(value=data)
    if stamp is None:
        warn(message=f"injection-stamp sidecar {path} is not a JSON object")
        return {}
    return stamp
