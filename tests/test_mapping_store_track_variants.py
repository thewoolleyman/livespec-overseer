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


def test_raw_row_write_surface_is_not_public_registry_api():
    assert not hasattr(registry, "write_rows")
    assert not hasattr(registry, "read_rows")
    assert "_track_to_row" not in registry.__all__
