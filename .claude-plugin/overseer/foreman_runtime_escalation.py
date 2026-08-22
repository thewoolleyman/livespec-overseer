"""Foreman runtime writes for non-blocking human-decision escalation."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from _supervisor_foreman_escalation import escalation_path
from foreman_runtime_identity import canonical_session_name
from foreman_runtime_state import atomic_json

__all__: list[str] = ["foreman_session_identity", "record_blocking_prompt_escalation"]

_BLOCKING_PROMPT_REASON = (
    "foreman tick ended with a blocking prompt; the decision must stay on "
    "the non-blocking attention surface so the loop cadence can continue"
)


def record_blocking_prompt_escalation(*, repo: Path, session_identity: str | None = None) -> None:
    topic = canonical_session_name(repo=repo)
    payload: dict[str, object] = {"reason": _BLOCKING_PROMPT_REASON}
    if session_identity is not None:
        payload["session_identity"] = session_identity
    atomic_json(
        path=escalation_path(repo=str(repo), topic=topic),
        payload=payload,
    )


def foreman_session_identity(*, payload: dict[str, object], repo: Path) -> str | None:
    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, Mapping):
        return None
    rows = cast("Mapping[str, object]", snapshot).get("rows")
    if not isinstance(rows, list):
        return None
    typed_rows = cast("list[object]", rows)
    topic = canonical_session_name(repo=repo)
    for row in typed_rows:
        if not isinstance(row, Mapping):
            continue
        typed_row = cast("Mapping[str, object]", row)
        if typed_row.get("topic") != topic:
            continue
        identity = typed_row.get("session_identity")
        if isinstance(identity, str) and identity.strip():
            return identity.strip()
    return None
