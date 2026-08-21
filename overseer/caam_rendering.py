"""Pure rendering helpers for caam account rotation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from math import inf
from typing import Protocol

__all__: list[str] = [
    "CURRENT_COL",
    "RenderableProfileUsage",
    "RenderableUsageRecord",
    "SwitchTargetSummary",
    "current_cell",
    "decision_dry_run",
    "decision_forced",
    "decision_hold_allowance",
    "decision_hold_no_candidate",
    "decision_switched",
    "decision_trigger",
    "fmt_duration",
    "render_table",
    "trigger_header",
    "until",
]


class RenderableUsageRecord(Protocol):
    five_hour: float
    seven_day: float
    five_hour_resets_at: str | None
    seven_day_resets_at: str | None
    fable: float | None
    fable_resets_at: str | None


class RenderableProfileUsage(Protocol):
    name: str
    source: str
    usage: RenderableUsageRecord | None


@dataclass(frozen=True, kw_only=True)
class SwitchTargetSummary:
    name: str
    weekly_used: float
    weekly_reset: str | None
    source: str
    now: datetime


CURRENT_COL = 8


def fmt_duration(*, seconds: float) -> str:
    remaining = max(0, int(seconds))
    days, remaining = divmod(remaining, 86400)
    hours, remaining = divmod(remaining, 3600)
    minutes = remaining // 60
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def until(*, timestamp: str | None, now: datetime) -> str:
    reset_at = resets_at(timestamp=timestamp)
    if reset_at == inf:
        return "-"
    return fmt_duration(seconds=reset_at - now.timestamp())


def current_cell(*, is_active: bool) -> str:
    if not is_active:
        return " " * CURRENT_COL
    return "✅" + (" " * (CURRENT_COL - 2))


def render_table(
    *, rows: tuple[RenderableProfileUsage, ...], active_name: str, now: datetime
) -> str:
    lines = [
        "",
        f"{'PROFILE':<13} {'CURRENT':<{CURRENT_COL}} {'5H':>7} {'5H RESET':>13} "
        f"{'WEEK':>9} {'WEEK RESET':>13} {'FABLE':>10} {'FABLE RESET':>13}   SOURCE",
    ]
    lines.extend(row_line(row=row, active_name=active_name, now=now) for row in rows)
    lines.append("")
    return "\n".join(lines) + "\n"


def trigger_header(*, stamp: str) -> str:
    return (
        f"{stamp}  triggers: 5h-remaining < {100 - five_hour_threshold():.0f}% or "
        f"weekly-remaining < {weekly_reserve():.0f}% "
        f"(candidate must gain >={min_headroom_gain():.0f} pts)"
    )


def decision_hold_allowance(
    *, label: str, spent: float, weekly_remaining: float, reserve: float
) -> str:
    return (
        f"hold: {label} is the binding allowance and still has {100 - spent:.0f}% left "
        f"(weekly {weekly_remaining:.0f}%, reserve {reserve:.0f}%)"
    )


def decision_forced(*, threshold: float) -> str:
    return f"forced: ignoring the {threshold:.0f}% trigger, rotating to the best target now"


def decision_trigger(*, label: str, spent: float, weekly_remaining: float, dimension: str) -> str:
    return (
        f"trigger: {label} -- {spent:.0f}% spent, weekly {weekly_remaining:.0f}% left -- "
        f"comparing candidates on {dimension}"
    )


def decision_hold_no_candidate(*, gain_needed: float, dimension: str, active_name: str) -> str:
    return (
        f"hold: no candidate has >={gain_needed:.2f} points more {dimension} headroom "
        f"than {active_name} (all similarly spent, exhausted, or unverifiable)"
    )


def decision_dry_run(*, active_name: str, target: SwitchTargetSummary) -> str:
    return (
        f"DRY-RUN would switch {active_name} -> {target.name} "
        f"({100 - target.weekly_used:.0f}% week left, resets in "
        f"{until(timestamp=target.weekly_reset, now=target.now)} -- soonest, {target.source})"
    )


def decision_switched(
    *, active_name: str, current_five_hour_used: float, target: SwitchTargetSummary
) -> str:
    return (
        f"SWITCHED {active_name} -> {target.name} "
        f"(5h left was {100 - current_five_hour_used:.0f}%; target has "
        f"{100 - target.weekly_used:.0f}% week left resetting in "
        f"{until(timestamp=target.weekly_reset, now=target.now)} -- soonest, {target.source})"
    )


def row_line(*, row: RenderableProfileUsage, active_name: str, now: datetime) -> str:
    if row.usage is None:
        return (
            f"{row.name:<13} {current_cell(is_active=row.name == active_name)} "
            f"{'-':>7} {'-':>13} {'-':>9} {'-':>13} {'-':>10} {'-':>13}   {row.source}"
        )
    fable = f"{100 - row.usage.fable:.0f}%" if row.usage.fable is not None else "-"
    return (
        f"{row.name:<13} {current_cell(is_active=row.name == active_name)} "
        f"{100 - row.usage.five_hour:6.0f}% "
        f"{until(timestamp=row.usage.five_hour_resets_at, now=now):>13} "
        f"{100 - row.usage.seven_day:8.0f}% "
        f"{until(timestamp=row.usage.seven_day_resets_at, now=now):>13} "
        f"{fable:>9} {until(timestamp=row.usage.fable_resets_at, now=now):>13}   "
        f"{row.source}"
    )


def resets_at(*, timestamp: str | None) -> float:
    if not timestamp:
        return inf
    normalized = timestamp.removesuffix("Z") + "+00:00" if timestamp.endswith("Z") else timestamp
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return inf
    return parsed.timestamp()


def five_hour_threshold() -> float:
    return float(os.environ.get("CAAM_ROTATE_FIVE_HOUR_THRESHOLD", "85"))


def weekly_reserve() -> float:
    return float(os.environ.get("CAAM_ROTATE_WEEKLY_RESERVE", "10"))


def min_headroom_gain() -> float:
    return float(os.environ.get("CAAM_ROTATE_MIN_HEADROOM_GAIN", "10"))
