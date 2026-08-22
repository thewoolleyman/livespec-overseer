"""Integration tests for operator-visible mapping row health projection."""

from __future__ import annotations

import json
from pathlib import Path

import registry
from _supervisor_mapping_health import apply_mapping_health, explicit_null_added_at_keys
from _supervisor_view import RowView

__all__: list[str] = []


def write_rows(*, store_path: Path, rows: list[dict[str, object]]) -> None:
    store_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def row_view(*, topic: str) -> RowView:
    return RowView(
        repo="/data/projects/homelab",
        topic=topic,
        tmux=topic,
        ctx="n/a",
        status="idle",
        note="",
    )


def test_missing_added_at_key_is_reported_like_explicit_null(*, tmp_path: Path):
    store_path = tmp_path / "mapping.jsonl"
    absent_row = {
        "topic": "16-fleet-provisioning-usb",
        "repo": "/data/projects/homelab",
        "tmux": "16-fleet-provisioning-usb",
        "resume": "resume 16-fleet-provisioning-usb",
        "epic": "homelab-epic",
        "pinned_session_id": "session-123",
        "observed_session_identity": "codex:session-123",
    }
    null_row = {
        "topic": "null-added-at",
        "repo": "/data/projects/homelab",
        "tmux": "null-added-at",
        "resume": "resume null-added-at",
        "epic": "homelab-epic",
        "pinned_session_id": "session-456",
        "observed_session_identity": "codex:session-456",
        "added_at": None,
    }
    unpinned_absent_row = {
        "topic": "unpinned-absent-added-at",
        "repo": "/data/projects/homelab",
        "tmux": "unpinned-absent-added-at",
        "resume": "resume unpinned-absent-added-at",
        "epic": "homelab-epic",
    }
    iso_row = {
        "topic": "iso-added-at",
        "repo": "/data/projects/homelab",
        "tmux": "iso-added-at",
        "resume": "resume iso-added-at",
        "epic": "homelab-epic",
        "pinned_session_id": "session-789",
        "observed_session_identity": "codex:session-789",
        "added_at": "2026-08-22T16:57:00Z",
    }
    write_rows(store_path=store_path, rows=[absent_row, null_row, unpinned_absent_row, iso_row])

    tracks = {track.topic: track for track in registry.read_valid_mapping(store_path=store_path)}
    keys = explicit_null_added_at_keys(store_path=store_path)

    assert tracks["16-fleet-provisioning-usb"].added_at is None
    assert tracks["null-added-at"].added_at is None
    assert tracks["unpinned-absent-added-at"].added_at is None
    assert tracks["iso-added-at"].added_at == "2026-08-22T16:57:00Z"
    assert keys == frozenset(
        {
            (registry.norm(repo="/data/projects/homelab"), "16-fleet-provisioning-usb"),
            (registry.norm(repo="/data/projects/homelab"), "null-added-at"),
            (registry.norm(repo="/data/projects/homelab"), "unpinned-absent-added-at"),
        }
    )
    assert (
        apply_mapping_health(
            track=tracks["16-fleet-provisioning-usb"],
            row=row_view(topic="16-fleet-provisioning-usb"),
            null_added_at_keys=keys,
        ).status
        == "mapping-unusable"
    )
    assert (
        apply_mapping_health(
            track=tracks["iso-added-at"],
            row=row_view(topic="iso-added-at"),
            null_added_at_keys=keys,
        ).status
        == "idle"
    )


def test_mapping_health_keeps_reserved_seat_coverage_and_unassigned_control(*, tmp_path: Path):
    store_path = tmp_path / "mapping.jsonl"
    rows: list[dict[str, object]] = [
        {
            "kind": "foreman",
            "topic": "repo-foreman",
            "repo": "/data/projects/homelab",
            "tmux": "repo-foreman",
            "epic": "homelab-epic",
        },
        {
            "kind": "grooming",
            "topic": "repo-grooming",
            "repo": "/data/projects/homelab",
            "tmux": "repo-grooming",
            "epic": "homelab-epic",
            "added_at": None,
        },
        {
            "kind": "foreman",
            "topic": "repo-foreman-unresolved",
            "repo": "/data/projects/homelab",
            "tmux": "repo-foreman-unresolved",
        },
        {
            "kind": "grooming",
            "topic": "repo-grooming-unresolved",
            "repo": "/data/projects/homelab",
            "tmux": "repo-grooming-unresolved",
        },
    ]
    write_rows(store_path=store_path, rows=rows)

    tracks = {track.topic: track for track in registry.read_valid_mapping(store_path=store_path)}
    keys = explicit_null_added_at_keys(store_path=store_path)
    unassigned = registry.UnassignedPlan.make(repo="/data/projects/homelab", topic="unassigned")

    assert (
        apply_mapping_health(
            track=tracks["repo-foreman"],
            row=row_view(topic="repo-foreman"),
            null_added_at_keys=keys,
        ).note
        == "mapping row missing added_at; no-round ready cannot certify"
    )
    assert (
        apply_mapping_health(
            track=tracks["repo-grooming"],
            row=row_view(topic="repo-grooming"),
            null_added_at_keys=keys,
        ).note
        == "mapping row missing added_at; no-round ready cannot certify"
    )
    assert (
        apply_mapping_health(
            track=tracks["repo-foreman-unresolved"],
            row=row_view(topic="repo-foreman-unresolved"),
            null_added_at_keys=keys,
        ).note
        == "mapping row missing added_at; no-round ready cannot certify"
    )
    assert (
        apply_mapping_health(
            track=tracks["repo-grooming-unresolved"],
            row=row_view(topic="repo-grooming-unresolved"),
            null_added_at_keys=keys,
        ).note
        == "mapping row missing added_at; no-round ready cannot certify"
    )
    assert (
        apply_mapping_health(
            track=unassigned,
            row=row_view(topic="unassigned"),
            null_added_at_keys=keys,
        ).status
        == "idle"
    )
