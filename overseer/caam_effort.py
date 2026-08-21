"""Settings effort-floor enforcement for caam account rotation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Final

import jsonio

__all__: list[str] = [
    "EFFORT_ORDER",
    "enforce_effort_floor",
    "wanted_effort",
]

EFFORT_ORDER: Final = ("low", "medium", "high", "xhigh", "max")
_EFFORT_KEY: Final = "effortLevel"
_SETTINGS_MODE: Final = 0o600


def wanted_effort() -> str:
    return os.environ.get("CAAM_ROTATE_EFFORT", "high")


def enforce_effort_floor(*, settings_path: Path) -> list[str]:
    want = wanted_effort()
    if not want:
        return []

    settings = _read_settings(settings_path=settings_path)
    if settings is None:
        return []

    current = settings.get(_EFFORT_KEY)
    if _is_at_or_above_floor(current=current, want=want):
        return []

    settings[_EFFORT_KEY] = want
    if not _write_settings(settings_path=settings_path, settings=settings):
        return []

    return [
        f"effort: settings.json effortLevel {current!r} -> {want!r} "
        "(raised to the floor; a switch had reset it)"
    ]


def _read_settings(*, settings_path: Path) -> dict[str, object] | None:
    try:
        parsed = jsonio.parse_object(text=settings_path.read_text(encoding="utf-8"))
    except OSError:
        return None
    if jsonio.is_parse_failure(result=parsed):
        return None
    return parsed.unwrap()


def _is_at_or_above_floor(*, current: object, want: str) -> bool:
    if not isinstance(current, str):
        return False
    if current not in EFFORT_ORDER or want not in EFFORT_ORDER:
        return current == want
    return EFFORT_ORDER.index(current) >= EFFORT_ORDER.index(want)


def _write_settings(*, settings_path: Path, settings: dict[str, object]) -> bool:
    tmp_path = settings_path.with_name(settings_path.name + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2)
        tmp_path.chmod(_SETTINGS_MODE)
        _ = Path.replace(self=tmp_path, target=settings_path)
    except OSError:
        return False
    return True
