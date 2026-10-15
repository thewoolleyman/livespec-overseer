"""Busy-delivery legs of the idle cascade (spec v058).

A BUSY pane reaches :mod:`_supervisor_evaluate_idle` only when
:func:`_supervisor_busy_delivery.deliverable_while_busy` judged it deliverable. Two of
its legs differ from an idle pane's, and they live here so the cascade keeps reading
top-to-bottom: the settle compares the INPUT region rather than the whole pane (a
generating pane never settles as a whole), and a busy track that owes only its round's
expiry notice stays ``working`` rather than entering the idle-with-room nudge.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_busy_delivery
import _supervisor_launch
import _supervisor_threshold

if TYPE_CHECKING:
    from _supervisor_evaluate_idle import IdleRequest

__all__: list[str] = ["busy_expiry_notice_status", "settled"]


def settled(*, request: IdleRequest, busy_delivery: bool) -> bool:
    """The pre-act settle for this pane: input-only when delivering into a busy pane."""
    if busy_delivery:
        return _supervisor_busy_delivery.input_settled(
            sup=request.sup, target=request.target, is_codex=request.obs.is_codex
        )
    return _supervisor_launch.pane_settled(sup=request.sup, target=request.target)


def busy_expiry_notice_status(*, request: IdleRequest) -> str:
    """Deliver an owed expiry notice into a busy pane; the session is still working."""
    if request.act:
        _ = _supervisor_threshold.maybe_send_expiry_notice(
            request=_supervisor_threshold.ThresholdRequest(
                sup=request.sup,
                track=request.track,
                session=request.session,
                target=request.target,
                threshold=request.threshold,
                act=request.act,
                obs=request.obs,
            )
        )
    return "working"
