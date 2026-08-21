"""Model-enforcement orchestration for caam account rotation."""

from __future__ import annotations

from pathlib import Path

from caam_effort import enforce_effort_floor

__all__: list[str] = [
    "enforce_models",
]


def enforce_models(*, settings_path: Path, no_models: bool) -> list[str]:
    messages = enforce_effort_floor(settings_path=settings_path)
    if no_models:
        return messages
    return messages
