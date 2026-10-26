"""Validated pre-switch state for a caam credential activation."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from caam_profile_state import caam_vault, live_creds_path

__all__: list[str] = [
    "LiveSwitchState",
    "StateValidationError",
    "apply_activated_state",
    "capture_live_state",
    "restore_rejected_state",
]

_IDENTITY_KEYS: Final = ("oauthAccount", "userID")
_EFFORT_KEY: Final = "effortLevel"
_EFFORT_ORDER: Final = ("low", "medium", "high", "xhigh", "max")


class StateValidationError(Exception):
    """The state caam would overwrite cannot be safely preserved."""

    def __init__(self, *, path: Path, reason: str) -> None:
        super().__init__(f"{path} {reason}")


@dataclass(frozen=True, kw_only=True)
class LiveSwitchState:
    """Raw pre-switch files plus the identities to install after activation."""

    credential_bytes: bytes
    credential_path: Path
    profile: dict[str, object]
    profile_bytes: bytes
    profile_path: Path
    settings: dict[str, object]
    settings_bytes: bytes
    settings_path: Path
    target_profile: dict[str, object]


def capture_live_state(*, home: Path, target_name: str) -> LiveSwitchState:
    """Read every live byte before activation and reject invalid global state."""
    credential_path = live_creds_path(home=home)
    profile_path = home / ".claude.json"
    settings_path = home / ".claude/settings.json"
    target_path = caam_vault(home=home) / target_name / ".claude.json"
    credential_bytes = credential_path.read_bytes()
    profile_bytes = profile_path.read_bytes()
    settings_bytes = settings_path.read_bytes()
    profile = _read_object(path=profile_path, body=profile_bytes)
    settings = _read_object(path=settings_path, body=settings_bytes)
    target_profile = _read_object(path=target_path, body=target_path.read_bytes())
    missing = [key for key in _IDENTITY_KEYS if key not in target_profile]
    if missing:
        raise StateValidationError(
            path=target_path,
            reason="is missing required " + ", ".join(missing),
        )
    return LiveSwitchState(
        credential_bytes=credential_bytes,
        credential_path=credential_path,
        profile=profile,
        profile_bytes=profile_bytes,
        profile_path=profile_path,
        settings=settings,
        settings_bytes=settings_bytes,
        settings_path=settings_path,
        target_profile=target_profile,
    )


def restore_rejected_state(*, state: LiveSwitchState) -> None:
    """Return all three caam-overwritten live files to their captured bytes."""
    _atomic_write(path=state.credential_path, body=state.credential_bytes)
    _atomic_write(path=state.profile_path, body=state.profile_bytes)
    _atomic_write(path=state.settings_path, body=state.settings_bytes)


def apply_activated_state(*, state: LiveSwitchState) -> None:
    """Restore host state after caam replaces its three files under the switch lock."""
    profile = dict(state.profile)
    for key in _IDENTITY_KEYS:
        profile[key] = state.target_profile[key]
    _atomic_write(
        path=state.profile_path,
        body=(json.dumps(profile, indent=2) + "\n").encode("utf-8"),
    )
    _atomic_write(
        path=state.settings_path,
        body=_settings_with_effort_floor(state=state),
    )


def _settings_with_effort_floor(*, state: LiveSwitchState) -> bytes:
    """Return captured settings with only a below-floor effort value changed."""
    wanted = os.environ.get("CAAM_ROTATE_EFFORT", "high")
    current = state.settings.get(_EFFORT_KEY)
    if not wanted or _is_at_or_above_floor(current=current, wanted=wanted):
        return state.settings_bytes
    return _replace_top_level_value(
        body=state.settings_bytes,
        key=_EFFORT_KEY,
        value=wanted,
        has_members=bool(state.settings),
    )


def _is_at_or_above_floor(*, current: object, wanted: str) -> bool:
    """Whether one captured effort value needs no repair for this floor."""
    if not isinstance(current, str):
        return False
    if current not in _EFFORT_ORDER or wanted not in _EFFORT_ORDER:
        return current == wanted
    return _EFFORT_ORDER.index(current) >= _EFFORT_ORDER.index(wanted)


def _replace_top_level_value(*, body: bytes, key: str, value: str, has_members: bool) -> bytes:
    """Change or add one top-level JSON member without reserializing its siblings."""
    text = body.decode("utf-8")
    span = _top_level_value_span(text=text, key=key)
    rendered = json.dumps(value)
    if span is not None:
        start, end = span
        return (text[:start] + rendered + text[end:]).encode("utf-8")
    closing = text.rfind("}")
    separator = "," if has_members else ""
    member = "\n  " + json.dumps(key) + ": " + rendered
    return (text[:closing] + separator + member + text[closing:]).encode("utf-8")


def _top_level_value_span(*, text: str, key: str) -> tuple[int, int] | None:
    """Find one top-level object's value span using the JSON parser's own grammar."""
    decoder = json.JSONDecoder()
    index = _skip_whitespace(text=text, index=0) + 1
    while True:
        index = _skip_whitespace(text=text, index=index)
        if text[index] == "}":
            return None
        name, index = decoder.raw_decode(text, index)
        index = _skip_whitespace(text=text, index=index) + 1
        start = _skip_whitespace(text=text, index=index)
        _, end = decoder.raw_decode(text, start)
        if name == key:
            return (start, end)
        index = _skip_whitespace(text=text, index=end)
        if text[index] == "}":
            return None
        index += 1


def _skip_whitespace(*, text: str, index: int) -> int:
    """Advance over JSON's allowed whitespace before the next structural token."""
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _read_object(*, path: Path, body: bytes) -> dict[str, object]:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateValidationError(path=path, reason="is not valid JSON") from exc
    if not isinstance(value, dict):
        raise StateValidationError(path=path, reason="does not contain a JSON object")
    return cast(dict[str, object], value)


def _atomic_write(*, path: Path, body: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, raw_path = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary = Path(raw_path)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            _ = handle.write(body)
        temporary.chmod(0o600)
        _ = temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
