"""_supervisor_archived_live — a mapped plan stays supervised while its runtime lives.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. It answers exactly one question — "is this mapped row ARCHIVED but still RUNNING?"
— and it is the only place that answer is derived, so discovery, archive-GC and the row
projection cannot grow three different opinions of it.

**Maintainer ruling 2026-09-12.** Plan archival ends live-plan DISCOVERY; it does NOT end
supervision of a session that is still running. Two mechanics together used to end it
anyway: :func:`registry.discover_plans` enumerates ``plan/*/`` and deliberately skips
``plan/archive/**``, and :func:`_supervisor_archive_gc.archive_gc` drops the mapping row
of a plan that is no longer there. Measured on ``create-agent-cockpit-repo``: the tmux
session was still alive and its agent still working when the plan was archived, and
within one tick the track had no row, no snapshot entry and no mapping — so the daemon
could not read its context, could not inject a wind-down, and could not complete a
ready-gated restart. Nothing was wrong with the SESSION; it had simply become invisible.

So a previously-mapped plan whose directory is archived (or gone) is re-admitted to the
tick's discovery set for as long as its recorded runtime exists, carrying its stored
Track unchanged — same epic locator, same launch profile — and archive cleanup becomes
eligible only once that runtime is genuinely gone.

Free functions taking the ``Supervisor`` as a parameter; ``Supervisor`` is imported under
``TYPE_CHECKING`` only, so the annotation resolves for pyright-strict while no runtime
import cycle exists. The only sibling this imports is the :class:`RowView` value type it
projects onto.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import registry
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "ARCHIVED_LIVE_EVENT",
    "extend_discovery",
    "mark_row",
    "retained_keys",
    "row_runtime_is_live",
    "runtime_is_live",
]

# The event name an entering retention is recorded under in the daemon's event history.
# Distinct from the archive-GC drop line on purpose: an operator reading the log has to be
# able to tell "this archived row is retained DELIBERATELY, because its session is still
# running" from "this row is a stale unarchived plan nobody has cleaned up".
ARCHIVED_LIVE_EVENT = "archived-live-retained"


def runtime_is_live(*, sup: Supervisor, session: str) -> bool:
    """Authoritative evidence that the runtime recorded for ``session`` still exists.

    tmux session existence is the evidence, for BOTH harnesses and at every moment of a
    restart. The Claude session registry and the live-Codex map are strictly NARROWER:
    each is empty for the seconds between a ``respawn-pane -k`` and the successor's first
    registry write, so keying retention on either would drop the mapping in exactly the
    window a fresh successor needs it — the successor would be born unsupervised, which
    is the same defect one restart later. And they cannot disagree in the other
    direction: both maps are keyed BY tmux session, so a session tmux does not have
    cannot appear in either.
    """
    return sup.tmux.session_exists(session=session)


def row_runtime_is_live(*, sup: Supervisor, row: dict[str, object], topic: str) -> bool:
    """Whether archive-GC must KEEP an already-archived RAW mapping row.

    Scoped to ``kind == "plan"`` rows. A ``supervisor`` seat whose worker thread is
    archived has a DIFFERENT, already-designed answer (overseer-y26): its computed binder
    is gone BY DESIGN once the thread is archived, and the seat is retired quietly rather
    than kept. Retention must not reach it, so this returns False for every other kind —
    including a legacy row with no ``kind`` at all, which archive-GC already keeps on its
    own fail-soft terms.

    The recorded ``tmux`` name is the session asked about; a row missing it falls back to
    the topic, which is the name :func:`registry.tmux_id` derives for an uncollided topic
    and the name such a row would have been launched under.
    """
    if row.get("kind") != "plan":
        return False
    recorded = row.get("tmux")
    session = recorded if isinstance(recorded, str) and recorded else topic
    return runtime_is_live(sup=sup, session=session)


def _track_is_archived_live(*, sup: Supervisor, track: registry.Track) -> bool:
    if track.kind != "plan":
        return False
    if not registry.repo_root_present(repo=track.repo):
        # An unreachable repo ROOT (unmounted volume, repo mid-move) is not evidence of
        # ARCHIVAL. Archive-GC already holds such a row untouched and surfaces it (B6);
        # claiming it as archived-live here would additionally join it back in as a
        # supervised row, asserting a supervision no discovery supports.
        return False
    if not registry.archived_or_gone(repo=track.repo, topic=track.topic):
        return False
    return runtime_is_live(sup=sup, session=track.tmux)


def retained_keys(*, sup: Supervisor) -> frozenset[tuple[str, str]]:
    """``(normalized repo, topic)`` for every mapped PLAN row that is archived-live.

    Normalized with :func:`registry.norm` because this set is compared against — and
    unioned into — the discovery pairs the join keys on, and both sides of that join must
    normalize identically or rows silently vanish.
    """
    return frozenset(
        (registry.norm(repo=track.repo), track.topic)
        for track in registry.read_valid_mapping(store_path=sup.store_path)
        if _track_is_archived_live(sup=sup, track=track)
    )


def extend_discovery(
    *,
    sup: Supervisor,
    discovered: list[tuple[str, str]],
    act: bool,
) -> list[tuple[str, str]]:
    """Fold this tick's archived-live rows back into the discovery set.

    Discovery keys on a LIVE ``plan/<topic>/`` directory and skips ``plan/archive/**``,
    so an archived track has no left-hand side for the join and would vanish from the row
    set even though its row survives GC. Re-admitting the pair HERE — and only here —
    keeps the join, the evaluate cascade, the restart path and every operator surface
    working from one row set, with the stored Track (its epic locator, its launch
    profile) untouched.

    ``sup.archived_live`` carries the PREVIOUS pass's retention set on the way in and this
    pass's on the way out. That double duty is deliberate rather than thrifty: the
    difference between them is exactly the set of tracks that ENTERED retention, which is
    what makes the event edge-triggered (invariant 10) instead of one line per tick per
    archived track, for as long as the session lives. Only an ACTING tick reports, because
    the read-only ``list`` path must not write an event history it did not earn — but both
    paths refresh the set, so `list` still DISPLAYS the retention it did not perform.
    """
    retained = retained_keys(sup=sup)
    if act:
        for repo, topic in sorted(retained - sup.archived_live):
            sup.log(
                event=ARCHIVED_LIVE_EVENT,
                message=(
                    f"archived plan {repo}::{topic} kept under supervision — "
                    "its recorded session is still live"
                ),
                repo=repo,
                topic=topic,
                fields={"archived_live": True},
            )
    sup.archived_live = retained
    return sorted(set(discovered) | retained)


def mark_row(*, row: RowView, retained: frozenset[tuple[str, str]]) -> RowView:
    """Flag ROW when its track is being supervised past its own plan's archival.

    A dedicated FIELD rather than a note: the note is session-authored free text that is
    elided at a display width, and whether a row is retained on purpose is a machine-
    readable fact the status snapshot has to be able to carry intact.
    """
    if (registry.norm(repo=row.repo), row.topic) not in retained:
        return row
    return dataclasses.replace(row, archived_live=True)
