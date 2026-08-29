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
    "idle_nudge_value",
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


def idle_nudge_value(*, value: object) -> bool | None:
    """The per-track idle-nudge override this ``add`` invocation asks for.

    The `{on,off,inherit}` vocabulary is validated by argparse's own ``choices``, so
    this only has to map it: ``on``/``off`` set the override, and ``inherit`` — like an
    UNSUPPLIED flag — means "no override", which the upsert then CLEARS from the row
    rather than persisting as a null. That is the ``--ctx-threshold inherit`` ergonomic,
    spelled for a tri-state whose two set values are booleans rather than ints.
    """
    if value == "on":
        return True
    if value == "off":
        return False
    return None


def add_update_fields(*, epic: object, ctx_threshold: object, idle_nudge: object) -> frozenset[str]:
    fields = {"added_at", "tmux"}
    if field_supplied(value=epic):
        fields.add("epic")
    if field_supplied(value=ctx_threshold):
        fields.add("ctx_threshold")
    if field_supplied(value=idle_nudge):
        fields.add("idle_nudge")
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
    _ = parser.add_argument(
        "--idle-nudge",
        choices=["on", "off", "inherit"],
        default=UNSET,
        help=(
            "per-track override for the idle-with-context keep-going nudge, winning over "
            "the daemon-wide `overseerd --idle-nudge`, or 'inherit' to clear it"
        ),
    )


def upsert_track(
    *, track: registry.Track, update_fields: frozenset[str] = frozenset({"tmux"})
) -> bool:
    """Create a mapping row or update only the fields this CLI invocation supplied."""
    return registry.upsert_mapping(
        track=track, store_path=None, added_at=iso_now(), update_fields=update_fields
    )
