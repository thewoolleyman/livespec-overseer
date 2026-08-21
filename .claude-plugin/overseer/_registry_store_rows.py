"""Mapping-row serialization and validation for the durable registry store."""

from __future__ import annotations

from _registry_core import SupervisorSeat, Track
from _registry_resume import normalize_resume_override
from _registry_row_fields import ctx_threshold_from_row, model_profile_from_row, opt_str_from_row
from _registry_track_row_parse import RowExtras, track_from_mapping_row

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
        "epic": track.epic,
        "pinned_session_id": track.pinned_session_id,
        "observed_session_identity": track.observed_session_identity,
        "added_at": track.added_at,
    }
    # OMIT ``ctx_threshold`` when there is no per-track override (None): a row
    # WITHOUT the key means "inherit the daemon default"; include it only for an
    # explicit int override.
    if track.ctx_threshold is not None:
        row["ctx_threshold"] = track.ctx_threshold
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
    known = set(serialized)
    return {**{key: value for key, value in row.items() if key not in known}, **serialized}
