"""File-backed provenance for peer-injected pane input."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import streams

__all__: list[str] = [
    "DEFAULT_PATH",
    "clear",
    "latest",
    "record_peer",
    "status",
]

DEFAULT_PATH = Path.home() / ".livespec-overseer-input-provenance.json"


def _negative(*, session: str | None) -> dict[str, object]:
    return {
        "peer_injected": False,
        "target_session": session,
    }


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _warn(*, message: str) -> None:
    streams.write_stderr(text=f"overseer.input_provenance: {message}\n")


def _read(*, path: Path) -> dict[str, dict[str, object]]:
    try:
        raw = path.read_text(encoding="utf-8")
        parsed: object = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    raw_records = cast(dict[str, object], parsed)
    records: dict[str, dict[str, object]] = {}
    for session, record in raw_records.items():
        if isinstance(record, dict):
            records[session] = dict(cast(dict[str, object], record))
    return records


def _write(*, path: Path, records: dict[str, dict[str, object]]) -> None:
    body = json.dumps(records, indent=2, sort_keys=True) + "\n"
    try:
        _ = path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        _ = tmp.write_text(body, encoding="utf-8")
        _ = tmp.replace(path)
    except OSError as exc:
        _warn(message=f"write failed: {exc}")


def record_peer(*, path: Path, session: str, sending_seat: str) -> None:
    records = _read(path=path)
    records[session] = {
        "peer_injected": True,
        "sending_seat": sending_seat,
        "target_session": session,
        "delivery": "bracketed-paste",
        "recorded_at": _utc_now(),
    }
    _write(path=path, records=records)


def clear(*, path: Path, session: str) -> None:
    records = _read(path=path)
    if session in records:
        _ = records.pop(session)
        _write(path=path, records=records)


def latest(*, path: Path, session: str) -> dict[str, object]:
    record = _read(path=path).get(session)
    if record is None:
        return _negative(session=session)
    return dict(record)


def status(*, path: Path, session: str | None) -> dict[str, object]:
    if session is None:
        return _negative(session=None)
    return latest(path=path, session=session)
