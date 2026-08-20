"""Tests for typed invalid mapping-store object rows."""

import json
import os

import _registry_mapping_read
import _registry_rows_io
import registry

__all__: list[str] = []


def test_read_mapping_parses_store_once_when_no_normalization_is_needed(*, tmp_path, monkeypatch):
    store = tmp_path / "map.jsonl"
    store.write_text(
        json.dumps({"topic": "a", "repo": "/r"})
        + "\n"
        + json.dumps({"topic": "b", "repo": "/r"})
        + "\n",
        encoding="utf-8",
    )
    original_read_row_records = _registry_rows_io.read_row_records
    parse_calls: list[str | os.PathLike[str] | None] = []

    def counting_read_row_records(
        *,
        store_path: str | os.PathLike[str] | None = None,
    ) -> list[_registry_rows_io.RawMappingRow]:
        parse_calls.append(store_path)
        return original_read_row_records(store_path=store_path)

    monkeypatch.setattr(_registry_rows_io, "read_row_records", counting_read_row_records)
    monkeypatch.setattr(_registry_mapping_read, "read_row_records", counting_read_row_records)

    assert [
        entry.track.topic
        for entry in registry.read_mapping(store_path=store)
        if type(entry).__name__ == "MappingValid"
    ] == ["a", "b"]
    assert parse_calls == [store]


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


def test_read_mapping_reports_constructor_rejected_rows(*, tmp_path):
    store = tmp_path / "map.jsonl"
    bad = json.dumps(
        {
            "kind": "supervisor",
            "topic": "plain",
            "repo": "/r",
            "tmux": "plain",
            "epic": "overseer-plain",
        }
    )
    store.write_text(bad + "\n", encoding="utf-8")

    [entry] = registry.read_mapping(store_path=store)

    assert type(entry).__name__ == "MappingInvalid"
    assert entry.reason == "missing_supervised_topic"
    assert entry.raw_line == bad
