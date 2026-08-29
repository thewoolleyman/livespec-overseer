"""_supervisor_idle_nudge_policy — the ONE place the idle-nudge decision is resolved.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. The single surface here answers one question for one track: may the daemon send
the idle-with-context "keep going" nudge?

**It governs that nudge and NOTHING else.** The low-context wrap-up injection and the
cardinal-rule restart-on-``ready`` have no off-switch and stay unconditional for every
actively-driven plan: a session that has run its context down must still be wound up
and restarted, whatever an operator thinks of being poked while idle. Do not reach this
function from ``_supervisor_wrapup_injection``, ``_supervisor_ready`` or
``_supervisor_restart`` — a repo-level test asserts those three modules never mention
it, because "the daemon stops nudging me" and "the daemon stops winding me down" are
very different promises and the second one is not on offer.

This is a SEAM, deliberately wider than what it does today, and slice B is the first
proof it works: the per-track override landed by EXTENDING this function, leaving the
``_supervisor_idle`` call site untouched. The per-repo override (slice C) extends it the
same way, so the precedence chain stays in exactly one readable place rather than inline
in the gate condition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["resolve_idle_nudge"]


def resolve_idle_nudge(*, sup: Supervisor, track: registry.Track) -> bool:
    """The effective idle-nudge decision for one track: True = may nudge, False = do not.

    The precedence chain, most specific first:

    1. the track's own ``idle_nudge`` override (``overseer add --idle-nudge {on,off}``),
       which wins in BOTH directions — it can quiet one track under a daemon-wide ``on``
       and opt one track back in under a daemon-wide ``off``;
    2. the daemon-wide default — ``overseerd --idle-nudge {on,off}``, carried on
       :attr:`Supervisor.idle_nudge` and defaulting to on, so an absent flag and an
       override-free row together preserve exactly the behaviour the daemon always had.

    ``None`` is what makes the first tier a genuine THREE-state field rather than a
    boolean that has to pick a side: it means "no override", not "off". That is why
    ``--idle-nudge inherit`` removes the row key instead of writing ``false`` — a
    persisted ``false`` would pin today's answer to the daemon-wide question forever.
    """
    if track.idle_nudge is not None:
        return track.idle_nudge
    return sup.idle_nudge
