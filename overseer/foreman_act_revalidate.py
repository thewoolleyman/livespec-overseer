"""Proposal and snapshot revalidation for the deterministic foreman actuator."""

from __future__ import annotations

from typing import Final

import jsonio
from foreman_act_types import (
    ACTION_IDS,
    PROPOSAL_SCHEMA_VERSION,
    WORK_ITEM_SESSION_ACTIONS,
    ActionId,
)
from foreman_gather_collect import DOCUMENT_SCHEMA_VERSION

__all__: list[str] = [
    "int_field",
    "revalidate_identity",
    "revalidate_source",
    "str_field",
    "validate_proposal",
]

_FREEFORM_COMMAND_FIELDS: Final[tuple[str, ...]] = ("argv", "command", "shell")


def str_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) else None


def int_field(*, payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):  # pragma: no cover
        return None
    return value


def validate_proposal(*, proposal: dict[str, object]) -> tuple[str | None, str | None]:
    raw_action = proposal.get("action_id")
    action_id: str | None = _known_action_id(value=raw_action)
    reason = None
    if any(field in proposal for field in _FREEFORM_COMMAND_FIELDS):
        reason = "free_form_command"
    elif proposal.get("schema_version") != PROPOSAL_SCHEMA_VERSION:
        reason = "unsupported_proposal_schema"
    elif action_id is None:
        action_id = raw_action if isinstance(raw_action, str) else None
        reason = "unknown_action"
    else:
        snapshot = _proposal_snapshot(proposal=proposal) or {}
        row_required = action_id not in WORK_ITEM_SESSION_ACTIONS
        malformed = (
            str_field(payload=proposal, key="repo") is None
            or str_field(payload=proposal, key="topic") is None
            or int_field(payload=snapshot, key="tick_generation") is None
            or (row_required and str_field(payload=proposal, key="session_name") is None)
        )
        if malformed:  # pragma: no cover
            reason = "malformed_proposal"
    return action_id, reason


def revalidate_source(*, document: dict[str, object]) -> str | None:
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


def revalidate_identity(*, proposal: dict[str, object], document: dict[str, object]) -> str | None:
    repo = str_field(payload=proposal, key="repo")
    topic = str_field(payload=proposal, key="topic")
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
