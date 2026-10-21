"""Naming a fresh Herdr Codex successor, proven by the successor's own index record.

A fresh Codex rollout carries no ``session_index`` ``thread_name``, so the daemon submits
``/rename <topic>`` to bind one. That payload is unlike every other payload the daemon
pastes, and the difference is the whole reason this module exists: a slash command asks
the model for nothing, so no turn begins, and a Codex pane can prove neither a turn start
nor an empty composer. NOTHING a capture can show ever confirms the rename landed.

Measured 2026-10-21 (found by factory run 01M5EVBNK0X1, reproduced three times against a
real herdr instance, the released ``overseerd`` and a stub codex): submitting it through
the verified native prompt submitter therefore left an UNCONFIRMED per-pane attempt
standing forever, and the submitter answers every later payload for a pane from the
attempt it already holds. So the replacement's resume line was never pasted,
``_resume_successor`` failed, and the Enter-only retry had no payload in the composer to
match — the Codex arm of herdr replacement could not complete for any caller.

SPECIFICATION v064 (``SPECIFICATION/spec.md``, the supervision-round rules) settles it: a
daemon-authored payload that asks the runtime for no turn MUST NOT be held as an
UNCONFIRMED delivery and MUST NOT suppress a later paste, and the daemon MUST prove its
outcome by that payload's own evidence — for a Codex rename, the durable session-index
record binding the successor's rollout to the topic — never by an observed turn start.

So the submission here holds no attempt at all. The paste goes through the pane's ordinary
write surface, which keeps no per-pane delivery state, and the Enter through the stateless
exact-payload submitter, which reads the composer afresh every call. That is the same
shape the tmux arm already uses (:mod:`_supervisor_codex_fresh` pastes, re-sends Enter,
and polls ``fresh_rollout_indexed``); it is the held router state, not the sequence, that
the herdr arm got wrong. Every OTHER payload keeps the held-attempt suppression exactly as
it was.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, cast

import codex_sessions
import registry
from _supervisor_config import RESTART_POLL_INTERVAL, RESTART_POLL_MAX

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["name_fresh_successor", "rollout_named"]


class PendingEnterRetry(Protocol):
    def __call__(
        self,
        *,
        session: str,
        text: str,
        sleep: Callable[[float], None],
    ) -> tuple[bool, bool]: ...


def rollout_named(*, sup: Supervisor, track: registry.Track, rollout: str) -> bool:
    """True once the durable session index binds ``rollout`` to this track's plan topic.

    This record is written while the successor is still idle and outlives its process, so
    it is the one piece of evidence that exists in the naming phase — where no turn start
    is coming and the fd-gated live join can still be empty.
    """
    indexed = codex_sessions.latest_session_for_thread_name(
        thread_name=track.topic, codex_home=sup.codex_home
    )
    return indexed == rollout


def _submit_no_turn(*, sup: Supervisor, target: str, text: str) -> bool:
    """Paste the payload afresh and submit it, recording no attempt for this pane.

    Returns whether the Enter may have landed, which is as much as a no-turn payload can
    report about itself: a refused paste or an Enter the daemon can show never arrived is
    a provable miss, and anything else is left to the caller's own evidence. A pane driver
    with no stateless exact-payload submitter — a non-Herdr backend — sends the single
    Enter the tmux naming arm sends.
    """
    if not sup.tmux.bracketed_paste(session=target, text=text):
        return False
    native = cast(PendingEnterRetry | None, getattr(sup.tmux, "retry_prompt_enter_once", None))
    if native is None:
        sup.sleep(RESTART_POLL_INTERVAL)
        return sup.tmux.send_keys(session=target, keys="Enter")
    submitted, effect_unknown = native(session=target, text=text, sleep=sup.sleep)
    return submitted or effect_unknown


def name_fresh_successor(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    text: str,
    rollout: str,
) -> bool:
    """Submit the no-turn naming payload, then wait — bounded — for the index to record it.

    False means the successor is still UNNAMED when the bound expires, which the caller
    surfaces with the ready declaration kept and no resume line delivered; it never means
    the payload may be replayed from here.
    """
    if not _submit_no_turn(sup=sup, target=target, text=text):
        return False
    for _ in range(RESTART_POLL_MAX):
        if rollout_named(sup=sup, track=track, rollout=rollout):
            return True
        sup.sleep(RESTART_POLL_INTERVAL)
    return False
