# livespec-lloc-soft-band-owner: overseer-tdfe.2
"""Typed records for foreman convene obligations and their outcomes."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path
from typing import cast

__all__: list[str] = [
    "convene_obligation_path",
    "main",
    "write_convene_discharge",
    "write_convene_escalation",
    "write_convene_obligation",
]

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
    return write_outcome(
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
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    obligation = subparsers.add_parser("obligation")
    add_common_arguments(command=obligation)
    _ = obligation.add_argument("--action-id", required=True)
    _ = obligation.add_argument("--human-valve-category", required=True)
    for command in ("discharge", "escalation"):
        outcome = subparsers.add_parser(command)
        add_common_arguments(command=outcome)
        _ = outcome.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    _ = write_for_args(args=args)
    return 0


def add_common_arguments(*, command: argparse.ArgumentParser) -> None:  # pragma: no cover
    _ = command.add_argument("--repo", required=True)
    _ = command.add_argument("--topic", required=True)
    _ = command.add_argument("--question-fingerprint", required=True)
    _ = command.add_argument("--observed-at-epoch", required=True, type=float)
    _ = command.add_argument("--request-json", required=True)


def write_for_args(*, args: argparse.Namespace) -> Path:  # pragma: no cover
    request = json.loads(str(args.request_json))
    if not isinstance(request, dict):
        msg = "request-json must be a JSON object"
        raise TypeError(msg)
    typed_request = cast("dict[str, object]", request)
    if str(args.command) == "obligation":
        return write_convene_obligation(
            repo=str(args.repo),
            topic=str(args.topic),
            question_fingerprint=str(args.question_fingerprint),
            action_id=str(args.action_id),
            observed_at_epoch=float(args.observed_at_epoch),
            human_valve_category=str(args.human_valve_category),
            request=typed_request,
        )
    writer = (
        write_convene_discharge if str(args.command) == "discharge" else write_convene_escalation
    )
    return writer(
        repo=str(args.repo),
        topic=str(args.topic),
        question_fingerprint=str(args.question_fingerprint),
        reason=str(args.reason),
        observed_at_epoch=float(args.observed_at_epoch),
        request=typed_request,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
