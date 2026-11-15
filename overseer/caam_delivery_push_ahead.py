"""Push a delivery, then move the counter past any host found ahead of it.

A host whose apply step refuses with `stale-sequence <seq> host-applied <n>` and
n greater than the pushed sequence is AHEAD: the service's counter is behind the
host, for example after the counter was lost. The host is resolved by moving the
counter FORWARD to the greatest host-applied sequence and reissuing the current
delivery with the next sequence, so no host is ever moved back and none is
exempted from retry (SPECIFICATION/contracts.md, proposal #3094).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import caam_delivery_push
import caam_delivery_service
import streams
from caam_delivery_push_state import ahead_of

__all__: list[str] = ["push_and_reconcile"]


def push_and_reconcile(  # noqa: PLR0913 - each argument is an independent seam
    *,
    home: Path,
    delivery: caam_delivery_service.Delivery,
    now: float,
    confirm: Callable[..., str | None],
    run: caam_delivery_push.Runner,
    reissue: str | None,
    start: caam_delivery_push.Starter,
) -> caam_delivery_service.Delivery:
    """Push `delivery`; past a host ahead, push the reissue. Returns the current delivery."""
    _push(home=home, delivery=delivery, now=now, run=run, reissue=reissue, start=start)
    ahead = ahead_of(state=caam_delivery_push.load_state(home=home), sequence=delivery.sequence)
    issued = (
        None
        if ahead is None
        else caam_delivery_service.issue_delivery(
            home=home, now=now, confirm_account=confirm, above=ahead
        )
    )
    if issued is not None:
        _push(home=home, delivery=issued, now=now, run=run, reissue=reissue, start=start)
    return issued or delivery


def _push(
    *,
    home: Path,
    delivery: caam_delivery_service.Delivery,
    now: float,
    run: caam_delivery_push.Runner,
    reissue: str | None,
    start: caam_delivery_push.Starter,
) -> None:
    """Push `delivery` to every host due it, one journal line per outcome."""
    outcomes = caam_delivery_push.push_due(
        home=home, delivery=delivery, now=now, run=run, reissue=reissue, start=start
    )
    for label, outcome in outcomes.items():
        streams.write_stdout(text=f"push {label} sequence {delivery.sequence}: {outcome}\n")
