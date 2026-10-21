"""Stateless delivery of a daemon payload a Herdr runtime answers with NO turn."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import cast

import herdr_identity
import pane_router_observe
import pane_router_reads
import pane_router_submit_signals

__all__: list[str] = ["submit_no_turn_once"]


def submit_no_turn_once(
    *,
    reads: pane_router_reads.PaneRoutingReads,
    writer: pane_router_submit_signals.HerdrInput,
    session: str,
    text: str,
    sleep: Callable[[float], None],
) -> bool:
    """Paste and submit a no-turn payload, recording NO attempt that could outlive it.

    SPECIFICATION v064, spec.md, the supervision round: a daemon-authored payload that
    asks the runtime for no turn — the ``/rename <topic>`` that names a fresh Codex
    successor — MUST NOT be held as an UNCONFIRMED delivery, and MUST NOT suppress a
    later paste. The ordinary submitter cannot honour that: it confirms a delivery
    only by an observed turn start or a positively empty composer, a slash command
    starts no turn, and a Codex composer is never positively empty
    (:func:`pane_router_submit_signals.composer_empty`), so its attempt resolved in
    NEITHER direction. Held, it then answered every later request for that pane from
    the stale rename and the replacement's resume line was never pasted at all
    (factory run 01M5EVBNK0X1 on overseer-uzvcbn.4, reproduced three times against a
    real herdr instance).

    So the attempt is deliberately forgotten here. The outcome is proven by the
    CALLER from the payload's own evidence — for a rename, the durable
    ``session_index`` record binding the successor's rollout to the topic — exactly as
    the tmux arm proves it (:func:`_supervisor_codex_successor.fresh_rollout_indexed`).

    The returned bool reports only that the writes were ACKNOWLEDGED. It is never
    delivery confirmation, and a caller that reads it as one has the wrong proof.
    """
    target = cast(herdr_identity.HerdrPaneTarget, reads.decode(value=session).herdr)
    pasted = writer.bracketed_paste(target=target, text=text)
    if not pasted.ok and not pasted.effect_unknown:
        return False
    # The same pre-Enter observation the ordinary submitter takes, for the same reason:
    # a freshly launched runtime can still be drawing its first frame, and an Enter
    # that arrives then is dropped. The capture is read for its timing, not for a
    # verdict — this payload has no verdict to read out of a pane.
    _ = pane_router_observe.observe_capture(
        reads=reads,
        session=session,
        sleep=sleep,
        accept=partial(pane_router_submit_signals.prompt_visible, text=text),
    )
    entered = writer.send_enter(target=target)
    return entered.ok or entered.effect_unknown
