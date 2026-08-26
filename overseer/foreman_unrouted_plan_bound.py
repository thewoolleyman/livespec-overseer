"""Resolve the maintainer-owned UNROUTED-PLAN BOUND and the past-bound verdict.

The bound is repository configuration and never a value this module chooses for
itself: there is no default here, and none may be added. Where the repository
configures no bound, or configures one this module cannot read as a tick count,
the determination resolves UNDETERMINED and carries the reason, because an
unavailable input is not evidence that a plan is being worked. The verdict is
therefore three-valued — never the boolean a determined, not-past-bound plan
carries — so a caller cannot mistake an absent input for an absent condition.

The count this reads is the per-plan consecutive-unactioned count recorded by
`foreman_plan_roster_state`, which resets a plan's count on any tick that
actions it. Both halves are needed: a bound with no count, and a count with no
bound, are each an unavailable input.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import jsonio
from foreman_gather_sources import parse_repo_config

__all__: list[str] = [
    "BOUND_NOT_A_TICK_COUNT",
    "BOUND_UNCONFIGURED",
    "CONFIGURED",
    "CONFIG_KEY",
    "CONFIG_SECTION",
    "COUNT_UNAVAILABLE",
    "UNDETERMINED",
    "PastBoundVerdict",
    "UnroutedPlanBound",
    "annotate_unactioned_past_bound",
    "resolve_unrouted_plan_bound",
    "unactioned_past_bound",
]

CONFIG_KEY: Final[str] = "unrouted_plan_bound"
CONFIG_SECTION: Final[str] = "livespec-overseer"
CONFIGURED: Final[str] = "configured"
UNDETERMINED: Final[str] = "undetermined"
BOUND_UNCONFIGURED: Final[str] = "unrouted_plan_bound_unconfigured"
BOUND_NOT_A_TICK_COUNT: Final[str] = "unrouted_plan_bound_not_a_positive_tick_count"
COUNT_UNAVAILABLE: Final[str] = "consecutive_unactioned_count_unavailable"
_ROW_COUNT_KEY: Final[str] = "consecutive_unactioned_ticks"
_ROW_VERDICT_KEY: Final[str] = "unactioned_past_bound"
_ROW_REASON_KEY: Final[str] = "unactioned_past_bound_undetermined_reason"
_UNCONFIGURED_SOURCE: Final[str] = "unconfigured"


@dataclass(frozen=True, kw_only=True)
class UnroutedPlanBound:
    """A bound read from repository configuration, or why it could not be."""

    bound: int | None
    configured: object
    undetermined_reason: str | None
    source: str

    def document(self) -> dict[str, object]:
        return {
            "bound": self.bound,
            "configured": self.configured,
            "resolution": UNDETERMINED if self.bound is None else CONFIGURED,
            "undetermined_reason": self.undetermined_reason,
            "source": self.source,
        }


@dataclass(frozen=True, kw_only=True)
class PastBoundVerdict:
    """Whether a plan is unactioned past its bound, or why that is undetermined."""

    verdict: bool | str
    undetermined_reason: str | None


def _configured_value(*, config: dict[str, object] | None) -> object:
    if config is None:
        return None
    section = jsonio.as_object(value=config.get(CONFIG_SECTION))
    return None if section is None else section.get(CONFIG_KEY)


def _reportable(*, value: object) -> object:
    return value if isinstance(value, bool | int | float | str) else None


def resolve_unrouted_plan_bound(*, repo: Path) -> UnroutedPlanBound:
    configured = _configured_value(config=parse_repo_config(repo=repo))
    if configured is None:
        return UnroutedPlanBound(
            bound=None,
            configured=None,
            undetermined_reason=BOUND_UNCONFIGURED,
            source=_UNCONFIGURED_SOURCE,
        )
    source = str(repo / ".livespec.jsonc")
    if isinstance(configured, bool) or not isinstance(configured, int) or configured < 1:
        return UnroutedPlanBound(
            bound=None,
            configured=_reportable(value=configured),
            undetermined_reason=BOUND_NOT_A_TICK_COUNT,
            source=source,
        )
    return UnroutedPlanBound(
        bound=configured,
        configured=configured,
        undetermined_reason=None,
        source=source,
    )


def unactioned_past_bound(*, count: int | None, bound: UnroutedPlanBound) -> PastBoundVerdict:
    if bound.bound is None:
        return PastBoundVerdict(
            verdict=UNDETERMINED,
            undetermined_reason=bound.undetermined_reason,
        )
    if count is None:
        return PastBoundVerdict(verdict=UNDETERMINED, undetermined_reason=COUNT_UNAVAILABLE)
    return PastBoundVerdict(verdict=count >= bound.bound, undetermined_reason=None)


def annotate_unactioned_past_bound(
    *, repo: Path, rows: list[dict[str, object]]
) -> dict[str, object]:
    """Annotate each roster row with its verdict; return the bound's document."""
    bound = resolve_unrouted_plan_bound(repo=repo)
    for row in rows:
        recorded = row.get(_ROW_COUNT_KEY)
        resolved = unactioned_past_bound(
            count=recorded if isinstance(recorded, int) else None,
            bound=bound,
        )
        row[_ROW_VERDICT_KEY] = resolved.verdict
        row[_ROW_REASON_KEY] = resolved.undetermined_reason
    return bound.document()
