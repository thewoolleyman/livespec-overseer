"""Archive garbage collection for durable mapping rows."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import foreman_valve_policy
import registry
import signals

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


def _full_autonomy_enabled(*, repo: str) -> bool:
    resolved = foreman_valve_policy.effective_full_autonomy(repo=Path(repo))
    return resolved.get("full_autonomy") is True


def _canonical_session(*, sup: Supervisor, repo: str, topic: str) -> str:
    return registry.tmux_id(repo=repo, topic=topic, colliding=sup.colliding_topics)


def _clear_path(*, sup: Supervisor, path: Path, repo: str, topic: str) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        sup.log(message=f"could not clear archived seat state for {repo}::{topic}: {exc}")


def _clear_archived_seat_state(*, sup: Supervisor, repo: str, topic: str) -> None:
    _clear_path(sup=sup, path=signals.state_path(repo=repo, topic=topic), repo=repo, topic=topic)
    _clear_path(
        sup=sup,
        path=signals.marker_dir(repo=repo, topic=topic) / ".supervisor-state",
        repo=repo,
        topic=topic,
    )
    supervisor_topic = signals.supervisor_topic(entity_topic=topic)
    _clear_path(
        sup=sup,
        path=signals.marker_dir(repo=repo, topic=supervisor_topic) / ".supervisor-state",
        repo=repo,
        topic=topic,
    )
    registry.clear_injection_stamp(repo=repo, topic=topic, stamp_path=sup.stamp_path)


def _exit_archived_seat(*, sup: Supervisor, repo: str, topic: str, session: str) -> bool:
    if session != _canonical_session(sup=sup, repo=repo, topic=topic):
        sup.log(message=f"archive-GC leaving shared tmux session running {repo}::{topic}")
        return True
    if not sup.tmux.session_exists(session=session):
        sup.log(message=f"archive-GC found no tmux session to exit for {repo}::{topic}")
        return True
    if not sup.tmux.bracketed_paste(session=session, text="/exit"):
        sup.surface(message=f"archive-GC could not paste /exit for {repo}::{topic}; keeping row")
        return False
    if not sup.tmux.send_keys(session=session, keys="Enter"):
        sup.surface(message=f"archive-GC could not submit /exit for {repo}::{topic}; keeping row")
        return False
    sup.log(message=f"archive-GC submitted /exit for archived seat {repo}::{topic}")
    return True


def _retire_archived_seat(
    *, sup: Supervisor, row: dict[str, object], repo: str, topic: str
) -> bool:
    if not _full_autonomy_enabled(repo=repo):
        return True
    tmux = row.get("tmux")
    if not isinstance(tmux, str):
        return True
    if not _exit_archived_seat(sup=sup, repo=repo, topic=topic, session=tmux):
        return False
    _clear_archived_seat_state(sup=sup, repo=repo, topic=topic)
    return True


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
            if not _retire_archived_seat(sup=sup, row=row, repo=repo, topic=liveness_topic):
                return True
            sup.log(message=f"archive-GC dropping mapping row {repo}::{topic}")
            return False
        return True

    return registry.rewrite_mapping(keep=keep, store_path=sup.store_path)
