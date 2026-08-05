"""Round certification-floor records stored in the injection sidecar."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import jsonio
from _registry_core import atomic_write, file_lock, norm, resolve_stamp_store, warn

__all__: list[str] = [
    "RoundRecord",
    "read_round_open_identity",
    "read_round_record",
    "record_ready_void",
]


@dataclass(frozen=True, kw_only=True)
class RoundRecord:
    at: float | None
    bands: list[int]
    voided_at: float | None
    session_identity: str | None
    malformed_reason: str | None

    @property
    def certification_floor(self) -> float | None:
        if self.at is None:
            return None
        if self.voided_at is None:
            return self.at
        return max(self.at, self.voided_at)


def _stamp_key(*, repo: str, topic: str) -> str:
    return f"{norm(repo=repo)}\t{topic}"


def _read_stamp_data(*, path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        warn(message=f"unreadable injection-stamp sidecar {path}: {exc}")
        return {}
    stamp = jsonio.as_object(value=data)
    if stamp is None:
        warn(message=f"injection-stamp sidecar {path} is not a JSON object")
        return {}
    return stamp


def read_round_record(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> RoundRecord:
    """Read the full round sidecar record used by the restart interlock."""
    data = _read_stamp_data(path=resolve_stamp_store(stamp_path=stamp_path))
    value = data.get(_stamp_key(repo=repo, topic=topic))
    if value is None:
        return RoundRecord(
            at=None,
            bands=[],
            voided_at=None,
            session_identity=None,
            malformed_reason=None,
        )
    entry = jsonio.as_object(value=value)
    if entry is None:
        return _legacy_record(value=value, repo=repo, topic=topic)
    return _dict_record(entry=entry)


def _legacy_record(*, value: object, repo: str, topic: str) -> RoundRecord:
    at = jsonio.as_float(value=value)
    reason = None if at is None else "round record missing session identity"
    if at is None:
        reason = "non-numeric injection stamp"
        warn(message=f"non-numeric injection stamp for {repo}::{topic}")
    return RoundRecord(
        at=at,
        bands=[],
        voided_at=None,
        session_identity=None,
        malformed_reason=reason,
    )


def _dict_record(*, entry: dict[str, object]) -> RoundRecord:
    at = jsonio.as_float(value=entry.get("at"))
    voided_at_raw = entry.get("voided_at")
    voided_at = jsonio.as_float(value=voided_at_raw) if voided_at_raw is not None else None
    identity = entry.get("session_identity")
    session_identity = identity if isinstance(identity, str) and identity else None
    bands_raw = jsonio.as_list(value=entry.get("bands"))
    bands = [b for b in bands_raw if isinstance(b, int)] if bands_raw is not None else []
    return RoundRecord(
        at=at,
        bands=bands,
        voided_at=voided_at,
        session_identity=session_identity,
        malformed_reason=_malformed_reason(
            at=at,
            voided_at_raw=voided_at_raw,
            voided_at=voided_at,
            session_identity=session_identity,
        ),
    )


def _malformed_reason(
    *,
    at: float | None,
    voided_at_raw: object,
    voided_at: float | None,
    session_identity: str | None,
) -> str | None:
    if at is None:
        return "missing or non-numeric injection stamp"
    if voided_at_raw is not None and voided_at is None:
        return "non-numeric ready void instant"
    if session_identity is None:
        return "round record missing session identity"
    return None


def read_round_open_identity(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> str | None:
    return read_round_record(repo=repo, topic=topic, stamp_path=stamp_path).session_identity


def record_ready_void(
    *,
    repo: str,
    topic: str,
    ts: float,
    floor_min: float,
    stamp_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Raise the round's ready-void floor without closing the round."""
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = _read_stamp_data(path=path)
        key = _stamp_key(repo=repo, topic=topic)
        existing = jsonio.as_object(value=data.get(key))
        if existing is None:
            return False
        entry: dict[str, object] = dict(existing)
        entry["voided_at"] = max(float(ts), float(floor_min))
        data[key] = entry
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")
        return True
