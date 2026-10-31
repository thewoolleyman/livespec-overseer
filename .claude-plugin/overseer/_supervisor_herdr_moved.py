"""Follow a supervised session that was relaunched by hand (overseer-bce3).

A session relaunched by hand is a NEW process generation, in another pane of the same
herdr instance or in the very pane the row records (overseer-lw6t). Either way the row
still names the predecessor, and the recorded-identity gate refuses the successor
forever. These helpers move the row and its identity only on positive proof: the same
herdr instance for a moved pane, and the re-key scan's own process-generation match for
a relaunch in place.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import _herdr_replacement_store
import herdr_identity
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["relaunched_identity", "renumbered_coordinate", "repoint_moved_session"]


def _legacy_unqualified_target(*, value: str | None) -> bool:
    return isinstance(value, str) and bool(herdr_identity.decode_target(value=value).tmux_session)


def _same_herdr_instance(*, recorded: str | None, live: str) -> bool:
    """Whether both coordinates name panes on ONE live herdr server generation.

    A session on a different socket or server generation is a namesake, which an exact
    target must never be retargeted to.
    """
    old = herdr_identity.decode_target(value=recorded or "").herdr
    new = herdr_identity.decode_target(value=live).herdr
    return (
        old is not None
        and new is not None
        and herdr_identity.herdr_instance_key(target=old)
        == herdr_identity.herdr_instance_key(target=new)
    )


def _restarted_herdr_server(*, sup: Supervisor, recorded: str | None, live: str) -> bool:
    """Whether the live pane is on a RESTARTED server of the recorded herdr socket.

    A host reboot brings herdr back as a new generation on the SAME socket and resumes
    each pane's agent (overseer-rwrkkr). That is not a namesake only while the recorded
    generation is provably gone: its server pid no longer runs with the recorded start
    time. A recorded generation that still runs is a second live server, and keeps
    refusing.
    """
    old = herdr_identity.decode_target(value=recorded or "").herdr
    new = herdr_identity.decode_target(value=live).herdr
    return (
        old is not None
        and new is not None
        and old.socket_path == new.socket_path
        and (old.server_pid, old.server_starttime) != (new.server_pid, new.server_starttime)
        and sup.starttime_of(pid=old.server_pid) != old.server_starttime
    )


def _live_identity(*, sup: Supervisor, session: str, topic: str) -> str | None:
    identity = sup.claude_identity_by_session.get((session, topic))
    if identity is not None:
        return identity
    live = sup.live_codex.get((session, topic))
    return f"codex:{live.session_id}" if live is not None else None


def repoint_moved_session(
    *, sup: Supervisor, repo: str, topic: str, recorded: str | None, live: str
) -> bool:
    """Re-point a mapped row to the pane its live named session now occupies.

    A legacy tmux row may move to any session; a herdr row only within its own herdr
    instance, or onto the restarted server of its own socket once the recorded
    generation is gone and no unfinished daemon replacement owns the track. The moved
    session's live identity is recorded with it, so the recorded-identity gate accepts
    the pane it now runs in.
    """
    restarted = _restarted_herdr_server(sup=sup, recorded=recorded, live=live)
    if restarted:
        track = _mapped_track(sup=sup, repo=repo, topic=topic)
        restarted = track is not None and not _replacement_open(track=track)
    movable = (
        _legacy_unqualified_target(value=recorded)
        or _same_herdr_instance(recorded=recorded, live=live)
        or restarted
    )
    if (
        not movable
        or recorded == live
        or not registry.repoint_tmux(
            repo=repo, topic=topic, new_tmux=live, store_path=sup.store_path
        )
    ):
        return False
    reason = " after a herdr server restart" if restarted else ""
    sup.log(message=f"re-pointed {repo}::{topic} tmux {recorded} → {live}{reason}")
    identity = _live_identity(sup=sup, session=live, topic=topic)
    if identity is not None:
        _ = registry.record_observed_session_identity(
            repo=repo, topic=topic, session_identity=identity, store_path=sup.store_path
        )
    return True


def _mapped_track(*, sup: Supervisor, repo: str, topic: str) -> registry.Track | None:
    key = (registry.norm(repo=repo), topic)
    return next(
        (
            track
            for track in registry.read_valid_mapping(store_path=sup.store_path)
            if (registry.norm(repo=track.repo), track.topic) == key
        ),
        None,
    )


def _replacement_open(*, track: registry.Track) -> bool:
    """Whether an unfinished daemon replacement (or an unreadable record) owns the track."""
    try:
        transaction = _herdr_replacement_store.read_transaction(
            path=_herdr_replacement_store.scratch_path(track=track)
            / _herdr_replacement_store.RECORD_NAME
        )
    except (AttributeError, OSError, TypeError, ValueError):
        return True
    return transaction is not None and transaction.get("phase") != "completed"


def renumbered_coordinate(*, sup: Supervisor, track: registry.Track, session: str) -> str | None:
    if not session.startswith(herdr_identity.HERDR_SCHEME):
        return None
    resolver = cast(
        Callable[..., str | None] | None,
        getattr(sup.tmux, "renumbered_herdr_coordinate", None),
    )
    if resolver is None:
        return None
    return resolver(
        session=session,
        observed_session_identity=track.observed_session_identity,
        starttime_of=sup.starttime_of,
    )


def relaunched_identity(*, sup: Supervisor, track: registry.Track, session: str) -> str | None:
    """The live identity of a Claude relaunched by hand in the recorded pane, if proven.

    The registry must name a live Claude for this topic in the recorded pane, AND the
    re-key scan must find that identity's process generation in exactly that pane: a
    reused positional id now hosting a foreign process fails the scan. The daemon's own
    unfinished replacement keeps priority, because its successor is reconciled by the
    replacement transaction and never re-recorded here.
    """
    if track.topic not in sup.claude_names_by_session.get(session, set()):
        return None
    identity = sup.claude_identity_by_session.get((session, track.topic))
    resolver = cast(
        Callable[..., str | None] | None,
        getattr(sup.tmux, "renumbered_herdr_coordinate", None),
    )
    if identity is None or identity == track.observed_session_identity or resolver is None:
        return None
    located = resolver(
        session=session, observed_session_identity=identity, starttime_of=sup.starttime_of
    )
    if located != session or _replacement_open(track=track):
        return None
    return identity
