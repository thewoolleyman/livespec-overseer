"""Typed wait-premise records for dispatch-shaped waits.

A typed wait premise records why an actor believes a wait is mechanical rather
than prose-only: a bounded target, a source that can be re-queried, when that
claim was recorded, and when it must be checked again. The files live only under
the already-sanctioned overseer scratch roots:

- daemon/session actors: ``<repo>/tmp/overseer/<topic>/wait-premises/``
- foreman actors: ``<repo>/tmp/overseer/foreman/wait-premises/``

Schema version 1 is intentionally flat JSON:

``schema_version``
    Integer schema version; currently ``1``.
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
from hashlib import sha256
from pathlib import Path

import _wait_premise_validation
import jsonio

__all__: list[str] = [
    "SCHEMA_VERSION",
    "WAIT_PREMISE_KINDS",
    "read_wait_premises",
    "remove_wait_premise",
    "wait_premise_dir",
    "wait_premise_path",
    "wait_premise_record",
    "write_wait_premise",
]

WAIT_PREMISE_KINDS = ("fabro-run", "pr", "ci-run", "work-item-close")
SCHEMA_VERSION = 1
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
_REQUIRED_FIELDS = frozenset({"kind", "target_id", "evidence_source", "recorded_at", "recheck_by"})


def wait_premise_record(
    *,
    kind: str,
    target_id: str,
    evidence_source: str,
    recorded_at: str,
    recheck_by: str,
) -> dict[str, object]:
    require_kind(kind=kind)
    _wait_premise_validation.require_non_empty(field="target_id", value=target_id)
    _wait_premise_validation.require_non_empty(field="evidence_source", value=evidence_source)
    _wait_premise_validation.require_timestamp(field="recorded_at", value=recorded_at)
    _wait_premise_validation.require_timestamp(field="recheck_by", value=recheck_by)
    return {
        "schema_version": SCHEMA_VERSION,
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
    kind = _wait_premise_validation.required_field(fields=fields, field="kind")
    target_id = _wait_premise_validation.required_field(fields=fields, field="target_id")
    record = wait_premise_record(
        kind=kind,
        target_id=target_id,
        evidence_source=_wait_premise_validation.required_field(
            fields=fields, field="evidence_source"
        ),
        recorded_at=_wait_premise_validation.required_field(fields=fields, field="recorded_at"),
        recheck_by=_wait_premise_validation.required_field(fields=fields, field="recheck_by"),
    )
    record.update({key: value for key, value in fields.items() if key not in _REQUIRED_FIELDS})
    path = wait_premise_path(repo=repo, topic=topic, kind=kind, target_id=target_id)
    write_json_atomic(path=path, payload=record)
    return path


def remove_wait_premise(
    *,
    repo: str | os.PathLike[str],
    topic: str,
    kind: str,
    target_id: str,
) -> Path:
    path = wait_premise_path(repo=repo, topic=topic, kind=kind, target_id=target_id)
    path.unlink(missing_ok=True)
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
        if record is None:
            # A legacy record migrated during THIS pass still belongs to it.
            # Returning it only on the next read made a single read report no
            # premises at all for a record that plainly exists.
            record = migrate_legacy_wait_premise(path=path)
        if record is not None:
            records.append(record)
    return records


def wait_premise_path(
    *, repo: str | os.PathLike[str], topic: str, kind: str, target_id: str
) -> Path:
    directory = wait_premise_dir(repo=repo, topic=topic)
    require_kind(kind=kind)
    _wait_premise_validation.require_non_empty(field="target_id", value=target_id)
    safe_target = _SAFE_FILENAME.sub("-", target_id).strip(".-")
    if safe_target == "":
        safe_target = "target"
    digest = sha256(target_id.encode("utf-8")).hexdigest()[:12]
    return directory / f"{kind}-{safe_target}-{digest}.json"


def wait_premise_dir(*, repo: str | os.PathLike[str], topic: str) -> Path:
    repo_path = Path(repo)
    if str(repo_path) == "." or str(repo_path) == "":
        msg = "repo must be non-empty"
        raise ValueError(msg)
    _wait_premise_validation.require_non_empty(field="topic", value=topic)
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


def migrate_legacy_wait_premise(*, path: Path) -> dict[str, object] | None:
    """Bring one versionless record forward, returning it when it lands.

    The source is removed only AFTER its migrated copy is safely in place, so a
    failed write can never lose the record. Leaving the source behind made one
    target hold two files: the migrated copy and a versionless original that
    every later read skipped and never reported.
    """
    parsed = legacy_record_at(path=path)
    if parsed is None:
        return None
    destination = wait_premise_path(
        repo=legacy_repo_from_path(path=path),
        topic=legacy_topic_from_path(path=path),
        kind=str(parsed["kind"]),
        target_id=str(parsed["target_id"]),
    )
    if destination == path:
        return None
    if destination.exists():
        # The record already came forward on an earlier pass; drop the stale
        # original rather than leaving it to be skipped on every future read.
        path.unlink(missing_ok=True)
        return None
    migrated = {**parsed, "schema_version": SCHEMA_VERSION}
    try:
        write_json_atomic(path=destination, payload=migrated)
    except OSError:
        return None
    path.unlink(missing_ok=True)
    return migrated


def legacy_record_at(*, path: Path) -> dict[str, object] | None:
    """Parse a record that is well-formed in every way EXCEPT its version."""
    try:
        parsed_result = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    except OSError:
        return None
    if jsonio.is_parse_failure(result=parsed_result):
        return None
    parsed = parsed_result.unwrap()
    if parsed is None or "schema_version" in parsed:
        return None
    return parsed if valid_legacy_wait_premise(value=parsed) else None


def valid_wait_premise(*, value: dict[str, object]) -> bool:
    return valid_schema_version(value=value) and valid_legacy_wait_premise(value=value)


def valid_legacy_wait_premise(*, value: dict[str, object]) -> bool:
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


def valid_schema_version(*, value: dict[str, object]) -> bool:
    return type(value.get("schema_version")) is int and value["schema_version"] == SCHEMA_VERSION


def legacy_repo_from_path(*, path: Path) -> Path:
    return path.parents[4]


def legacy_topic_from_path(*, path: Path) -> str:
    return path.parents[1].name


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
    _wait_premise_validation.require_kind(kind=kind, kinds=WAIT_PREMISE_KINDS)


def timestamp_valid(*, value: str) -> bool:
    return _wait_premise_validation.timestamp_valid(value=value)
