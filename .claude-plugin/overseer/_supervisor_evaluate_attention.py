"""Liveness-attention preparation for the supervisor evaluation cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_attention
import _supervisor_liveness
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = ["EvaluationAttention", "prepare_evaluation_attention"]


@dataclass(frozen=True, kw_only=True)
class EvaluationAttention:
    threshold: int
    attention: _supervisor_attention.LivenessAttention
    generating: bool
    shell_only: bool


def prepare_evaluation_attention(
    *, sup: Supervisor, track: registry.Track, obs: Observation
) -> EvaluationAttention:
    # A per-track override (an int ``ctx_threshold``) wins; otherwise inherit
    # the daemon-wide default (``warn_percent``, set from ``--warn-percent``).
    threshold = _supervisor_liveness.threshold_for(sup=sup, track=track)
    attention = _supervisor_attention.observe_liveness_attention(
        request=_supervisor_attention.ObserveRequest(
            sup=sup,
            istate=obs.istate,
            capture=obs.capture,
            claude_status=obs.claude_status,
            codex_fallback=obs.codex_fallback,
            eff_ctx=obs.eff_ctx,
            threshold=threshold,
            injection_stamp=obs.injection_stamp,
        )
    )
    return EvaluationAttention(
        threshold=threshold,
        attention=attention,
        generating=attention.generating,
        shell_only=attention.shell_only,
    )
