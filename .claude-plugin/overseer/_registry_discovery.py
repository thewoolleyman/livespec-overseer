"""Plan discovery, the discovery ⋈ mapping join, and archive-GC.

Extracted from `registry.py` at its own section banner when that module crossed the
250-LLOC hard ceiling. `registry.py` re-exports this surface, so consumers keep
importing `registry`.

The WATCH SET — the `~/.livespec-overseer-repos.json` declaration, its entry shapes and
the small JSONC scanner it is parsed with — moved on to `_registry_watch_set.py` when
this module crossed the 200-LLOC soft band; it was a second concern this docstring had
always listed separately, and the scanner now sits with its only consumers. Both public
readers are imported back below, so this module's own surface is unchanged.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import signals
from _registry_core import (
    Track,
    UnassignedPlan,
    colliding_topics,
    norm,
    tmux_id,
    warn,
)
from _registry_watch_set import (
    repo_idle_nudge_from_config as repo_idle_nudge_from_config,
)
from _registry_watch_set import (
    watch_set_from_config as watch_set_from_config,
)

__all__: list[str] = [
    "archived_or_gone",
    "discover_plans",
    "join",
    "plan_liveness_topic",
    "repo_idle_nudge_from_config",
    "repo_root_present",
    "watch_set_from_config",
]


# --------------------------------------------------------------------------- #
# Discovery, join, watch-set, archive-GC.
# --------------------------------------------------------------------------- #


def discover_plans(
    *,
    watch_repos: Iterable[str | os.PathLike[str]],
) -> list[tuple[str, str]]:
    """Enumerate each watched repo's ``plan/*/`` DIRECTORIES (a track per dir).

    Returns ``(repo, topic)`` pairs, sorted for determinism. Discovery keys on the
    ``plan/<topic>/`` DIRECTORY existing — it does NOT read or stat any FILE inside it,
    because the overseer never touches a session's ``plan/`` files (their contents are
    the session's own workflow). Discovery derives NO pointer into the directory at all:
    a track's read-first source is the plan state held on its ledger epic, whose id the
    mapping store persists, so there is nothing path-shaped for discovery to hand out.
    Excludes ``plan/archive/**`` (only direct children of ``plan/`` are
    considered, and the literal ``archive`` dir is skipped).
    Fail-soft: a repo with no ``plan/`` dir contributes nothing, and an OSError
    on ONE repo (a ``plan/`` that becomes unreadable between the ``is_dir`` check
    and ``iterdir`` — chmod, NFS hiccup, mid-clone) is warned and skipped rather
    than propagated out to crash the daemon that supervises ALL tracks
    (adversarial code review 2026-07-13, blocker B7).
    """
    pairs: list[tuple[str, str]] = []
    for repo in watch_repos:
        repo_norm = norm(repo=repo)
        plan_dir = Path(repo_norm) / "plan"
        try:
            if not plan_dir.is_dir():
                continue
            children = list(plan_dir.iterdir())
        except OSError as exc:
            warn(message=f"unreadable plan dir {plan_dir}: {exc}")
            continue
        for child in children:
            try:
                if not child.is_dir() or child.name == "archive":
                    continue
                if signals.topic_reserved_for_supervisor(topic=child.name):
                    warn(message=f"refusing reserved supervisor plan directory {child}")
                    continue
                # Directory existence IS the track — nothing inside it is read,
                # stat-ed, or named.
                pairs.append((repo_norm, child.name))
            except OSError as exc:
                warn(message=f"unreadable plan child {child}: {exc}")
                continue
    discovered = _without_reserved_session_derivations(discovered=pairs)
    discovered.sort(key=lambda t: (t[0], t[1]))
    return discovered


def _without_reserved_session_derivations(
    *,
    discovered: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    collisions = colliding_topics(discovered=discovered)
    admitted: list[tuple[str, str]] = []
    for repo, topic in discovered:
        try:
            _ = tmux_id(repo=repo, topic=topic, colliding=collisions)
        except ValueError as exc:
            warn(message=str(exc))
            continue
        admitted.append((repo, topic))
    return admitted


def join(
    *,
    discovered: Iterable[tuple[str, str]],
    mapping: Iterable[Track],
) -> list[Track]:
    """LEFT JOIN discovered plans with mapping rows on ``(repo, topic)``.

    Discovery is the left side: one Track per discovered pair. A discovered plan with a
    mapping row yields the mapped Track unchanged — discovery contributes only the
    track's EXISTENCE, since every durable fact about it (its session, its plan epic, an
    operator's resume override, a threshold) lives in the row. A discovered-but-unmapped
    plan yields an ``unassigned`` Track. Mapping rows with no discovered plan do NOT
    appear here — those are dropped by the daemon's archive-GC, not the join.
    """
    index: dict[tuple[str, str], Track] = {}
    for track in mapping:
        index[(norm(repo=track.repo), track.topic)] = track

    result: list[Track] = []
    for repo, topic in discovered:
        mapped = index.get((norm(repo=repo), topic))
        result.append(mapped if mapped is not None else UnassignedPlan.make(repo=repo, topic=topic))
    result.sort(key=lambda t: (norm(repo=t.repo), t.topic))
    return result


def repo_root_present(*, repo: str) -> bool:
    """True if the repo checkout root itself exists as a directory.

    The daemon's GC preconditions on this so a TRANSIENTLY-unreachable repo (an
    unmounted volume, a repo mid-move) is not mistaken for "plan deleted" and its
    mapping row permanently dropped + later re-created with DEFAULT overrides
    (adversarial code review 2026-07-13, blocker B6). A missing root ⇒ keep the
    row and surface; only a plan gone UNDER an existing root is a real deletion.
    """
    try:
        return Path(repo).is_dir()
    except OSError:
        return False


def plan_liveness_topic(*, repo: str, topic: str) -> str | None:
    """The plan topic whose directory certifies ``topic`` is still live.

    Ordinary worker topics certify against their own ``plan/<topic>/`` directory.
    A ``-supervisor`` entity has no plan directory of its own by design; it inherits
    liveness from the worker topic it supervises, but only when that worker plan is
    actually live. With no live supervised counterpart, the entity has no liveness
    source and should still be refused or dropped.
    """
    worker_topic = signals.topic_supervised_worker(topic=topic)
    if worker_topic is None:
        return topic
    if (Path(repo) / "plan" / worker_topic).is_dir():
        return worker_topic
    return None


def archived_or_gone(*, repo: str, topic: str) -> bool:
    """True if ``<repo>/plan/<topic>/`` is archived or deleted (ACTIVE wins).

    Used by the daemon's GC to drop a mapping row whose plan has been archived or
    deleted. The ACTIVE ``plan/<topic>`` is checked FIRST and wins: a live plan
    whose topic name ALSO happens to exist under ``plan/archive/`` (a new plan
    reusing a retired topic slug) must NOT be treated as archived — the old code
    checked the archive path first and would GC-drop the active plan's row every
    tick (adversarial code review 2026-07-13, blocker B6). Callers should
    precondition on :func:`repo_root_present` so a missing repo ROOT (transient
    unmount) is not read here as a gone plan.
    """
    live_topic = plan_liveness_topic(repo=repo, topic=topic)
    if live_topic is None:
        return True
    base = Path(repo) / "plan"
    if (base / live_topic).is_dir():
        return False  # active plan present — wins over any same-named archive copy
    if (base / "archive" / live_topic).is_dir():
        return True  # archived
    return True  # plan dir gone under an existing repo root ⇒ deleted
