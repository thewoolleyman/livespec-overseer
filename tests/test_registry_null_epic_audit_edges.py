"""Edge coverage for null-epic registry audit fixtures."""

import json

import registry

__all__: list[str] = []


def test_audit_null_epics_skips_rows_without_usable_identity(*, tmp_path):
    store = tmp_path / "map.jsonl"
    store.write_text(
        json.dumps({"repo": "/r", "epic": None})
        + "\n"
        + json.dumps({"topic": "missing-repo", "epic": None})
        + "\n",
        encoding="utf-8",
    )

    assert registry.audit_null_epics(store_path=store) == []
