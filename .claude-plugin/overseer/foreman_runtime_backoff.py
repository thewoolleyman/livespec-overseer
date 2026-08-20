"""Auto-resume backoff for a foreman loop that exhausted its tick budget.

Budget exhaustion means the loop is ticking without converging. That is a
CADENCE problem, not a decision for the maintainer, and the resume picker it
replaces measured 13 hours with no foreman loop on 2026-08-19/20.

The escalated interval is durable rather than in-memory: each `foreman-runtime`
invocation builds a fresh config, so a backoff held only in the process would
reset on every tick and never actually back off.
"""

from __future__ import annotations

from pathlib import Path

from foreman_act_record import AppendJournal

__all__: list[str] = [
    "DEFAULT_MAX_LLM_TICK_INTERVAL_SECONDS",
    "auto_resume_interval",
    "effective_interval",
]

# The ceiling the backoff doubles toward. A budget exhaustion is a cadence
# signal rather than a stop condition, but an unbounded backoff would retire the
# loop just as surely as the picker it replaces.
DEFAULT_MAX_LLM_TICK_INTERVAL_SECONDS = 6.0 * 60.0 * 60.0


def effective_interval(*, state: dict[str, object], configured_seconds: float) -> float:
    """The durable interval this tick runs at, falling back to the configured one."""
    recorded = state.get("llm_tick_interval_seconds")
    if isinstance(recorded, bool) or not isinstance(recorded, int | float):
        return configured_seconds
    return float(recorded) if recorded > 0 else configured_seconds


def auto_resume_interval(
    *,
    repo: Path,
    append_journal: AppendJournal,
    interval_seconds: float,
    max_interval_seconds: float,
    tick_generation: int,
) -> float | None:
    """Journal the auto-resume and return the widened interval, or None to stop.

    Returning None restores the pre-existing stop-and-report behavior. That is
    the journal-before-act rule applied here: an auto-resume nobody recorded is
    not an auto-resume, so a failed append must not silently widen the cadence.
    """
    widened = min(interval_seconds * 2.0, max_interval_seconds)
    try:
        append_journal(
            repo=repo,
            record={
                "stage": "foreman-auto-resume",
                "reason": "hard-tick-budget",
                "repo": str(repo),
                "tick_generation": tick_generation,
                "previous_llm_tick_interval_seconds": interval_seconds,
                "llm_tick_interval_seconds": widened,
            },
        )
    except OSError:
        return None
    return widened
