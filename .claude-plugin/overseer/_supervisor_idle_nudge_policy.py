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

This is a SEAM, and it held: all three slices landed by EXTENDING this one function,
leaving the ``_supervisor_idle`` call site untouched from the day slice A wrote it. The
whole precedence chain therefore sits in exactly one readable place rather than inline in
the gate condition — which is the property to preserve if a fourth tier is ever wanted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["resolve_idle_nudge"]


def _per_repo_overrides(*, sup: Supervisor) -> dict[str, bool]:
    """The per-repo overrides declared in the watch-set this supervisor reads.

    RE-READ rather than cached, deliberately: the watch-set is a hand-edited operator
    file the daemon already re-reads every tick for the watch set itself, so quieting a
    repo takes effect on the next tick without bouncing the daemon (which would otherwise
    mean losing every track's in-memory idle clock to change one flag). The read is cheap
    and rare — it is reached only after the per-track tier declines, and only for a track
    that has already gone idle above threshold.

    A supervisor with no ``watch_set_path`` — the beside-tests that inject ``watch_repos``
    directly, and the extra-repos-only path — has declared no watch-set to read, so it has
    no per-repo overrides and the daemon-wide default answers.
    """
    if sup.watch_set_path is None:
        return {}
    return registry.repo_idle_nudge_from_config(config_path=sup.watch_set_path)


def resolve_idle_nudge(*, sup: Supervisor, track: registry.Track) -> bool:
    """The effective idle-nudge decision for one track: True = may nudge, False = do not.

    The precedence chain, most specific first:

    1. the track's own ``idle_nudge`` override (``overseer add --idle-nudge {on,off}``),
       which wins in BOTH directions — it can quiet one track under a daemon-wide ``on``
       and opt one track back in under a daemon-wide ``off``;
    2. the per-repo override declared beside that checkout in the watch-set
       (``~/.livespec-overseer-repos.json``, an entry spelled
       ``{"path": "<checkout>", "idle_nudge": false}``), which does the same for every
       track in one repo that has not spoken for itself;
    3. the daemon-wide default — ``overseerd --idle-nudge {on,off}``, carried on
       :attr:`Supervisor.idle_nudge` and defaulting to on, so an absent flag, a
       bare-string watch-set entry and an override-free row together preserve exactly the
       behaviour the daemon always had.

    ``None`` is what makes the first two tiers genuine THREE-state settings rather than
    booleans that have to pick a side: it means "no override", not "off". That is why
    ``--idle-nudge inherit`` removes the row key instead of writing ``false``, and why a
    watch-set entry without the key declares nothing — a persisted ``false`` at either
    tier would pin today's answer to the daemon-wide question forever.
    """
    if track.idle_nudge is not None:
        return track.idle_nudge
    per_repo = _per_repo_overrides(sup=sup).get(registry.norm(repo=track.repo))
    if per_repo is not None:
        return per_repo
    return sup.idle_nudge
