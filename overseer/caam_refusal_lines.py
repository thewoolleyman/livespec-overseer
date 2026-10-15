"""What a pass SAYS when a refusal governs it, in the operator's words.

The lines live beside the trigger rather than with the general rendering
helpers, exactly as the expiring-quota drain's do: a trigger's own vocabulary
belongs to the trigger.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Final

from caam_refusal_store import RememberedRefusal
from caam_refusals import window_label

__all__: list[str] = [
    "REFUSAL_TRIGGER",
    "refusal_trigger_line",
]

REFUSAL_TRIGGER: Final = "usage-limit-refusal"


def refusal_trigger_line(*, remembered: RememberedRefusal) -> str:
    return (
        f"trigger: usage-limit refusal -- {remembered.account} refused on its "
        f"{window_label(window=remembered.refusal.window)} at "
        f"{_stamp(at=remembered.refusal.recorded_at)} -- "
        f"comparing candidates on {remembered.refusal.window}"
    )


def _stamp(*, at: float) -> str:
    """The same instant shape every other surface of this operation stamps."""
    return datetime.fromtimestamp(at, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
