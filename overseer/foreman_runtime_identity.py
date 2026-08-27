"""Entry and identity gates for the per-repo foreman runtime."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import registry
from _signals_topics import foreman_topic

__all__: list[str] = [
    "EntryGateResult",
    "RuntimeEvidence",
    "canonical_session_name",
    "entry_gate",
]


class _SessionExists(Protocol):
    def session_exists(self, *, session: str) -> bool: ...


class _RuntimeIdentity(Protocol):
    """The identity fields the entry gate needs from ONE live runtime session.

    Deliberately the SMALLEST shape that answers the gate's question — the exact
    display name and the exact repository cwd — so Claude registry evidence
    (``_claude_sessions_registry.ClaudeSession``), Codex rollout-join evidence
    (``_codex_session_models.CodexSession``) and Pi active-session evidence
    (``pi_sessions.PiSession``) all satisfy it as they already stand.
    Generalizing the SHAPE rather than the CHECK is what keeps the exact
    name-plus-repository identity test byte-for-byte the same for every runtime;
    a runtime-branching gate could drift into admitting one on weaker evidence.
    """

    @property
    def name(self) -> str: ...

    @property
    def cwd(self) -> str: ...


@dataclass(frozen=True, kw_only=True)
class RuntimeEvidence:
    """Live identity evidence, one already-read field per runtime that can supply it.

    The three fields carry the SAME shape and are aggregated identically; the split is
    provenance, so a caller wires each reader explicitly and a missing one is visibly
    missing rather than silently folded into another runtime's list. All default empty
    and the whole carrier defaults empty, so evidence must be supplied to be admitted.

    Carrying them TOGETHER rather than as three parameters is what stops the gate's
    signature growing by one every time the fleet gains a runtime — the growth this
    replaced, at the third one. It also puts the "which runtime supplied it is not the
    gate's business" rule in the type rather than only in the prose below.
    """

    sessions: Sequence[_RuntimeIdentity] = ()
    codex_sessions: Sequence[_RuntimeIdentity] = ()
    pi_sessions: Sequence[_RuntimeIdentity] = ()

    def identities(self) -> tuple[_RuntimeIdentity, ...]:
        """Every supplied identity, in runtime order — the gate's only read of this."""
        return (*self.sessions, *self.codex_sessions, *self.pi_sessions)


@dataclass(frozen=True, kw_only=True)
class EntryGateResult:
    ok: bool
    session_name: str
    reason: str | None = None


def canonical_session_name(*, repo: str | os.PathLike[str]) -> str:
    return foreman_topic(repo_slug=registry.repo_slug(repo=repo))


def _repo_key(*, repo: str | os.PathLike[str]) -> str:
    return registry.norm(repo=Path(repo).resolve())


def _watch_set_repos(*, watch_set_path: Path) -> list[str]:
    return [
        registry.norm(repo=Path(repo).resolve())
        for repo in registry.watch_set_from_config(config_path=watch_set_path)
    ]


def _identity_matches(
    *, repo: Path, session_name: str, identities: Sequence[_RuntimeIdentity]
) -> bool:
    repo_key = _repo_key(repo=repo)
    return any(
        identity.name == session_name and _repo_key(repo=identity.cwd) == repo_key
        for identity in identities
    )


def entry_gate(
    *,
    repo: str | os.PathLike[str],
    cwd: str | os.PathLike[str],
    watch_set_path: str | os.PathLike[str],
    tmux: _SessionExists,
    evidence: RuntimeEvidence,
) -> EntryGateResult:
    """Admit a foreman seat only on live, exactly-matching runtime identity evidence.

    ``evidence`` carries Claude registry evidence, the live Codex evidence a caller
    reads from ``codex_sessions.read_live_codex_sessions()``, and the live Pi evidence
    from ``pi_sessions.read_live_pi_sessions()``. They are AGGREGATED rather than tried
    in turn: a seat needs one live identity carrying the canonical session name in this
    exact repository, and which runtime supplied it is not the gate's business. Every
    field defaults empty and fails closed, so a caller that supplies no evidence at all
    is refused rather than waved through.

    Evidence must arrive already read: this module deliberately duplicates no process
    scan, no rollout discovery and no session-file read, and it accepts no session its
    reader declined to name — an unindexed Codex session and a Pi invocation lacking
    the injected session variables are both dropped before the gate ever sees them.
    That is what keeps "a session with no name has no topic" a property of each join
    rather than a policy here.
    """
    repo_path = Path(repo).resolve()
    session_name = canonical_session_name(repo=repo_path)
    if _repo_key(repo=cwd) != _repo_key(repo=repo_path):
        return EntryGateResult(ok=False, session_name=session_name, reason="cwd is not repo")
    watched = _watch_set_repos(watch_set_path=Path(watch_set_path))
    if not watched or _repo_key(repo=repo_path) not in watched:
        return EntryGateResult(ok=False, session_name=session_name, reason="repo not in watch set")
    if not tmux.session_exists(session=session_name):
        return EntryGateResult(ok=False, session_name=session_name, reason="tmux session missing")
    if not _identity_matches(
        repo=repo_path, session_name=session_name, identities=evidence.identities()
    ):
        return EntryGateResult(
            ok=False, session_name=session_name, reason="runtime registry mismatch"
        )
    return EntryGateResult(ok=True, session_name=session_name)
