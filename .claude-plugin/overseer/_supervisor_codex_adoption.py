"""Store-bound adoption for live Codex sessions absent from the Codex index."""

from __future__ import annotations

from typing import TYPE_CHECKING

import codex_sessions
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "bound_track_for_unindexed_codex",
    "codex_sessions_by_tmux_session",
    "store_bound_unindexed_codex_sessions",
]


def bound_track_for_unindexed_codex(
    *, sup: Supervisor, session: codex_sessions.UnindexedCodexSession
) -> registry.Track | None:
    """The single mapping row that explicitly binds this unindexed Codex tmux session.

    This is deliberately narrower than guessing from a repo cwd or a topic-like tmux
    name. The operator-authored mapping store must already name the tmux session, and
    the live Codex process cwd must sit inside that mapped repo. If two rows claim the
    same tmux session in the same repo, the evidence is ambiguous and remains diagnostic.
    """
    matches = [
        track
        for track in registry.read_valid_mapping(store_path=sup.store_path)
        if track.tmux == session.tmux_session
        and signals.path_in_repo(pane_current_path=session.cwd, repo=track.repo)
    ]
    return matches[0] if len(matches) == 1 else None


def store_bound_unindexed_codex_sessions(
    *,
    sup: Supervisor,
    pane_pid_to_session: dict[int, str],
) -> dict[tuple[str, str], codex_sessions.CodexSession]:
    """Adopt unindexed Codex sessions only when the mapping store already binds them."""
    out: dict[tuple[str, str], codex_sessions.CodexSession] = {}
    for session in codex_sessions.map_unindexed_codex_sessions(
        pane_pid_to_session=pane_pid_to_session,
        codex_home=sup.codex_home,
        ppid_of=sup.ppid_of,
        pids_of_comm=sup.codex_pids_of_comm,
        cwd_of=sup.codex_cwd_of,
        fd_targets_of=sup.codex_fd_targets_of,
    ):
        track = bound_track_for_unindexed_codex(sup=sup, session=session)
        if track is None:
            continue
        out[(session.tmux_session, track.topic)] = codex_sessions.CodexSession(
            pid=session.pid,
            name=track.topic,
            cwd=session.cwd,
            session_id=session.session_id,
        )
    return out


def codex_sessions_by_tmux_session(
    *,
    sup: Supervisor,
    pane_pid_to_session: dict[int, str],
) -> dict[tuple[str, str], codex_sessions.CodexSession]:
    """Indexed Codex sessions plus store-bound unindexed sessions, keyed for evaluation."""
    out = codex_sessions.codex_by_tmux_session(
        pane_pid_to_session=pane_pid_to_session,
        codex_home=sup.codex_home,
        ppid_of=sup.ppid_of,
        pids_of_comm=sup.codex_pids_of_comm,
        cwd_of=sup.codex_cwd_of,
        fd_targets_of=sup.codex_fd_targets_of,
    )
    for key, session in store_bound_unindexed_codex_sessions(
        sup=sup, pane_pid_to_session=pane_pid_to_session
    ).items():
        _ = out.setdefault(key, session)
    return out
