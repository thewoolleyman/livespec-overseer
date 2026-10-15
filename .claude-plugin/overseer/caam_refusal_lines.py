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
from caam_rendering import until, with_reasons

__all__: list[str] = [
    "REFUSAL_TRIGGER",
    "refusal_exclusion_reason",
    "refusal_hold_line",
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


def refusal_hold_line(*, active_name: str, cause: str, reasons: tuple[str, ...] = ()) -> str:
    """The hold line for a refusing account no candidate could replace.

    It states BOTH facts the ratified clause requires -- that the active account
    is refusing requests, and that no account could be selected -- and then hands
    over the cause that emptied the candidate set, since every other rule still
    applied and the operator's next move depends on which one spoke.
    """
    return with_reasons(
        line=(
            f"hold: {active_name} is refusing requests and no account "
            f"could be selected -- {cause}"
        ),
        reasons=reasons,
    )


def refusal_exclusion_reason(
    *, holding: tuple[RememberedRefusal, ...], active_name: str
) -> str | None:
    """Why a candidate the table still lists was never considered, and since when.

    A hold REASON rather than a line of its own, so it composes with every other
    condition that can hold a pass exactly as they compose with each other. It
    is what reconciles the hold with the table printed beside it: the cause names
    the gate that emptied the candidate set, and this names the accounts that
    never reached that gate, each with the instant its refusal was recorded.

    The ACTIVE account is left out. It is not a candidate, and where a refusal
    holds it the hold line already says it is refusing requests.
    """
    excluded = tuple(remembered for remembered in holding if remembered.account != active_name)
    if not excluded:
        return None
    named = ", ".join(
        f"{remembered.account} (refused at {_stamp(at=remembered.refusal.recorded_at)})"
        for remembered in excluded
    )
    return f"a usage-limit refusal excludes {named} from the candidate set"


def _stamp(*, at: float) -> str:
    """The same instant shape every other surface of this operation stamps."""
    return datetime.fromtimestamp(at, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
