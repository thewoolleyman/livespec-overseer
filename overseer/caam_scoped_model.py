"""Scoped-model pin detection and shared model constants for caam enforcement.

Relocated out of the retired ``caam_foreman_override`` module (plan
overseer-54k2za.53) when the caam operation was decoupled from the foreman and
grooming seats, both of which have since been retired whole. This module holds
only the seat-independent surface: the scoped-model constants and the "an
operator pin names the scoped model" detection, whose per-session-pin and
observed-running arms arm the scoped-model rotation trigger (overseer-dyt6). The
foreman-suffix derivation and the global ``--foreman-model`` operator pin that
used to live here are gone.
"""

from __future__ import annotations

from typing import Final

__all__: list[str] = [
    "OBSERVED_MODELS_KEY",
    "SCOPED_MODEL",
    "WANTED_MODELS",
    "scoped_model_pinned",
]

# Enforcement records every pane's KNOWN observed model here each pass (it runs
# before the rotation decision in the same pass), so the decision can see that a
# tracked session is currently running the scoped model. Per ratified spec that
# observation arms the scoped-model trigger exactly as a per-session pin does.
OBSERVED_MODELS_KEY: Final = "observed_models"

WANTED_MODELS: Final = frozenset(("fable", "opus"))
# The scoped-model allowance the specification names generically is this
# product's Fable weekly allowance (see `caam_usage`, which identifies it as the
# `weekly_scoped` limit on the model displayed as Fable). Pinning it is what puts
# the scoped-model selection clause in effect; pinning the general model does not.
SCOPED_MODEL: Final = "fable"
# The per-session enforced-model pins live under these state keys. They mirror
# caam_session_models.STATE_KEY / _LEGACY_STATE_KEY, duplicated here rather than
# imported because caam_session_models imports THIS module (the dependency runs
# one way only); the legacy key is read for state not yet migrated by an apply.
_SESSION_MODEL_KEYS: Final = ("session_models", "session-models")


def scoped_model_pinned(*, state: dict[str, object]) -> bool:
    """Whether an operator pin -- per-session -- names the scoped model.

    "An operator pin names the scoped model" is armed when EITHER any
    per-session pin (a `session_models` entry) names the scoped model OR any
    tracked session is currently observed running it, whether it arrived there
    by pin, by an operator's choice, or as the default -- enforcement records
    those observations under OBSERVED_MODELS_KEY. Both arming routes arm the
    scoped-model selection clause identically; the precedence is unchanged (a
    protection floor still outranks the pin, which waives only the
    relative-headroom margin, and anti-oscillation is preserved). An unreadable
    model is never recorded, so it arms nothing.
    """
    for key in _SESSION_MODEL_KEYS:
        pins = state.get(key)
        if isinstance(pins, dict) and SCOPED_MODEL in pins.values():
            return True
    observed = state.get(OBSERVED_MODELS_KEY)
    return isinstance(observed, dict) and SCOPED_MODEL in observed.values()
