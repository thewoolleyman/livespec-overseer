"""Typed wait-premise records for dispatch-shaped waits.

A typed wait premise records why an actor believes a wait is mechanical rather
than prose-only: a bounded target, a source that can be re-queried, when that
claim was recorded, and when it must be checked again. The files live only under
the already-sanctioned overseer scratch roots:

- daemon/session actors: ``<repo>/tmp/overseer/<topic>/wait-premises/``
- foreman actors: ``<repo>/tmp/overseer/foreman/wait-premises/``

Schema version 1 is intentionally flat JSON:

``kind``
    One of ``fabro-run``, ``pr``, ``ci-run``, or ``work-item-close``.
``target_id``
    The concrete run, pull request, CI run, or work-item identifier.
``evidence_source``
    The command or API surface a later actor should re-query.
``recorded_at``
    UTC timestamp for the claim.
``recheck_by``
    UTC timestamp by which the liveness leg must be refreshed.

Untyped prose waits remain legal; they simply do not produce one of these
records and keep the existing re-read discipline.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

import jsonio

__all__: list[str] = [
    "WAIT_PREMISE_KINDS",
    "read_wait_premises",
    "wait_premise_dir",
    "wait_premise_path",
    "wait_premise_record",
    "write_wait_premise",
]

WAIT_PREMISE_KINDS = ("fabro-run", "pr", "ci-run", "work-item-close")
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def wait_premise_record(
    *,
    kind: str,
    target_id: str,
    evidence_source: str,
    recorded_at: str,
    recheck_by: str,
) -> dict[str, object]:
    require_kind(kind=kind)
    require_non_empty(field="target_id", value=target_id)
    require_non_empty(field="evidence_source", value=evidence_source)
    require_timestamp(field="recorded_at", value=recorded_at)
    require_timestamp(field="recheck_by", value=recheck_by)
    return {
        "kind": kind,
        "target_id": target_id,
        "evidence_source": evidence_source,
        "recorded_at": recorded_at,
        "recheck_by": recheck_by,
    }


def write_wait_premise(
    *,
    repo: str | os.PathLike[str],
    topic: str,
    **fields: str,
) -> Path:
    kind = required_field(fields=fields, field="kind")
    target_id = required_field(fields=fields, field="target_id")
    record = wait_premise_record(
        kind=kind,
        target_id=target_id,
        evidence_source=required_field(fields=fields, field="evidence_source"),
        recorded_at=required_field(fields=fields, field="recorded_at"),
        recheck_by=required_field(fields=fields, field="recheck_by"),
    )
    path = wait_premise_path(repo=repo, topic=topic, kind=kind, target_id=target_id)
    write_json_atomic(path=path, payload=record)
    return path


def read_wait_premises(*, repo: str | os.PathLike[str], topic: str) -> list[dict[str, object]]:
    directory = wait_premise_dir(repo=repo, topic=topic)
    try:
        paths = sorted(directory.glob("*.json"))
    except OSError:
        return []
    records: list[dict[str, object]] = []
    for path in paths:
        record = read_wait_premise(path=path)
        if record is not None:
            records.append(record)
    return records


def wait_premise_path(
    *, repo: str | os.PathLike[str], topic: str, kind: str, target_id: str
) -> Path:
    directory = wait_premise_dir(repo=repo, topic=topic)
    require_kind(kind=kind)
    require_non_empty(field="target_id", value=target_id)
    safe_target = _SAFE_FILENAME.sub("-", target_id).strip(".-")
    if safe_target == "":
        safe_target = "target"
    return directory / f"{kind}-{safe_target}.json"


def wait_premise_dir(*, repo: str | os.PathLike[str], topic: str) -> Path:
    repo_path = Path(repo)
    if str(repo_path) == "." or str(repo_path) == "":
        msg = "repo must be non-empty"
        raise ValueError(msg)
    require_non_empty(field="topic", value=topic)
    return repo_path / "tmp" / "overseer" / topic / "wait-premises"


def read_wait_premise(*, path: Path) -> dict[str, object] | None:
    try:
        parsed_result = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    except OSError:
        return None
    if jsonio.is_parse_failure(result=parsed_result):
        return None
    parsed = parsed_result.unwrap()
    if parsed is None:
        return None
    return parsed if valid_wait_premise(value=parsed) else None


def valid_wait_premise(*, value: dict[str, object]) -> bool:
    return (
        isinstance(value.get("kind"), str)
        and value["kind"] in WAIT_PREMISE_KINDS
        and isinstance(value.get("target_id"), str)
        and value["target_id"] != ""
        and isinstance(value.get("evidence_source"), str)
        and value["evidence_source"] != ""
        and isinstance(value.get("recorded_at"), str)
        and timestamp_valid(value=str(value["recorded_at"]))
        and isinstance(value.get("recheck_by"), str)
        and timestamp_valid(value=str(value["recheck_by"]))
    )


def write_json_atomic(*, path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            _ = handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _ = temp_path.replace(target=path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise


def require_kind(*, kind: str) -> None:
    if kind not in WAIT_PREMISE_KINDS:
        msg = f"kind must be one of {', '.join(WAIT_PREMISE_KINDS)}"
        raise ValueError(msg)


def required_field(*, fields: dict[str, str], field: str) -> str:
    try:
        return fields[field]
    except KeyError:
        msg = f"{field} is required"
        raise ValueError(msg) from None


def require_non_empty(*, field: str, value: str) -> None:
    if value == "":
        msg = f"{field} must be non-empty"
        raise ValueError(msg)


def require_timestamp(*, field: str, value: str) -> None:
    if not timestamp_valid(value=value):
        msg = f"{field} must be an ISO-8601 timestamp"
        raise ValueError(msg)


def timestamp_valid(*, value: str) -> bool:
    try:
        _ = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True
