"""An account's CAPACITY CLASS: the four classes, the mapping, and the table cell.

Two accounts at the same percentage can hold very different absolute headroom --
measured 2026-10-13 on host hp, a $20 account fell about 70 short-window points
in one 30-minute pass where a $200 account fell about 10 -- so a percentage read
alone does not say how much an account can actually carry. The class is the
provider-agnostic answer to "how much", and the provider's own plan name travels
with it as DETAIL so an operator can tell which plan produced the class.

THE CLASS IS PROVIDER-AGNOSTIC AND THE PLAN NAME IS NOT, which is why they are
separate fields rather than one string. A provider added to rotation later
supplies its own source and its own mapping onto these same three named classes;
nothing downstream of here learns a second vocabulary.

This module is deliberately PURE: it knows the mapping and how a class renders,
and nothing about how a plan is read. The read lives in `caam_capacity_source`,
which imports this. Keeping the direction one-way is what lets `caam_rendering`
import the cell without reaching the provider transport at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

__all__: list[str] = [
    "ANTHROPIC_CAPACITY_CLASSES",
    "LARGE",
    "MEDIUM",
    "SMALL",
    "UNKNOWN",
    "AccountCapacity",
    "CapacitySource",
    "capacity_cell",
    "capacity_of",
]

SMALL: Final = "small"
MEDIUM: Final = "medium"
LARGE: Final = "large"
UNKNOWN: Final = "unknown"

# contracts.md section "The account-rotation operation", paragraph **Capacity
# class source**. Anything absent from this table maps to `unknown` -- stated as
# the mapping's DEFAULT rather than as a fourth row, so a plan nobody has
# measured can never acquire a class by resembling one that has been.
ANTHROPIC_CAPACITY_CLASSES: Final[dict[str, str]] = {
    "default_claude_ai": SMALL,
    "default_claude_max_5x": MEDIUM,
    "default_claude_max_20x": LARGE,
}


@dataclass(frozen=True, kw_only=True)
class AccountCapacity:
    """One account's observed capacity class, with the plan name it was read from.

    `plan_name` is None ONLY where no plan name was read at all -- a failed or
    unparseable read, or a locally-expired token that was skipped rather than
    sent. An UNMAPPED plan name is a different fact and keeps its value: it
    reports `unknown` beside the provider's own word for the plan, so an
    operator can tell "this plan has no mapping yet" from "nothing was read".
    """

    capacity_class: str
    plan_name: str | None


class CapacitySource(Protocol):
    """A provider's live plan read: (plan name, None) or (None, reason).

    Takes the CREDENTIAL rather than an account name, because the specification
    requires the read to be made with the same credential the pass uses for that
    account's usage -- so the caller resolving that credential once is what keeps
    the two reads talking about the same account.
    """

    def __call__(
        self,
        *,
        creds_path: Path,
        now: float | None = None,
    ) -> tuple[str | None, str | None]: ...


def capacity_of(*, tier: str | None) -> AccountCapacity:
    """The class a provider plan name maps to, with that name kept as detail.

    There is no stored or guessed fallback on this path by construction: the
    only input is what this pass read, so a pass that read nothing reports
    `unknown` rather than the class an earlier pass or a login-time credential
    field would have supplied.
    """

    if tier is None:
        return AccountCapacity(capacity_class=UNKNOWN, plan_name=None)
    return AccountCapacity(
        capacity_class=ANTHROPIC_CAPACITY_CLASSES.get(tier, UNKNOWN),
        plan_name=tier,
    )


def capacity_cell(*, capacity: AccountCapacity | None) -> str:
    """The one CAPACITY cell an account row shows.

    A row carrying NO observation at all reads `unknown` exactly as an
    unreadable one does, because from the operator's side they are the same
    fact: this pass cannot say what plan the account is on.
    """

    if capacity is None:
        return UNKNOWN
    if capacity.plan_name is None:
        return capacity.capacity_class
    return f"{capacity.capacity_class} ({capacity.plan_name})"
