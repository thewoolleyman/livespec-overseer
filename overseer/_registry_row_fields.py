"""Typed field decoders for raw mapping-store rows."""

from __future__ import annotations

from typing import cast

import jsonio
from _registry_core import ModelProfile, warn

__all__: list[str] = [
    "ctx_threshold_from_row",
    "model_profile_from_row",
    "opt_str_from_row",
]

_MODEL_PROFILE_KEYS = {"harness", "model", "wrapper"}


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
        or set(profile) != _MODEL_PROFILE_KEYS
        or not isinstance(profile.get("harness"), str)
        or not isinstance(profile.get("model"), str)
        or not isinstance(profile.get("wrapper"), str | type(None))
    ):
        warn(message=f"dropping malformed model_profile for {repo}::{topic}: {value!r}")
        return None
    return cast(
        ModelProfile,
        {
            "harness": profile["harness"],
            "model": profile["model"],
            "wrapper": profile["wrapper"],
        },
    )
