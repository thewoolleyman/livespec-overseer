"""Stateless Enter-only recovery for an exact durable Herdr prompt."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import herdr_identity
import pane_router_observe
import pane_router_reads
import pane_router_submit_signals
import signals

__all__: list[str] = ["retry_enter_once"]


def retry_enter_once(
    *,
    reads: pane_router_reads.PaneRoutingReads,
    writer: pane_router_submit_signals.HerdrInput,
    session: str,
    text: str,
    sleep: Callable[[float], None],
) -> tuple[bool, bool]:
    """Submit an exact, already-visible prompt without pasting it again."""
    target = cast(herdr_identity.HerdrPaneTarget, reads.decode(value=session).herdr)
    expected = text.partition("\n")[0].strip()
    capture = reads.capture_pane(session=session)
    if signals.input_box_text(capture_text=capture) != expected:
        return False, False
    entered = writer.send_enter(target=target)
    if not entered.ok and not entered.effect_unknown:
        return False, False
    observed = pane_router_observe.observe_capture(
        reads=reads,
        session=session,
        sleep=sleep,
        accept=pane_router_submit_signals.submitted,
    )
    if pane_router_submit_signals.submitted(capture=observed):
        return True, False
    still_pending = signals.input_box_text(capture_text=observed) == expected
    return False, entered.effect_unknown or not still_pending
