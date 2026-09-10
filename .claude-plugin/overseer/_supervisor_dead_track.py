"""_supervisor_dead_track — the ONE evidence-bound runtime classifier for a dead track.

Every deliberate dead-track recovery entry point (`supervisor.py start` and the
callable :func:`_supervisor_recovery.recover_missing_sessions`) asks THIS module which
runtime a mapped-but-dead track is, so the two cannot grow competing classifiers that
drift apart. It decides only; the launch mechanics live beside it.

The contract is ``SPECIFICATION/spec.md``: a crashed track whose runtime identity is
ESTABLISHED must be resumed as that runtime, and a target that is ambiguous between
candidate runtimes — or resolvable only by topic-name guessing — must be reported to the
human instead of launched.

**The durable ``observed_session_identity`` is the only accepted evidence.** It is what
the daemon RECORDED while the process was alive (``_supervisor_evaluate_observation``),
so it is exact process evidence that outlived the process. The persisted Codex index is
consulted only to CORROBORATE that recorded identifier — that the index maps the exact
id to this plan topic and that a resumable rollout survives — never to nominate a
candidate of its own.

**Why a topic lookup can never nominate.** The retired recovery path derived the runtime
from the newest global same-topic entry in ``session_index.jsonl``. That is the
stale-namesake defect the specification names outright and ``overseer/AGENTS.md`` records
live: topic ``autonomous-mode`` sat in the Codex index as a six-day-old namesake while the
real track was Claude, so a topic-keyed lookup would have ``codex resume``-d a Claude
track. A same-topic index entry with no recorded identity behind it is therefore AMBIGUOUS
here — reported, never launched.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TypeAlias

import codex_sessions
import registry
from _supervisor_launch import canonical_codex_session_id

__all__: list[str] = [
    "AmbiguousRuntime",
    "ClaudeRuntime",
    "CodexRuntime",
    "DeadTrackRuntime",
    "LaunchableRuntime",
    "classify_dead_track",
]

CLAUDE_IDENTITY_PREFIX = "claude:"
CODEX_IDENTITY_PREFIX = "codex:"


@dataclass(frozen=True, kw_only=True)
class ClaudeRuntime:
    """The track launches as Claude — either evidence-proven, or never launched at all.

    A brand-new mapped plan carries no recorded identity and names no Codex session, so
    it keeps the documented Claude default launch; a track whose recorded identity is a
    ``claude:`` one keeps its proven Claude launch.
    """


@dataclass(frozen=True, kw_only=True)
class CodexRuntime:
    """The track resumes as Codex under ``session_id``, a canonical UUID.

    Reached only when the recorded exact identity, the index's mapping of that exact id
    to this plan topic, and a surviving rollout for it all agree.
    """

    session_id: str


@dataclass(frozen=True, kw_only=True)
class AmbiguousRuntime:
    """The runtime is NOT established. ``reason`` names which evidence failed."""

    reason: str


DeadTrackRuntime: TypeAlias = ClaudeRuntime | CodexRuntime | AmbiguousRuntime
LaunchableRuntime: TypeAlias = ClaudeRuntime | CodexRuntime


def classify_dead_track(
    *, track: registry.Track, codex_home: str | os.PathLike[str] | None
) -> DeadTrackRuntime:
    """Classify a mapped-but-dead ``track`` from durable evidence alone."""
    home = codex_home if codex_home is not None else codex_sessions.default_codex_home()
    identity = track.observed_session_identity
    if identity is None:
        return _without_recorded_identity(track=track, codex_home=home)
    if identity.startswith(CODEX_IDENTITY_PREFIX):
        return _from_codex_identity(
            track=track,
            codex_home=home,
            recorded=identity[len(CODEX_IDENTITY_PREFIX) :],
        )
    if identity.startswith(CLAUDE_IDENTITY_PREFIX):
        return ClaudeRuntime()
    return AmbiguousRuntime(
        reason=(
            f"recorded session identity {identity!r} names no supported runtime, so this "
            "track's runtime cannot be established from evidence"
        )
    )


def _without_recorded_identity(
    *, track: registry.Track, codex_home: str | os.PathLike[str]
) -> DeadTrackRuntime:
    """No durable identity: the Claude default UNLESS a same-topic Codex namesake exists.

    The namesake lookup is a REFUSAL test, never a nomination: a hit means the only way to
    call this track Codex would be to guess from its topic name, which the specification
    forbids, so the track is reported instead of launched under either runtime.
    """
    namesake = codex_sessions.latest_session_for_thread_name(
        thread_name=track.topic, codex_home=codex_home
    )
    if namesake is None:
        return ClaudeRuntime()
    return AmbiguousRuntime(
        reason=(
            f"no durable session identity is recorded, and the Codex index names session "
            f"{namesake} for topic {track.topic!r}; that is a topic-only guess, not "
            "runtime evidence"
        )
    )


def _from_codex_identity(
    *, track: registry.Track, codex_home: str | os.PathLike[str], recorded: str
) -> DeadTrackRuntime:
    """Corroborate a recorded ``codex:<uuid>`` identity against the surviving index."""
    session_id = canonical_codex_session_id(value=recorded)
    if session_id is None:
        return AmbiguousRuntime(
            reason=(
                f"recorded Codex session id {recorded!r} is not a canonical UUID, so "
                "`codex resume` would open its interactive picker instead of resuming"
            )
        )
    indexed = codex_sessions.read_thread_names(codex_home=codex_home).get(session_id)
    if indexed != track.topic:
        return AmbiguousRuntime(
            reason=(
                f"the Codex index maps session {session_id} to {indexed!r}, not to plan "
                f"topic {track.topic!r}; the recorded identifier and the topic disagree"
            )
        )
    if not codex_sessions.rollout_exists(session_id=session_id, codex_home=codex_home):
        return AmbiguousRuntime(
            reason=(
                f"the Codex rollout for session {session_id} is gone, so no resumable "
                f"transcript survives for topic {track.topic!r}"
            )
        )
    return CodexRuntime(session_id=session_id)
