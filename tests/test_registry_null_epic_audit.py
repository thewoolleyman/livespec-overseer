"""Fixture-backed audit coverage for deliberate registry ``epic: null`` rows."""

import json

import registry

__all__: list[str] = []


def test_audit_null_epic_rows_distinguishes_documented_nulls_from_gaps(*, tmp_path):
    assert hasattr(registry, "audit_null_epics")
    store = tmp_path / "map.jsonl"
    store.write_text(
        json.dumps(
            {
                "topic": "documented",
                "repo": "/r",
                "epic": None,
                "epic_null_audit": (
                    "2026-08-23: deliberate null; no taggable epic exists in fixture"
                ),
            }
        )
        + "\n"
        + json.dumps({"topic": "undocumented", "repo": "/r", "epic": None})
        + "\n"
        + json.dumps({"topic": "resolved", "repo": "/r", "epic": "overseer-764a"})
        + "\n",
        encoding="utf-8",
    )

    audit = registry.audit_null_epics(store_path=store)

    assert [(row.topic, row.status) for row in audit] == [
        ("documented", "documented-null"),
        ("undocumented", "undocumented-null"),
    ]
    assert audit[0].evidence == "2026-08-23: deliberate null; no taggable epic exists in fixture"
    assert audit[1].evidence is None
