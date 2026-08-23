"""Launch-profile seed for reserved runtime seats."""

from __future__ import annotations

import os

from _supervisor_launch_profile import DEFAULT_START_MODEL

__all__: list[str] = ["registration_model_profile"]


def registration_model_profile() -> dict[str, str | None]:
    """Return the initial profile a reserved seat records at row birth.

    Reserved foreman/grooming seats self-register before the daemon's wrap-up-time
    live-process refresh can run, so registration owns the non-null initial profile.
    The refresh path remains the owner of later live re-reads and statusline baselines.
    """
    return {
        "harness": "claude",
        "model": os.environ.get("ANTHROPIC_MODEL", DEFAULT_START_MODEL),
        "wrapper": os.environ.get("LIVESPEC_LOCAL_LLM_WRAPPER"),
    }
