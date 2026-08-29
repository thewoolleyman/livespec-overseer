"""Mapping-row serialization and validation for the durable registry store."""

from __future__ import annotations

from _registry_core import SupervisorSeat, Track
from _registry_resume import normalize_resume_override
from _registry_row_fields import (
    ctx_threshold_from_row,
    idle_nudge_from_row,
    model_profile_from_row,
    opt_str_from_row,
)
from _registry_track_row_parse import RowExtras, track_from_mapping_row
from _registry_track_variants import epic_is_resolved

__all__: list[str] = ["track_to_row", "validated_row"]


def track_to_row(*, track: Track) -> dict[str, object]:
    # A legacy row's `handoff` key is READ without error (it is simply not mapped onto
    # any Track field) and is dropped here, so the first rewrite that touches such a row
    # retires the key. The store never emits it: a track's read-first source is the plan
    # state held on its ledger `epic`, and a second, path-shaped copy of that answer is
    # exactly the drift the locator replaced.
    row: dict[str, object] = {
        "kind": track.kind,
        "topic": track.topic,
        "repo": track.repo,
        "tmux": track.tmux,
        "resume": track.resume,
        # The reader substitutes an in-memory PLACEHOLDER for an ABSENT epic so
        # downstream code has a value to carry. SPECIFICATION/contracts.md calls that
        # a READ-TIME PROJECTION and forbids writing it back: absent and recorded are
        # the only two persisted states, and the projection must not become a third.
        # This is the single chokepoint every track-shaped write serializes through —
        # `append_mapping` appends directly, ahead of the write predicate — so the
        # projection is stripped HERE rather than at the store. A row that already
        # carries a persisted placeholder is treated exactly as one with no recorded
        # epic, so re-serializing it renders the same absent value.
        "epic": track.epic if epic_is_resolved(epic=track.epic) else None,
        "pinned_session_id": track.pinned_session_id,
        "observed_session_identity": track.observed_session_identity,
        "added_at": track.added_at,
    }
    # OMIT ``ctx_threshold`` when there is no per-track override (None): a row
    # WITHOUT the key means "inherit the daemon default"; include it only for an
    # explicit int override.
    if track.ctx_threshold is not None:
        row["ctx_threshold"] = track.ctx_threshold
    # ``idle_nudge`` is omitted on the same terms and for the same reason: a row
    # WITHOUT the key inherits the daemon-wide ``--idle-nudge``, and only an explicit
    # per-track on/off is persisted.
    if track.idle_nudge is not None:
        row["idle_nudge"] = track.idle_nudge
    if track.model_profile is not None:
        row["model_profile"] = track.model_profile
    if isinstance(track, SupervisorSeat):
        row["supervised_topic"] = track.supervised_topic
    _ = normalize_resume_override(row=row)
    return row


def validated_row(*, row: dict[str, object]) -> dict[str, object]:
    topic = row.get("topic")
    repo = row.get("repo")
    track = track_from_mapping_row(
        row=row,
        extras=RowExtras(
            resume=opt_str_from_row(row=row, key="resume"),
            ctx_threshold=ctx_threshold_from_row(row=row),
            idle_nudge=idle_nudge_from_row(row=row),
            pinned_session_id=opt_str_from_row(row=row, key="pinned_session_id"),
            observed_session_identity=opt_str_from_row(row=row, key="observed_session_identity"),
            added_at=opt_str_from_row(row=row, key="added_at"),
            model_profile=model_profile_from_row(
                row=row,
                repo=repo if isinstance(repo, str) else "",
                topic=topic if isinstance(topic, str) else "",
            ),
        ),
    )
    serialized = track_to_row(track=track)
    # `track_to_row` renders an absent epic, an explicit null, and a persisted
    # placeholder identically as null, so only the KEY's presence in the source row
    # distinguishes a row that never carried the key from one that carried it null.
    # Preserve that distinction; everything else about an unrecorded epic is the same.
    if serialized.get("epic") is None and "epic" not in row:
        _ = serialized.pop("epic", None)
    known = set(serialized)
    return {**{key: value for key, value in row.items() if key not in known}, **serialized}
