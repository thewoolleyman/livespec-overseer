"""Work-item relationship indexing for foreman plan roster work state."""

from __future__ import annotations

import re

import jsonio

__all__: list[str] = [
    "plan_dispatch_item_ids",
    "work_item_plan_anchors",
]

EXPLICIT_ANCHOR_METADATA_KEYS = frozenset(
    {
        "epic",
        "epic_anchor",
        "ledger_epic_anchor",
        "plan_anchor",
        "plan_epic_anchor",
    }
)
TEXT_ASSOCIATION_FIELDS = (
    "title",
    "description",
    "notes",
    "acceptance_criteria",
)


def _string_field(*, item: dict[str, object], key: str) -> str | None:
    value = item.get(key)
    return value if isinstance(value, str) else None


def _metadata_anchor(*, item: dict[str, object], anchor_ids: set[str]) -> str | None:
    metadata = jsonio.as_object(value=item.get("metadata"))
    if metadata is None:
        return None
    for key in EXPLICIT_ANCHOR_METADATA_KEYS:
        value = metadata.get(key)
        if isinstance(value, str) and value in anchor_ids:
            return value
    return None


def _text_anchor(*, item: dict[str, object], anchor_ids: set[str]) -> str | None:
    text = "\n".join(
        value
        for field in TEXT_ASSOCIATION_FIELDS
        if (value := _string_field(item=item, key=field)) is not None
    )
    for anchor in sorted(anchor_ids):
        if re.search(rf"\b(?:plan\s+)?epic\s+`?{re.escape(anchor)}`?\b", text):
            return anchor
    return None


def _explicit_anchor(*, item: dict[str, object], anchor_ids: set[str]) -> str | None:
    metadata_anchor = _metadata_anchor(item=item, anchor_ids=anchor_ids)
    if metadata_anchor is not None:
        return metadata_anchor
    return _text_anchor(item=item, anchor_ids=anchor_ids)


def work_item_plan_anchors(*, records: list[dict[str, object]]) -> dict[str, str]:
    anchor_ids = {
        record_id
        for item in records
        if item.get("issue_type") == "epic"
        if isinstance(record_id := item.get("id"), str)
    }
    plan_anchors: dict[str, str] = {}
    for item in records:
        item_id = item.get("id")
        if not isinstance(item_id, str):
            continue
        parent = item.get("parent")
        if isinstance(parent, str) and parent in anchor_ids:
            plan_anchors[item_id] = parent
            continue
        explicit_anchor = _explicit_anchor(item=item, anchor_ids=anchor_ids)
        if explicit_anchor is not None:
            plan_anchors[item_id] = explicit_anchor
    return plan_anchors


def plan_dispatch_item_ids(
    *, anchor: str, dispatch_item_ids: list[str], plan_anchors_by_item_id: dict[str, str]
) -> list[str]:
    item_ids: list[str] = []
    dotted_prefix = f"{anchor}."
    for item_id in dispatch_item_ids:
        mapped_anchor = plan_anchors_by_item_id.get(item_id)
        if mapped_anchor == anchor or (mapped_anchor is None and item_id.startswith(dotted_prefix)):
            item_ids.append(item_id)
    return item_ids
