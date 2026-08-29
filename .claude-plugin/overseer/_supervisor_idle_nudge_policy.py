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

This is a SEAM, deliberately wider than what it does today. Slice A resolves the
daemon-wide default alone; the per-track (slice B) and per-repo (slice C) overrides
extend THIS function, so the ``_supervisor_idle`` call site never has to be re-plumbed
and the tri-state precedence lands in exactly one readable place rather than inline in
the gate condition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["resolve_idle_nudge"]


def resolve_idle_nudge(*, sup: Supervisor, track: registry.Track) -> bool:
    """The effective idle-nudge decision for one track: True = may nudge, False = do not.

    Slice A consults ONLY the daemon-wide default — ``overseerd --idle-nudge {on,off}``,
    carried on :attr:`Supervisor.idle_nudge` and defaulting to on, so an absent flag
    preserves the behaviour the daemon has always had exactly.

    ``track`` is unused today and is in the signature ON PURPOSE: it is what slices B
    and C need in order to consult a per-track override and the track's repo, and taking
    it now is the difference between those slices extending this function and those
    slices rewriting the call site.
    """
    del track  # slice A: the daemon-wide default is the whole precedence chain
    return sup.idle_nudge
