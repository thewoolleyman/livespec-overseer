"""Archive garbage collection for durable mapping rows."""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["archive_gc"]


def _liveness_topic_for_row(*, row: dict[str, object], topic: str) -> str | None:
    kind = row.get("kind")
    if not isinstance(kind, str) or kind not in {"plan", "supervisor"}:
        return None
    if kind == "supervisor":
        supervised_topic = row.get("supervised_topic")
        return supervised_topic if isinstance(supervised_topic, str) else None
    return topic


def archive_gc(*, sup: Supervisor) -> int:
    """Drop mapping rows whose ``<repo>/plan/<topic>/`` is archived or gone."""

    def keep(*, row: dict[str, object]) -> bool:
        repo = row.get("repo")
        topic = row.get("topic")
        if not isinstance(repo, str) or not isinstance(topic, str):
            return True  # fail-soft: never drop a row we can't evaluate
        liveness_topic = _liveness_topic_for_row(row=row, topic=topic)
        if liveness_topic is None:
            return True
        if not registry.repo_root_present(repo=repo):
            # Repo root itself unreachable (unmounted / mid-move) — KEEP the row
            # and surface, so a transient outage does not permanently drop it and
            # lose its custom overrides on the auto-link re-add (B6).
            sup.surface(message=f"repo root missing for {repo}::{topic}; keeping mapping row")
            return True
        if registry.archived_or_gone(repo=repo, topic=liveness_topic):
            sup.log(message=f"archive-GC dropping mapping row {repo}::{topic}")
            return False
        return True

    return registry.rewrite_mapping(keep=keep, store_path=sup.store_path)
