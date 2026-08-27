# livespec-lloc-soft-band-owner: overseer-tdfe.2
"""Typed records for foreman convene obligations and their outcomes."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path
from typing import cast

from foreman_wait_publication import (
    ESCALATION_AWAITING_ANSWER,
    WaitPublisher,
    WaitState,
    publish_wait_state,
)

__all__: list[str] = [
    "WAIT_PUBLISHER",
    "convene_obligation_path",
    "main",
    "write_convene_discharge",
    "write_convene_escalation",
    "write_convene_obligation",
]

# The declared seam for the wait publication in `write_convene_escalation`. A
# module binding rather than a parameter: that function already sits at the
# argument ceiling, and it is read at CALL time, so redirecting it on THIS
# module — the one that reads it — is what takes effect.
WAIT_PUBLISHER: WaitPublisher = publish_wait_state

_SCHEMA_VERSION = 1
_FOREMAN_STATE = Path("tmp") / "overseer" / "foreman"
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
_HEX_DIGEST_LENGTH = 64


def write_convene_obligation(
    *,
    repo: str | os.PathLike[str],
    topic: str,
    **fields: object,
) -> Path:
    question_fingerprint = str_field(fields=fields, field="question_fingerprint")
    action_id = str_field(fields=fields, field="action_id")
    record: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "kind": "foreman-convene-obligation",
        "question_fingerprint": question_fingerprint,
        "action_id": action_id,
        "human_valve": {"category": str_field(fields=fields, field="human_valve_category")},
        "observed_at_epoch": epoch_field(fields=fields),
        "request": request_field(fields=fields, question_fingerprint=question_fingerprint),
    }
    path = convene_obligation_path(
        repo=repo,
        topic=topic,
        action_id=action_id,
        question_fingerprint=question_fingerprint,
    )
    write_json_atomic(path=path, payload=record)
    return path


def write_convene_discharge(
    *,
    repo: str | os.PathLike[str],
    topic: str,
    question_fingerprint: str,
    reason: str,
    observed_at_epoch: float,
    request: dict[str, object],
) -> Path:
    return write_outcome(
        repo=repo,
        topic=topic,
        root="convene-discharges",
        fields={
            "question_fingerprint": question_fingerprint,
            "reason": reason,
            "observed_at_epoch": observed_at_epoch,
            "request": request,
        },
    )


def write_convene_escalation(
    *,
    repo: str | os.PathLike[str],
    topic: str,
    question_fingerprint: str,
    reason: str,
    observed_at_epoch: float,
    request: dict[str, object],
) -> Path:
    path = write_outcome(
        repo=repo,
        topic=topic,
        root="convene-escalations",
        fields={
            "question_fingerprint": question_fingerprint,
            "reason": reason,
            "observed_at_epoch": observed_at_epoch,
            "request": request,
        },
    )
    # An escalation is raised the moment this record lands, and from here it is
    # waiting on an answer. The private record above is written FIRST so an
    # unreachable ledger cannot cost the escalation; publishing second is what
    # makes the wait readable without opening the pane it was raised in.
    _ = WAIT_PUBLISHER(
        repo=Path(repo),
        wait=WaitState(kind=ESCALATION_AWAITING_ANSWER, plan=topic, detail=reason),
    )
    return path


def convene_obligation_path(
    *,
    repo: str | os.PathLike[str],
    topic: str,
    action_id: str,
    question_fingerprint: str,
) -> Path:
    require_non_empty(field="action_id", value=action_id)
    return record_path(
        repo=repo,
        topic=topic,
        root="convene-obligations",
        prefix=action_id,
        question_fingerprint=question_fingerprint,
    )


def write_outcome(
    *,
    repo: str | os.PathLike[str],
    topic: str,
    root: str,
    fields: dict[str, object],
) -> Path:
    question_fingerprint = str_field(fields=fields, field="question_fingerprint")
    reason = str_field(fields=fields, field="reason")
    observed_at_epoch = epoch_field(fields=fields)
    request = request_field(fields=fields, question_fingerprint=question_fingerprint)
    require_non_empty(field="reason", value=reason)
    record: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "kind": f"foreman-{root[:-1]}",
        "question_fingerprint": question_fingerprint,
        "reason": reason,
        "observed_at_epoch": observed_at_epoch,
        "request": request,
    }
    path = record_path(
        repo=repo,
        topic=topic,
        root=root,
        prefix=reason,
        question_fingerprint=question_fingerprint,
    )
    write_json_atomic(path=path, payload=record)
    return path


def record_path(
    *,
    repo: str | os.PathLike[str],
    topic: str,
    root: str,
    prefix: str,
    question_fingerprint: str,
) -> Path:
    repo_path = Path(repo)
    if str(repo_path) == "." or str(repo_path) == "":  # pragma: no cover
        msg = "repo must be non-empty"
        raise ValueError(msg)
    require_non_empty(field="topic", value=topic)
    require_question_fingerprint(question_fingerprint=question_fingerprint)
    safe_prefix = _SAFE_FILENAME.sub("-", prefix).strip(".-") or "record"
    digest = sha256(f"{prefix}\0{question_fingerprint}".encode()).hexdigest()[:12]
    filename = f"{safe_prefix}-{question_fingerprint[:12]}-{digest}.json"
    return repo_path / _FOREMAN_STATE / root / topic / filename


def str_field(*, fields: dict[str, object], field: str) -> str:
    value = fields.get(field)
    if not isinstance(value, str):  # pragma: no cover
        msg = f"{field} is required"
        raise TypeError(msg)
    require_non_empty(field=field, value=value)
    return value


def epoch_field(*, fields: dict[str, object]) -> float:
    value = fields.get("observed_at_epoch")
    if isinstance(value, bool) or not isinstance(value, int | float):  # pragma: no cover
        msg = "observed_at_epoch is required"
        raise TypeError(msg)
    return float(value)


def request_field(*, fields: dict[str, object], question_fingerprint: str) -> dict[str, object]:
    value = fields.get("request")
    if not isinstance(value, dict):  # pragma: no cover
        msg = "request is required"
        raise TypeError(msg)
    request = cast("dict[str, object]", value)
    require_request_fingerprint(request=request, question_fingerprint=question_fingerprint)
    return request


def require_non_empty(*, field: str, value: str) -> None:
    if value == "":  # pragma: no cover
        msg = f"{field} must be non-empty"
        raise ValueError(msg)


def require_question_fingerprint(*, question_fingerprint: str) -> None:
    if len(question_fingerprint) != _HEX_DIGEST_LENGTH or any(
        character not in "0123456789abcdef" for character in question_fingerprint
    ):  # pragma: no cover
        msg = "question_fingerprint must be a sha256 hex digest"
        raise ValueError(msg)


def require_request_fingerprint(*, request: dict[str, object], question_fingerprint: str) -> None:
    if request.get("question_fingerprint") != question_fingerprint:  # pragma: no cover
        msg = "request.question_fingerprint must match question_fingerprint"
        raise ValueError(msg)


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
    except OSError:  # pragma: no cover
        temp_path.unlink(missing_ok=True)
        raise


def main(*, argv: Sequence[str] | None = None) -> int:  # pragma: no cover
    # Deferred so the CLI can import the writers above without a cycle, matching
    # `foreman_plan_roster`'s split. The public entry point stays HERE, so
    # `python -m foreman_convene_obligations` and every existing caller are
    # unchanged by the split.
    from foreman_convene_obligations_cli import main as cli_main

    return cli_main(argv=argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
