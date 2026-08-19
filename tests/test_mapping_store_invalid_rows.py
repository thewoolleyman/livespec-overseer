"""Tests for typed invalid mapping-store object rows."""

import json

import registry

__all__: list[str] = []


def test_read_mapping_reports_invalid_object_rows_without_dropping_valid_neighbors(*, tmp_path):
    store = tmp_path / "map.jsonl"
    good_a = json.dumps({"topic": "a", "repo": "/r"})
    bad = json.dumps({"repo": "/r", "tmux": "broken"})
    good_b = json.dumps({"topic": "b", "repo": "/r"})
    store.write_text(good_a + "\n" + bad + "\n" + good_b + "\n", encoding="utf-8")

    entries = registry.read_mapping(store_path=store)

    assert [type(entry).__name__ for entry in entries] == [
        "MappingValid",
        "MappingInvalid",
        "MappingValid",
    ]
    assert [entry.track.topic for entry in entries if type(entry).__name__ == "MappingValid"] == [
        "a",
        "b",
    ]
    invalid = entries[1]
    assert invalid.reason == "missing_topic_or_repo"
    assert invalid.raw_line == bad
    assert invalid.lineno == 2
