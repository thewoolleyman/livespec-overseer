"""Operator CLI mapping-update provenance helpers."""

from __future__ import annotations

import argparse

import registry
from _supervisor_config import iso_now

__all__: list[str] = [
    "UNSET",
    "add_mapping_write_args",
    "add_update_fields",
    "ctx_threshold_argument",
    "ctx_threshold_value",
    "field_supplied",
    "optional_str_value",
    "upsert_track",
]

UNSET: object = object()


def field_supplied(*, value: object) -> bool:
    return value is not UNSET


def optional_str_value(*, value: object) -> str | None:
    return value if isinstance(value, str) else None


def ctx_threshold_argument(*, value: str) -> int | None:
    if value == "inherit":
        return None
    return int(value)


def ctx_threshold_value(*, value: object) -> int | None:
    return value if isinstance(value, int) else None


def add_update_fields(*, epic: object, ctx_threshold: object) -> frozenset[str]:
    fields = {"added_at", "tmux"}
    if field_supplied(value=epic):
        fields.add("epic")
    if field_supplied(value=ctx_threshold):
        fields.add("ctx_threshold")
    return frozenset(fields)


def add_mapping_write_args(*, parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument(
        "--epic",
        default=UNSET,
        help="ledger epic id for the plan state",
    )
    _ = parser.add_argument(
        "--ctx-threshold",
        type=lambda value: ctx_threshold_argument(value=value),
        default=UNSET,
        metavar="N",
        help="per-track remaining-context %% threshold override, or 'inherit' to clear",
    )


def upsert_track(
    *, track: registry.Track, update_fields: frozenset[str] = frozenset({"tmux"})
) -> bool:
    """Create a mapping row or update only the fields this CLI invocation supplied."""
    return registry.upsert_mapping(
        track=track, store_path=None, added_at=iso_now(), update_fields=update_fields
    )
