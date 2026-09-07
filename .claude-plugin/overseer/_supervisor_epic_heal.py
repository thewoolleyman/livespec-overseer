"""_supervisor_epic_heal — eager heal of a derivable-but-null plan-epic mapping row.

A plan mapping row can carry an unresolved epic while
``registry.epic_from_plan_anchor(repo, topic)`` WOULD resolve a real epic — a
session adopted before its anchor was readable, or adopted epic-less by design
(``adopt_sessions`` never reads the anchor). Left unhealed such a row renders
``mapping-unusable`` ("mapping row has unresolved epic; restart resume cannot be
built"), lands in ``NEEDS YOU``, and pesters the operator to register an epic the
daemon can name itself.

The restart-boundary re-derive (:func:`_supervisor_restart.rederive_epic_if_stale`,
overseer-vbmq) heals it, but ONLY when a track reaches the restart interlock —
after ``resume_prompt`` returns None, under ``act``. A track that never reaches
that boundary (session-gone, never-restarted, or simply idle-and-fine) is never
healed there, so its derivable null sits mapping-unusable indefinitely
(overseer-fdau). This heals it EAGERLY, on first observation of a derivable null
during the acting tick, so no track has to reach the restart boundary first.

For each assigned plan track whose epic is unresolved, derive once from the
anchor, persist on success (:func:`registry.record_derived_epic`), and re-point
the in-memory row so THIS tick's ``evaluate`` already sees the resolved epic.

Bounded to ONE anchor read per ``(repo, topic)`` per daemon lifetime, so a
genuinely-unresolvable row — the anchor returns None — never adds a ledger
subprocess to every tick; it surfaces to a human unchanged. The bound reuses
``sup.mapping_epics``, the daemon's in-memory record of the epic it has resolved
for each track this lifetime: a hit there means "already resolved OR already
attempted-and-unresolvable this lifetime", so a null-but-derivable row is probed
exactly once. That record is seeded only for RESOLVED rows elsewhere
(``_supervisor_discovery_adoption``), so an unresolved row is never pre-marked and
always gets its one attempt. A daemon restart drops the record and re-attempts,
which only ever helps (an anchor written after the row was adopted becomes
readable). A resolved row is never re-derived: once persisted the joined track
carries the real epic and this pass returns early. A null-epic track is NEVER
dropped — an un-healable row is returned as-is and stays under supervision
(regression guard, cite overseer-y3xhlh.11).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["heal_derivable_epics"]


def heal_derivable_epics(*, sup: Supervisor, rows: list[registry.Track]) -> list[registry.Track]:
    """Return ``rows`` with every derivable-but-null plan epic healed and persisted."""
    return [_heal_one(sup=sup, track=track) for track in rows]


def _heal_one(*, sup: Supervisor, track: registry.Track) -> registry.Track:
    if not isinstance(track, registry.PlanTrack):
        return track
    if registry.epic_is_resolved(epic=track.epic):
        return track
    key = (registry.norm(repo=track.repo), track.topic)
    if key in sup.mapping_epics:
        return track
    derived = sup.epic_lookup(repo=track.repo, topic=track.topic)
    if derived is None:
        # Record the (unresolved) attempt so a genuinely-unresolvable row is not
        # re-probed every tick. The STORED epic is left untouched, so the row still
        # surfaces to a human unchanged; only the in-memory bound is marked.
        sup.mapping_epics[key] = track.epic
        return track
    _ = registry.record_derived_epic(
        repo=track.repo, topic=track.topic, epic=derived, store_path=sup.store_path
    )
    sup.mapping_epics[key] = derived
    sup.log(message=f"healed derivable epic for {track.repo}::{track.topic} → {derived}")
    return registry.track_with_epic(track=track, epic=derived)
