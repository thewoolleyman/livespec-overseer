"""File and path helpers for foreman panel dossiers."""

from __future__ import annotations

import json
from pathlib import Path

import jsonio
from foreman_consensus_types import DEFAULT_STATE_DIR

__all__: list[str] = [
    "default_dossier_dir",
    "load_request",
    "write_json",
]


def str_field(*, payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def default_dossier_dir(*, request: dict[str, object], key: str) -> Path:
    repo = Path(str_field(payload=request, key="repo"))
    if repo.is_absolute():
        return repo / DEFAULT_STATE_DIR / "panel" / key
    return DEFAULT_STATE_DIR / "panel" / key


def write_json(*, path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_request(*, path: Path) -> dict[str, object] | None:
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()
