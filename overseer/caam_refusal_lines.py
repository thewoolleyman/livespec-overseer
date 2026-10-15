"""What a pass SAYS when a refusal governs it, in the operator's words.

A move made under this trigger must be reported as such: the switch line names
the refusal as the reason and states when the refusal was recorded. That second
half is the load-bearing one for an operator reading the log afterwards -- the
usage figures in the table beside it will disagree with the decision, and the
instant the refusal was recorded is what reconciles them.

The lines live beside the trigger rather than with the general rendering
helpers, exactly as the expiring-quota drain's do: a trigger's own vocabulary
belongs to the trigger.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Final, cast

from caam_decision import ProfileUsage, UsageRecord
from caam_refusal_store import RememberedRefusal
from caam_refusals import window_label
from caam_rendering import until

__all__: list[str] = [
    "REFUSAL_TRIGGER",
    "refusal_switch_line",
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


def refusal_switch_line(
    *, active_name: str, target: ProfileUsage, remembered: RememberedRefusal, now: float
) -> str:
    usage = cast(UsageRecord, target.usage)
    now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
    return (
        f"SWITCHED {active_name} -> {target.name} "
        f"(usage-limit refusal on the {window_label(window=remembered.refusal.window)} "
        f"recorded at {_stamp(at=remembered.refusal.recorded_at)}; target has "
        f"{usage.seven_day_remaining:.0f}% week left, resets in "
        f"{until(timestamp=usage.seven_day_resets_at, now=now_dt)})"
    )


def _stamp(*, at: float) -> str:
    """The same instant shape every other surface of this operation stamps."""
    return datetime.fromtimestamp(at, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
