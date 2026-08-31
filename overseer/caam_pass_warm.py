"""The WARM STAGE of one rotation pass: refresh idle snapshots, schedule the next
wake, and record both as one span.

Split out of ``caam_anthropic_pass`` (work-item overseer-m7qrgp.4) for the same
reason ``caam_pass_seams`` was: that module sits ON the 250-LLOC hard ceiling and
cannot carry another line. The cut is by cohesion, not by count -- keeping idle
accounts switchable is one concern with three steps that are only ever performed
together, while the module it left holds the pass's own shape and ordering.

WHY THE STAGE IS A VALUE OBJECT. The warm stage needs eight facts about the pass,
which is past the argument limit and, worse, would have every call site restate
them. ``WarmStage`` gathers them once from the pass's context and seams, so the
two call sites differ only in the account they name as active -- which is the one
thing that genuinely differs between them.

THE TWO ENTRY POINTS ARE NOT INTERCHANGEABLE, and the difference is the reason
they are separate. ``run_warm_stage`` emits the pass's ONE
``caam.warm.schedule`` record; ``warm_idle`` does not. A pass that switches warms
twice -- once before deciding, once afterwards with the NEW active account -- and
recording the second would double-count every pass that moved.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from _caam_pass_span import PassSpan
from _caam_rotation_span import emit_warm_schedule
from caam_anthropic_finish import LineWriter
from caam_pass_seams import AgentRunner, line_logger
from caam_warm import WarmConfig, WarmOutcome, emit_next_warm_wake, keep_warm

__all__: list[str] = [
    "WarmStage",
    "run_warm_stage",
    "warm_idle",
]


@dataclass(frozen=True, kw_only=True)
class WarmStage:
    """Everything the warm stage of one pass needs, gathered once from that pass."""

    span: PassSpan
    home: Path
    state: dict[str, object]
    dry_run: bool
    no_warm: bool
    agent_runner: AgentRunner
    stdout: LineWriter
    now: float


def warm_idle(*, stage: WarmStage, active_name: str) -> WarmOutcome:
    """Refresh every snapshot but this one, so rotation keeps somewhere to go.

    Carrier X13. The oracle invokes this at three sites; hoisting it above the
    decision covers both hold paths and the switch path from one place, which
    three copies cannot be relied on to keep doing. What the hoist alone cannot
    cover is the oracle's LAST site, which runs with the NEW active profile -- and
    since this skips whichever account it is told is active, the account a pass has
    just left is otherwise never a candidate in the pass that left it. That matters
    exactly when the account being left is already inside the warm margin, which is
    ordinary late in a five-hour window and is the deadlock this whole slice exists
    to prevent.
    """

    return keep_warm(
        state=stage.state,
        config=WarmConfig(
            active_name=active_name,
            home=stage.home,
            dry_run=stage.dry_run,
            no_warm=stage.no_warm,
        ),
        agent_runner=stage.agent_runner,
        logger=line_logger(writer=stage.stdout),
        now=stage.now,
    )


def run_warm_stage(*, stage: WarmStage, active_name: str) -> None:
    """Warm the idle accounts, schedule the next wake, and record the pass's span.

    One record covers both halves: what was attempted and refreshed, and which idle
    account the scheduled wake belongs to. The wake comes back from the emitter
    rather than being recomputed, so the span and the operator line can never name
    different instants.
    """

    warmed = warm_idle(stage=stage, active_name=active_name)
    emit_warm_schedule(
        span=stage.span,
        account=active_name,
        warm=warmed,
        schedule=emit_next_warm_wake(
            home=stage.home, active_name=active_name, now=stage.now, stdout=stage.stdout
        ),
        at=stage.now,
    )
