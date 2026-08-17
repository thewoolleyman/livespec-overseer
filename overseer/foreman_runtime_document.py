"""Structured fingerprints for foreman runtime convergence and re-entry."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import jsonio

__all__: list[str] = ["ForemanDocument", "foreman_document"]


@dataclass(frozen=True, kw_only=True)
class ForemanDocument:
    payload: dict[str, object]
    fingerprint: str
    generation_fingerprint: str
    monitored_entities: tuple[str, ...]


def _stable_text(*, value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _digest(*, value: object) -> str:
    return hashlib.sha256(_stable_text(value=value).encode("utf-8")).hexdigest()


def _snapshot_rows(*, payload: dict[str, object]) -> list[dict[str, object]]:
    snapshot = jsonio.as_object(value=payload.get("snapshot")) or {}
    rows = jsonio.as_list(value=snapshot.get("rows")) or []
    return [row for row in (jsonio.as_object(value=row) for row in rows) if row is not None]


def _attention_items(*, payload: dict[str, object]) -> list[dict[str, object]]:
    attention = jsonio.as_object(value=payload.get("needs_attention")) or {}
    items = jsonio.as_list(value=attention.get("items")) or []
    return [item for item in (jsonio.as_object(value=item) for item in items) if item is not None]


def _fingerprint_rows(*, payload: dict[str, object]) -> list[dict[str, object]]:
    keys = (
        "topic",
        "status",
        "ctx",
        "human_wait",
        "session_identity",
        "progress_now",
        "round_open",
        "picker_open",
        "stall_seconds",
        "supervisor_state_age",
        "proposed_changes_count",
        "pane_content_hash",
    )
    return [{key: row.get(key) for key in keys} for row in _snapshot_rows(payload=payload)]


def _generation_basis(*, payload: dict[str, object]) -> dict[str, object]:
    snapshot = jsonio.as_object(value=payload.get("snapshot")) or {}
    return {
        "snapshot_generation": snapshot.get("tick_generation"),
        "attention_ids": [item.get("id") for item in _attention_items(payload=payload)],
    }


def foreman_document(*, payload: dict[str, object]) -> ForemanDocument:
    rows = _fingerprint_rows(payload=payload)
    items = _attention_items(payload=payload)
    monitored = tuple(
        str(entity)
        for entity in [
            *(row.get("topic") for row in rows),
            *(item.get("id") for item in items),
        ]
        if entity
    )
    return ForemanDocument(
        payload=payload,
        fingerprint=_digest(value={"rows": rows, "attention": items}),
        generation_fingerprint=_digest(value=_generation_basis(payload=payload)),
        monitored_entities=monitored,
    )
