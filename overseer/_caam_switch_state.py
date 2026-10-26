"""The Claude state caam preserves across a credential activation."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from caam_profile_state import caam_vault

__all__: list[str] = [
    "ClaudeState",
    "StateValidationError",
    "apply_identity_state",
    "capture_state",
]

_PROFILE_MODE: Final = 0o600


class StateValidationError(ValueError):
    """The account manager must not run when captured state is invalid."""


@dataclass(frozen=True, kw_only=True)
class ClaudeState:
    """The pre-activation files whose non-credential state survives a switch."""

    profile: dict[str, object]
    profile_path: Path
    settings_bytes: bytes
    settings_path: Path
    target_profile: dict[str, object]


def capture_state(*, home: Path, target_name: str) -> ClaudeState:
    """Capture and validate every state file before activation."""
    profile_path = home / ".claude.json"
    settings_path = home / ".claude/settings.json"
    target_path = caam_vault(home=home) / target_name / ".claude.json"
    state = ClaudeState(
        profile=_read_object(path=profile_path),
        profile_path=profile_path,
        settings_bytes=settings_path.read_bytes(),
        settings_path=settings_path,
        target_profile=_read_object(path=target_path),
    )
    for key in ("oauthAccount", "userID"):
        if key not in state.target_profile:
            raise StateValidationError(f"stored global state lacks {key}")
    _ = _read_object_bytes(body=state.settings_bytes)
    return state


def apply_identity_state(*, state: ClaudeState) -> None:
    """Restore live preferences and replace only the target account identity."""
    merged = dict(state.profile)
    merged["oauthAccount"] = state.target_profile["oauthAccount"]
    merged["userID"] = state.target_profile["userID"]
    _atomic_write(
        path=state.profile_path,
        body=(json.dumps(merged, indent=2) + "\n").encode("utf-8"),
    )
    _atomic_write(
        path=state.settings_path,
        body=state.settings_bytes,
    )


def _read_object(*, path: Path) -> dict[str, object]:
    return _read_object_bytes(body=path.read_bytes())


def _read_object_bytes(*, body: bytes) -> dict[str, object]:
    parsed = json.loads(body.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise StateValidationError("global state is not a JSON object")
    return cast(dict[str, object], parsed)


def _atomic_write(*, path: Path, body: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    with os.fdopen(descriptor, "wb") as handle:
        _ = handle.write(body)
    _ = temporary_path.chmod(_PROFILE_MODE)
    _ = temporary_path.replace(path)
