"""Relationship indexing coverage for foreman roster work items."""

from __future__ import annotations

import foreman_plan_roster_work_items

__all__: list[str] = []


def test_work_item_plan_anchors_reads_parent_metadata_and_text_associations():
    assert foreman_plan_roster_work_items.work_item_plan_anchors(
        records=[
            {"id": "anchor-a", "issue_type": "epic"},
            {"id": "anchor-b", "issue_type": "epic"},
            {"id": "anchor-c", "issue_type": "epic"},
            {"id": "parented", "issue_type": "bug", "parent": "anchor-a"},
            {
                "id": "metadata",
                "issue_type": "bug",
                "metadata": {"plan_epic_anchor": "anchor-b"},
            },
            {
                "id": "text",
                "issue_type": "bug",
                "description": "Thread membership: plan epic `anchor-c`.",
            },
            {"id": "ignored-parent", "issue_type": "bug", "parent": "missing"},
            {"id": "ignored-metadata", "issue_type": "bug", "metadata": []},
            {"id": "ignored-text", "issue_type": "bug", "description": "epic missing"},
            {"id": 7, "issue_type": "bug", "parent": "anchor-a"},
        ]
    ) == {
        "parented": "anchor-a",
        "metadata": "anchor-b",
        "text": "anchor-c",
    }


def test_plan_dispatch_item_ids_uses_only_recorded_mappings():
    assert foreman_plan_roster_work_items.plan_dispatch_item_ids(
        anchor="anchor-a",
        dispatch_item_ids=[
            "mapped",
            "anchor-a.unmapped",
            "blocked-by-other-map",
            "other.legacy",
        ],
        plan_anchors_by_item_id={
            "mapped": "anchor-a",
            "blocked-by-other-map": "anchor-b",
        },
    ) == ["mapped"]
