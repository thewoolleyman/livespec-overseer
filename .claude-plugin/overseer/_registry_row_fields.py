"""Typed field decoders for raw mapping-store rows."""

from __future__ import annotations

from typing import cast

import jsonio
from _registry_core import ContextCompaction, ModelProfile, warn

__all__: list[str] = [
    "context_compaction_from_row",
    "context_compaction_row_value",
    "ctx_threshold_from_row",
    "idle_nudge_from_row",
    "model_profile_from_row",
    "opt_str_from_row",
]

_MODEL_PROFILE_REQUIRED_KEYS = {"harness", "model", "wrapper"}
_MODEL_PROFILE_OPTIONAL_KEYS = {"statusline_model"}
# Every member is written on every write, so the decoder can require the exact key set
# and reject anything else as malformed. A partially-keyed record is not a record this
# daemon wrote, and guessing the missing halves is how a latch turns into a wrong one.
_CONTEXT_COMPACTION_KEYS = {
    "session_identity",
    "watermark_ctx",
    "latched_at",
    "from_ctx",
    "to_ctx",
}


def opt_str_from_row(*, row: dict[str, object], key: str) -> str | None:
    value = row.get(key)
    return value if isinstance(value, str) else None


def ctx_threshold_from_row(*, row: dict[str, object]) -> int | None:
    # A per-track override is present ONLY if the row carries an int
    # ``ctx_threshold``; a missing (or non-int) value means "no override" → None,
    # so the daemon-wide default applies. Do NOT default to DEFAULT_CTX_THRESHOLD
    # at read time — that would make a bare row indistinguishable from a row that
    # pinned the current default, defeating the daemon-wide ``--warn-percent``.
    threshold = row.get("ctx_threshold")
    return threshold if isinstance(threshold, int) else None


def idle_nudge_from_row(*, row: dict[str, object]) -> bool | None:
    # The ``ctx_threshold`` rule one field over, and for the same reason: a per-track
    # override is present ONLY if the row carries a bool ``idle_nudge``; a missing (or
    # non-bool) value means "no override" → None, so the daemon-wide ``--idle-nudge``
    # applies. Do NOT default to True at read time — that would make a bare row
    # indistinguishable from one that pinned today's default, which is exactly the
    # distinction ``add --idle-nudge inherit`` exists to restore.
    nudge = row.get("idle_nudge")
    return nudge if isinstance(nudge, bool) else None


def model_profile_from_row(
    *,
    row: dict[str, object],
    repo: str,
    topic: str,
) -> ModelProfile | None:
    value = row.get("model_profile")
    if value is None:
        return None
    profile = jsonio.as_object(value=value)
    if (
        profile is None
        or not _MODEL_PROFILE_REQUIRED_KEYS.issubset(profile)
        or not set(profile).issubset(_MODEL_PROFILE_REQUIRED_KEYS | _MODEL_PROFILE_OPTIONAL_KEYS)
        or not isinstance(profile.get("harness"), str)
        or not isinstance(profile.get("model"), str)
        or not isinstance(profile.get("wrapper"), str | type(None))
        or not isinstance(profile.get("statusline_model"), str | type(None))
    ):
        warn(message=f"dropping malformed model_profile for {repo}::{topic}: {value!r}")
        return None
    model_profile = {
        "harness": profile["harness"],
        "model": profile["model"],
        "wrapper": profile["wrapper"],
    }
    if "statusline_model" in profile:
        model_profile["statusline_model"] = profile["statusline_model"]
    return cast(ModelProfile, model_profile)


def _well_formed_context_compaction(*, record: dict[str, object]) -> bool:
    return (
        set(record) == _CONTEXT_COMPACTION_KEYS
        and isinstance(record["session_identity"], str | type(None))
        and isinstance(record["watermark_ctx"], int | type(None))
        and isinstance(record["latched_at"], int | float | type(None))
        and isinstance(record["from_ctx"], int | type(None))
        and isinstance(record["to_ctx"], int | type(None))
    )


def context_compaction_from_row(
    *,
    row: dict[str, object],
    repo: str,
    topic: str,
) -> ContextCompaction | None:
    """Decode a row's recorded compaction evidence, or None when it carries none.

    Fail-soft in the SAFE direction, which for this field is "no record": a malformed
    value is dropped with a warning rather than half-read, so a corrupt sidecar can
    never manufacture a restart obligation the daemon never observed. The opposite
    direction — losing a real latch — costs one supervision round and is re-detected
    the next time the same session's percentage rises.
    """
    value = row.get("context_compaction")
    if value is None:
        return None
    record = jsonio.as_object(value=value)
    if record is None or not _well_formed_context_compaction(record=record):
        warn(message=f"dropping malformed context_compaction for {repo}::{topic}: {value!r}")
        return None
    latched_at = record["latched_at"]
    return ContextCompaction(
        session_identity=cast("str | None", record["session_identity"]),
        watermark_ctx=cast("int | None", record["watermark_ctx"]),
        latched_at=None if latched_at is None else float(cast("float", latched_at)),
        from_ctx=cast("int | None", record["from_ctx"]),
        to_ctx=cast("int | None", record["to_ctx"]),
    )


def context_compaction_row_value(*, record: ContextCompaction) -> dict[str, object]:
    """Render a compaction record as its persisted row value (every key, always)."""
    return {
        "session_identity": record.session_identity,
        "watermark_ctx": record.watermark_ctx,
        "latched_at": record.latched_at,
        "from_ctx": record.from_ctx,
        "to_ctx": record.to_ctx,
    }
