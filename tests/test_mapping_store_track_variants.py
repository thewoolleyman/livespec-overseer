"""Typed track variants at the mapping-store boundary."""

import inspect
import json

import pytest
import registry

__all__: list[str] = []


def test_mapping_writes_and_reads_the_variant_discriminator(*, tmp_path):
    store = tmp_path / "map.jsonl"
    registry.append_mapping(
        track=registry.PlanTrack(
            topic="alpha",
            repo="/repo",
            tmux="alpha",
            epic="overseer-alpha",
        ),
        store_path=store,
    )

    row = json.loads(store.read_text(encoding="utf-8"))
    assert row["kind"] == "plan"
    [track] = registry.read_valid_mapping(store_path=store)
    assert type(track).__name__ == "PlanTrack"
    assert track.kind == "plan"
    assert track.epic == "overseer-alpha"


def test_the_four_track_variants_are_distinct_records():
    variants = [
        registry.UnassignedPlan.make(repo="/repo", topic="alpha"),
        registry.PlanTrack(topic="alpha", repo="/repo", tmux="alpha", epic="overseer-alpha"),
        registry.SupervisorSeat(
            topic="alpha-supervisor",
            repo="/repo",
            tmux="alpha-supervisor",
            epic="overseer-alpha",
            supervised_topic="alpha",
        ),
        registry.ForemanSeat(
            topic="repo-foreman",
            repo="/repo",
            tmux="repo-foreman",
            epic="overseer-foreman",
        ),
    ]

    assert [type(variant).__name__ for variant in variants] == [
        "UnassignedPlan",
        "PlanTrack",
        "SupervisorSeat",
        "ForemanSeat",
    ]
    assert [variant.kind for variant in variants] == [
        "unassigned_plan",
        "plan",
        "supervisor",
        "foreman",
    ]
    assert "tmux" not in inspect.signature(registry.UnassignedPlan).parameters
    assert "epic" not in inspect.signature(registry.UnassignedPlan).parameters
    assert (
        inspect.signature(registry.PlanTrack).parameters["epic"].default is inspect.Parameter.empty
    )


def test_foreman_seat_without_epic_fails_at_construction():
    with pytest.raises(ValueError, match="foreman.*epic"):
        registry.ForemanSeat(topic="repo-foreman", repo="/repo", tmux="repo-foreman")


def test_legacy_foreman_row_with_null_or_absent_epic_loads_with_unresolved_sentinel(*, tmp_path):
    store = tmp_path / "map.jsonl"
    store.write_text(
        json.dumps(
            {
                "kind": "foreman",
                "topic": "repo-foreman",
                "repo": "/repo",
                "tmux": "repo-foreman",
                "epic": None,
            }
        )
        + "\n"
        + json.dumps(
            {
                "kind": "foreman",
                "topic": "other-foreman",
                "repo": "/repo",
                "tmux": "other-foreman",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    entries = registry.read_mapping(store_path=store)
    tracks = registry.read_valid_mapping(store_path=store)

    assert [type(entry).__name__ for entry in entries] == ["MappingValid", "MappingValid"]
    assert [(track.topic, track.epic) for track in tracks] == [
        ("repo-foreman", registry.unresolved_plan_epic(topic="repo-foreman")),
        ("other-foreman", registry.unresolved_plan_epic(topic="other-foreman")),
    ]


def test_foreman_row_with_non_string_epic_stays_invalid(*, tmp_path):
    store = tmp_path / "map.jsonl"
    raw = json.dumps(
        {
            "kind": "foreman",
            "topic": "repo-foreman",
            "repo": "/repo",
            "tmux": "repo-foreman",
            "epic": 42,
        }
    )
    store.write_text(raw + "\n", encoding="utf-8")

    [entry] = registry.read_mapping(store_path=store)

    assert type(entry).__name__ == "MappingInvalid"
    assert entry.reason == "missing_epic"
    assert entry.raw_line == raw


def test_raw_row_write_surface_is_not_public_registry_api():
    assert not hasattr(registry, "write_rows")
    assert not hasattr(registry, "read_rows")
    assert "_track_to_row" not in registry.__all__
