"""Store-bound adoption for live Codex sessions absent from the Codex index."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_codex_identity
import codex_sessions
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "bound_track_for_unindexed_codex",
    "codex_host_readers",
    "codex_sessions_by_tmux_session",
    "store_bound_unindexed_codex_sessions",
    "without_live_recorded_claude",
]


def codex_host_readers(*, sup: Supervisor) -> codex_sessions.CodexHostReaders:
    """The supervisor's injected Codex host seams, as the one bundle the readers take.

    Every Codex read the daemon performs goes through these six, and they are threaded
    end-to-end rather than defaulted so the beside-tests stay hermetic: with the real
    defaults a test would fall through to this host's ``/proc`` and ``~/.codex``.

    ``environ_of`` is the daemon's one environ reader, shared with the Claude side
    rather than given a Codex twin: it answers which Codex home each carrier runs
    under, which is what scopes the host-wide carrier scan.
    """
    return codex_sessions.CodexHostReaders(
        codex_home=sup.codex_home,
        pids_of_comm=sup.codex_pids_of_comm,
        cwd_of=sup.codex_cwd_of,
        fd_targets_of=sup.codex_fd_targets_of,
        children_of=sup.children_of,
        environ_of=sup.environ_of,
        foreground_pgrp_of=sup.codex_foreground_pgrp_of,
    )


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
        ppid_of=sup.ppid_of,
        readers=codex_host_readers(sup=sup),
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


def without_live_recorded_claude(
    *,
    sup: Supervisor,
    sessions: dict[tuple[str, str], codex_sessions.CodexSession],
) -> dict[tuple[str, str], codex_sessions.CodexSession]:
    """Drop every Codex adoption for a pane whose recorded Claude process is still alive.

    A row keeps its recorded Claude identity and launch profile while that process lives
    in the pane, so no other carrier in the pane is adopted for the track, whichever
    source found it.
    """
    live_claude = {
        (track.topic, identity)
        for track in registry.read_valid_mapping(store_path=sup.store_path)
        if (identity := track.observed_session_identity) is not None
    }
    return {
        key: session
        for key, session in sessions.items()
        if (key[1], sup.claude_identity_by_session.get(key)) not in live_claude
    }


def codex_sessions_by_tmux_session(
    *,
    sup: Supervisor,
    pane_pid_to_session: dict[int, str],
) -> dict[tuple[str, str], codex_sessions.CodexSession]:
    """Indexed, store-bound unindexed, and identity-bound Codex sessions, keyed for evaluation.

    The three sources are tried in that order and every one of them only ever
    ``setdefault``s, so a session the rollout-fd join already answers for keeps exactly
    the answer it had. The third source reaches the carriers the first two cannot see at
    all: a Codex 0.16x carrier holding no rollout file descriptor is absent from the
    indexed join AND from the unindexed one, because both ask which rollout THIS process
    holds open (see :mod:`_supervisor_codex_identity`).
    """
    out = codex_sessions.codex_by_tmux_session(
        pane_pid_to_session=pane_pid_to_session,
        ppid_of=sup.ppid_of,
        readers=codex_host_readers(sup=sup),
    )
    for key, session in store_bound_unindexed_codex_sessions(
        sup=sup, pane_pid_to_session=pane_pid_to_session
    ).items():
        _ = out.setdefault(key, session)
    for key, session in _supervisor_codex_identity.identity_bound_codex_sessions(
        sup=sup,
        pane_pid_to_session=pane_pid_to_session,
        readers=codex_host_readers(sup=sup),
    ).items():
        _ = out.setdefault(key, session)
    return without_live_recorded_claude(sup=sup, sessions=out)
