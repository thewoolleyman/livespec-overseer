"""Deterministic Phase B foreman lifecycle actuator."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import jsonio
import streams
from _supervisor_snapshot import DEFAULT_STATUS_PATH
from foreman_act_commands import command_for
from foreman_act_types import (
    ACTION_IDS,
    BLOCKED_SESSION_ANSWER,
    HUMAN_VALVE,
    PROPOSAL_SCHEMA_VERSION,
    QUALIFYING_SESSION_RESUME,
    ActionId,
    ActResult,
)
from foreman_gather_collect import DOCUMENT_SCHEMA_VERSION, compose_document

__all__: list[str] = [
    "ACTION_IDS",
    "BLOCKED_SESSION_ANSWER",
    "HUMAN_VALVE",
    "PROPOSAL_SCHEMA_VERSION",
    "QUALIFYING_SESSION_RESUME",
    "ActResult",
    "ActionId",
    "act",
    "main",
    "run_command",
]

_HUMAN_ACTIONS = (BLOCKED_SESSION_ANSWER, HUMAN_VALVE)


class Gatherer(Protocol):
    def __call__(
        self, *, repo: str | Path, snapshot_path: str | Path = DEFAULT_STATUS_PATH
    ) -> dict[str, object]: ...


class Runner(Protocol):
    def __call__(self, *, argv: list[str]) -> int: ...


def _result(*, action_id: str | None, outcome: str, reason: str, mutated: bool) -> ActResult:
    result: ActResult = {
        "action_id": action_id,
        "mutated": mutated,
        "outcome": outcome,
        "reason": reason,
    }
    return result


def _refused(*, action_id: str | None, reason: str) -> ActResult:
    return _result(action_id=action_id, outcome="refused", reason=reason, mutated=False)


def _acted(*, action_id: str, reason: str) -> ActResult:
    return _result(action_id=action_id, outcome="acted", reason=reason, mutated=True)


def _failed(*, action_id: str, reason: str) -> ActResult:
    return _result(  # pragma: no cover
        action_id=action_id, outcome="failed", reason=reason, mutated=False
    )


def _str_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _int_field(*, payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):  # pragma: no cover
        return None
    return value


def _known_action_id(*, value: object) -> ActionId | None:
    if not isinstance(value, str):  # pragma: no cover
        return None
    return value if value in ACTION_IDS else None


def _proposal_snapshot(*, proposal: dict[str, object]) -> dict[str, object] | None:
    return jsonio.as_object(value=proposal.get("snapshot"))


def _source_snapshot(*, document: dict[str, object]) -> dict[str, object] | None:
    sources = jsonio.as_object(value=document.get("sources"))
    if sources is None:  # pragma: no cover
        return None
    return jsonio.as_object(value=sources.get("snapshot"))


def _current_snapshot(*, document: dict[str, object]) -> dict[str, object] | None:
    return jsonio.as_object(value=document.get("snapshot"))


def _rows(*, snapshot: dict[str, object]) -> list[dict[str, object]] | None:
    raw_rows = jsonio.as_list(value=snapshot.get("rows"))
    if raw_rows is None:  # pragma: no cover
        return None
    rows: list[dict[str, object]] = []
    for raw in raw_rows:
        row = jsonio.as_object(value=raw)
        if row is None:  # pragma: no cover
            return None
        rows.append(row)
    return rows


def _matching_row(
    *, document: dict[str, object], repo: str, topic: str
) -> dict[str, object] | None:
    snapshot = _current_snapshot(document=document)
    if snapshot is None:  # pragma: no cover
        return None
    rows = _rows(snapshot=snapshot)
    if rows is None:  # pragma: no cover
        return None
    for row in rows:
        if row.get("repo") == repo and row.get("topic") == topic:  # pragma: no branch
            return row
    return None  # pragma: no cover


def _revalidate_source(*, document: dict[str, object]) -> str | None:
    if document.get("schema_version") != DOCUMENT_SCHEMA_VERSION:
        return "unsupported_gather_schema"
    source = _source_snapshot(document=document)
    if source is None:  # pragma: no cover
        return "snapshot_not_actable"
    if source.get("status") != "ok" or source.get("mode") != "daemon-snapshot":
        return "snapshot_not_actable"
    if _current_snapshot(document=document) is None:  # pragma: no cover
        return "snapshot_not_actable"
    return None


def _revalidate_identity(*, proposal: dict[str, object], document: dict[str, object]) -> str | None:
    repo = _str_field(payload=proposal, key="repo")
    topic = _str_field(payload=proposal, key="topic")
    expected = _proposal_snapshot(proposal=proposal)
    current = _current_snapshot(document=document)
    reason = None
    if repo is None or topic is None or expected is None or current is None:  # pragma: no cover
        reason = "malformed_proposal"
    elif document.get("repo") != repo:
        reason = "repo_identity_changed"
    elif current.get("daemon_instance_id") != expected.get("daemon_instance_id"):
        reason = "daemon_identity_changed"
    elif current.get("tick_generation") != expected.get("tick_generation"):
        reason = "tick_generation_changed"
    else:
        row = _matching_row(document=document, repo=repo, topic=topic)
        if row is None or row.get("session_identity") != expected.get("session_identity"):
            reason = "session_identity_changed"
    return reason


def _validate_proposal(*, proposal: dict[str, object]) -> tuple[str | None, str | None]:
    raw_action = proposal.get("action_id")
    action_id: str | None = _known_action_id(value=raw_action)
    reason = None
    if proposal.get("schema_version") != PROPOSAL_SCHEMA_VERSION:
        reason = "unsupported_proposal_schema"
    elif action_id is None:
        action_id = raw_action if isinstance(raw_action, str) else None
        reason = "unknown_action"
    elif action_id in _HUMAN_ACTIONS:
        reason = "human_action_report_only"
    else:
        snapshot = _proposal_snapshot(proposal=proposal) or {}
        malformed = (
            _str_field(payload=proposal, key="repo") is None
            or _str_field(payload=proposal, key="topic") is None
            or _int_field(payload=snapshot, key="tick_generation") is None
        )
        if malformed:  # pragma: no cover
            reason = "malformed_proposal"
    return action_id, reason


def act(
    *,
    proposal: dict[str, object],
    run: Runner,
    gather: Gatherer = compose_document,
    snapshot_path: str | Path = DEFAULT_STATUS_PATH,
) -> ActResult:
    action_id, refusal = _validate_proposal(proposal=proposal)
    if refusal is not None:
        result = _refused(action_id=action_id, reason=refusal)
    elif action_id is None or action_id not in ACTION_IDS:  # pragma: no cover
        result = _refused(action_id=action_id, reason="unknown_action")
    else:
        repo = _str_field(payload=proposal, key="repo")
        if repo is None:  # pragma: no cover
            result = _refused(action_id=action_id, reason="malformed_proposal")
        else:
            result = _act_validated(
                action_id=action_id,
                proposal=proposal,
                repo=repo,
                gather=gather,
                run=run,
                snapshot_path=snapshot_path,
            )
    return result


def _act_validated(
    *,
    action_id: ActionId,
    proposal: dict[str, object],
    repo: str,
    gather: Gatherer,
    run: Runner,
    snapshot_path: str | Path,
) -> ActResult:
    document = gather(repo=repo, snapshot_path=snapshot_path)
    refusal = _revalidate_source(document=document) or _revalidate_identity(
        proposal=proposal, document=document
    )
    command = None if refusal is not None else command_for(action_id=action_id, proposal=proposal)
    if refusal is not None:
        result = _refused(action_id=action_id, reason=refusal)
    elif command is None:  # pragma: no cover
        result = _refused(action_id=action_id, reason="classifier_mismatch")
    else:
        code = run(argv=command)
        result = (
            _acted(
                action_id=action_id,
                reason="resumed" if action_id == QUALIFYING_SESSION_RESUME else "started",
            )
            if code == 0
            else _failed(action_id=action_id, reason=f"command_exit_{code}")
        )
    return result


def run_command(*, argv: list[str]) -> int:
    completed = subprocess.run(argv, check=False)  # noqa: S603  # pragma: no cover
    return int(completed.returncode)  # pragma: no cover


def _load_proposal(*, path: Path) -> dict[str, object] | None:
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    return parsed


def main(*, argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="foreman-act")
    _ = parser.add_argument("--proposal", required=True)
    _ = parser.add_argument("--snapshot-path", default=str(DEFAULT_STATUS_PATH))
    args = parser.parse_args(argv)
    proposal = _load_proposal(path=Path(args.proposal))
    result = (
        _refused(action_id=None, reason="malformed_proposal")  # pragma: no cover
        if proposal is None
        else act(
            proposal=proposal,
            run=run_command,
            gather=compose_document,
            snapshot_path=args.snapshot_path,
        )
    )
    streams.write_stdout(text=json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
