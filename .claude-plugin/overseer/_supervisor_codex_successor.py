"""Who the fresh Codex successor IS — proving its identity, and recording it.

Split out of :mod:`_supervisor_codex_fresh` by cohesion: that module runs the bring-up
SEQUENCE, while every question of the form "which rollout is this, and is it the one
this round created?" lives here. The two halves are asked at different times by
different callers — the sequence asks while the restart is in flight, and
:mod:`_supervisor_codex_late_adoption` asks again on an ordinary tick hours later —
which is exactly why the answers belong in one place rather than inside the sequence
that happens to ask first.

The proofs are deliberately phase-local. A fresh rollout is NAMED from the durable
``session_index`` record, which is written while the successor is still idle and
outlives the process; it is proven LIVE from the fd-gated discovery join, which needs a
process holding its rollout open and is therefore only answerable once Codex is
executing a turn. Taking each from the phase that produces it is what the 2026-09-11
control cost to learn (see :mod:`_supervisor_codex_fresh`); asking for the resulting
IDENTITY rather than a yes/no is what lets a later tick compare against it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_launch
import codex_sessions
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "fresh_rollout_indexed",
    "fresh_rollout_live",
    "named_successor_rollout",
    "record_fresh_restart_attempt",
    "rename_command",
]


def rename_command(*, topic: str) -> str:
    """The Codex TUI slash command that persists ``topic`` as the session's thread name.

    ``/rename`` is what appends a ``thread_name`` record to ``session_index.jsonl``, and
    that record is the DURABLE half of the successor's identity: it outlives the process,
    so a daemon that is itself restarted still joins the rollout back to its plan topic.
    The live half — the mapping row already binding this tmux session — is what makes the
    fresh session adoptable within the very next tick even before the index is re-read.
    """
    return f"/rename {topic}"


def fresh_rollout_indexed(*, sup: Supervisor, track: registry.Track, prior_session_id: str) -> bool:
    """True once ``session_index`` names THIS topic on a rollout that is not the prior one.

    The naming proof that is available in the phase the naming happens: ``/rename`` appends
    the record, and the record does not depend on any process still being alive — let alone
    on one holding its rollout open, which is the fd evidence the idle successor does not
    yet supply. Among the ids the index finally names ``topic``, the most-recently-updated
    one wins, so the answer flips exactly when the rename lands on a NEW rollout rather
    than on any older namesake of the same topic.

    The id is required to be a canonical UUID for the same reason the predecessor's is
    (:func:`_supervisor_codex_restart._prior_session_id`): an id that cannot be compared
    cannot discriminate "the rollout changed" from "nothing happened".
    """
    indexed = codex_sessions.latest_session_for_thread_name(
        thread_name=track.topic, codex_home=sup.codex_home
    )
    return (
        indexed is not None
        and indexed != prior_session_id
        and _supervisor_launch.canonical_codex_session_id(value=indexed) is not None
    )


def fresh_rollout_live(
    *, sup: Supervisor, track: registry.Track, session: str, prior_session_id: str
) -> bool:
    """True once discovery reports THIS topic on a rollout that is not the prior one.

    Three facts at once, which is why it is the round's post-respawn proof: the topic
    resolves to a live Codex process (so the launch took), the session id DIFFERS from
    the one that was live before the respawn (so the rollout really is new and the
    context window really did reset), and its cwd is inside the repository.
    """
    live = sup.live_codex.get((session, track.topic))
    return (
        live is not None
        and live.session_id != prior_session_id
        and signals.path_in_repo(pane_current_path=live.cwd, repo=track.repo)
    )


def named_successor_rollout(
    *, sup: Supervisor, track: registry.Track, session: str, prior_session_id: str
) -> str | None:
    """The CANONICAL rollout id of the successor this round just named, or None.

    The same two proofs :func:`_named` accepts, asked for the identity rather than for
    a yes/no — the durable index record first, the store-bound live join second — so
    the answer is taken from whichever phase-local evidence actually named the
    successor. It is required to be canonical for the reason every id on this arm is:
    an id that cannot be compared cannot later discriminate the daemon's own successor
    from an unrelated identity change, and a provenance record that cannot be compared
    is worse than none.
    """
    if fresh_rollout_indexed(sup=sup, track=track, prior_session_id=prior_session_id):
        indexed = codex_sessions.latest_session_for_thread_name(
            thread_name=track.topic, codex_home=sup.codex_home
        )
        return _supervisor_launch.canonical_codex_session_id(value=indexed)
    live = sup.live_codex.get((session, track.topic))
    if live is None or not fresh_rollout_live(
        sup=sup, track=track, session=session, prior_session_id=prior_session_id
    ):
        return None
    return _supervisor_launch.canonical_codex_session_id(value=live.session_id)


def record_fresh_restart_attempt(
    *,
    sup: Supervisor,
    track: registry.Track,
    pane: str,
    prior_session_id: str,
    successor: str,
    resume: str,
) -> None:
    """Persist what this attempt launched, so a later tick can finish what it started.

    The tmux session is re-derived here rather than passed in, from the same
    :func:`_supervisor_launch.session_of` the restart itself resolved its target
    through: a provenance record that names a session by some other derivation would
    compare against something the next tick never looks at.
    """
    registry.record_codex_fresh_restart(
        repo=track.repo,
        topic=track.topic,
        record=registry.CodexFreshRestart(
            predecessor=prior_session_id,
            successor=successor,
            tmux=_supervisor_launch.session_of(sup=sup, track=track),
            pane=pane,
            repo=track.repo,
            resume=resume,
            resume_submitted=False,
        ),
        stamp_path=sup.stamp_path,
    )
