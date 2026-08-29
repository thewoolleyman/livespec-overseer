"""Field mutation rules for mapping-store upserts."""

from __future__ import annotations

from _registry_track_variants import TrackRecord

__all__: list[str] = ["apply_upsert_update_fields"]


def apply_upsert_update_fields(
    *,
    row: dict[str, object],
    new_row: dict[str, object],
    track: TrackRecord,
    update_fields: frozenset[str],
) -> bool:
    changed = False
    for field, value in (("topic", track.topic), ("repo", track.repo)):
        if row.get(field) != value:
            row[field] = value
            changed = True
    for field in update_fields:
        # The two per-track OVERRIDE fields are cleared, not nulled: `inherit` removes
        # the key so the row goes back to inheriting the daemon-wide default, which a
        # persisted `null` would not do (a reader cannot tell it from a pinned value).
        if (field == "ctx_threshold" and track.ctx_threshold is None) or (
            field == "idle_nudge" and track.idle_nudge is None
        ):
            if field in row:
                del row[field]
                changed = True
            continue
        if field == "added_at" and isinstance(row.get(field), str):
            continue
        value = new_row.get(field)
        if row.get(field) != value:
            row[field] = value
            changed = True
    return changed
