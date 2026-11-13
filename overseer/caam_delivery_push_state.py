"""The push service's role-holder files: host list, settings and per-host push state.

Everything here lives in the operation's host state directory on the role
holder, except the optional settings file. The push state records, per host,
the last result its apply step reported, what it last applied and when, its
last successful push, and its last error with that error's time. No token or
other credential material is ever recorded.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import caam_delivery_service
import jsonio
import streams

__all__: list[str] = [
    "CONFIG_FILE",
    "HOSTS_FILE",
    "KNOWN_HOSTS",
    "PUSH_STATE",
    "STATE_DIR",
    "Host",
    "due",
    "load_config",
    "load_hosts",
    "load_state",
    "record_result",
    "seconds",
]

STATE_DIR = ".local/state/caam-usage-rotate"
HOSTS_FILE = f"{STATE_DIR}/delivery-hosts"
KNOWN_HOSTS = f"{STATE_DIR}/delivery-known_hosts"
PUSH_STATE = f"{STATE_DIR}/delivery-push.json"
CONFIG_FILE = ".config/caam-delivery/config.json"
_HOST_FIELDS = 3

_DEFAULTS: dict[str, object] = {
    "ssh_key": "~/.ssh/id_ed25519",
    "push_timeout_s": 30.0,
    "retry_s": 60.0,
    "stale_after_s": 900.0,
    "reissue_timeout_s": 15.0,
}


@dataclass(frozen=True, kw_only=True)
class Host:
    label: str
    target: str
    platform: str


def load_config(*, home: Path) -> dict[str, object]:
    """Defaults overlaid by `~/.config/caam-delivery/config.json` when present."""
    body = _object(path=home / CONFIG_FILE) or {}
    return {key: body.get(key, value) for key, value in _DEFAULTS.items()}


def load_hosts(*, home: Path) -> list[Host]:
    """`<label> <user@host> <platform>` per line; a malformed line is reported and skipped."""
    path = home / HOSTS_FILE
    if not path.exists():
        return []
    hosts: list[Host] = []
    for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        fields = text.split("#", 1)[0].split()
        if not fields:
            continue
        if not _valid_host(fields=fields):
            streams.write_stderr(text=f"FAIL host list line {number} rejected\n")
            continue
        hosts.append(Host(label=fields[0], target=fields[1], platform=fields[2]))
    return hosts


def load_state(*, home: Path) -> dict[str, dict[str, object]]:
    body = _object(path=home / PUSH_STATE) or {}
    return {key: value for key, value in body.items() if isinstance(value, dict)}


def record_result(
    *, entry: dict[str, object], line: str, delivery: caam_delivery_service.Delivery, now: float
) -> None:
    """Fold one result line into a host's push record; errors carry their time."""
    entry["last_attempt"] = now
    entry["attempt_sequence"] = delivery.sequence
    entry["last_result"] = line
    words = line.split(";", 1)[0].split()
    word = words[0] if words else ""
    if _reached(words=words, sequence=delivery.sequence):
        entry.update(
            state="ok",
            applied_at=now,
            sequence=delivery.sequence,
            account_id=delivery.account_id,
            expires_at=delivery.oauth.get("expiresAt"),
            last_success=now,
        )
        return
    if word == "queued":
        entry["state"] = "queued"
        return
    if word == "not-converted":
        entry.update(state="not-converted", last_error="not-converted", last_error_at=now)
        return
    marked = line if word in ("failed", "stale-sequence") else "failed " + line
    entry.update(state="failed", last_error=marked, last_error_at=now)


def due(
    *, entry: dict[str, object], sequence: int, now: float, settings: dict[str, object]
) -> bool:
    """Whether a host with push record `entry` should be pushed `sequence` now."""
    applied = entry.get("sequence")
    attempted = entry.get("last_attempt")
    if not isinstance(attempted, float):
        return True
    waited = now - attempted
    if entry.get("state") == "not-converted":
        return waited >= seconds(settings=settings, key="stale_after_s")
    if isinstance(applied, int) and applied >= sequence:
        return False
    return entry.get("attempt_sequence") != sequence or waited >= seconds(
        settings=settings, key="retry_s"
    )


def seconds(*, settings: dict[str, object], key: str) -> float:
    """A duration setting, falling back to its default when it is not a number."""
    value = settings.get(key)
    if isinstance(value, int | float):
        return float(value)
    default = _DEFAULTS[key]
    return float(default) if isinstance(default, int | float) else 0.0


def _valid_host(*, fields: list[str]) -> bool:
    if len(fields) != _HOST_FIELDS or any(field.startswith("-") for field in fields):
        return False
    user, _, machine = fields[1].partition("@")
    return bool(user and machine) and "@" not in machine and fields[2] in ("linux", "macos")


def _reached(*, words: list[str], sequence: int) -> bool:
    """`applied <sequence>`, or a `stale-sequence` refusal from a host already holding it."""
    return words[:2] == ["applied", str(sequence)] or (
        words[:1] == ["stale-sequence"] and words[2:] == ["host-applied", str(sequence)]
    )


def _object(*, path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()
