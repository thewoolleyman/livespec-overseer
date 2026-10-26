"""The Claude state caam must preserve across a credential activation."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from caam_effort import EFFORT_ORDER, wanted_effort
from caam_profile_state import caam_vault

__all__: list[str] = [
    "ClaudeState",
    "apply_identity_state",
    "capture_state",
]

_PROFILE_MODE: Final = 0o600
_EFFORT_KEY: Final = "effortLevel"


@dataclass(frozen=True, kw_only=True)
class ClaudeState:
    """The pre-activation files whose non-credential state survives a switch."""

    profile: dict[str, object]
    profile_path: Path
    settings_bytes: bytes
    settings_path: Path
    target_profile: dict[str, object]


def capture_state(*, home: Path, target_name: str) -> ClaudeState | None:
    """Read the state to preserve before caam overwrites it, if it exists."""
    profile_path = home / ".claude.json"
    settings_path = home / ".claude/settings.json"
    target_path = caam_vault(home=home) / target_name / ".claude.json"
    if not (profile_path.exists() or settings_path.exists() or target_path.exists()):
        return None
    return ClaudeState(
        profile=_read_object(path=profile_path),
        profile_path=profile_path,
        settings_bytes=settings_path.read_bytes(),
        settings_path=settings_path,
        target_profile=_read_object(path=target_path),
    )


def apply_identity_state(*, state: ClaudeState) -> None:
    """Restore live preferences and replace only the target account identity."""
    merged = dict(state.profile)
    merged["oauthAccount"] = state.target_profile["oauthAccount"]
    _atomic_write(
        path=state.profile_path,
        body=(json.dumps(merged, indent=2) + "\n").encode("utf-8"),
    )
    _atomic_write(
        path=state.settings_path,
        body=_settings_with_floor(settings_bytes=state.settings_bytes),
    )


def _read_object(*, path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def _settings_with_floor(*, settings_bytes: bytes) -> bytes:
    """Raise the effort floor without reserializing any unrelated settings."""
    settings = cast(dict[str, object], json.loads(settings_bytes.decode("utf-8")))
    current = settings.get(_EFFORT_KEY)
    want = wanted_effort()
    if not _below_floor(current=current, want=want):
        return settings_bytes
    value = json.dumps(want).encode("utf-8")
    key = re.escape(_EFFORT_KEY.encode("utf-8"))
    pattern = rb'("' + key + rb'"\s*:\s*)"(?:[^"\\]|\\.)*"'
    return re.sub(pattern, rb"\1" + value, settings_bytes, count=1)


def _below_floor(*, current: object, want: str) -> bool:
    ranks = {name: index for index, name in enumerate(EFFORT_ORDER)}
    return ranks.get(str(current), 0) < ranks.get(want, 0)


def _atomic_write(*, path: Path, body: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    with os.fdopen(descriptor, "wb") as handle:
        _ = handle.write(body)
    _ = temporary_path.chmod(_PROFILE_MODE)
    _ = temporary_path.replace(path)
