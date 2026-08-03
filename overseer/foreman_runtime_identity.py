"""Entry and identity gates for the per-repo foreman runtime."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import registry
from _claude_sessions_registry import ClaudeSession

__all__: list[str] = ["EntryGateResult", "canonical_session_name", "entry_gate"]


class _SessionExists(Protocol):
    def session_exists(self, *, session: str) -> bool: ...


@dataclass(frozen=True, kw_only=True)
class EntryGateResult:
    ok: bool
    session_name: str
    reason: str | None = None


def canonical_session_name(*, repo: str | os.PathLike[str]) -> str:
    return f"{registry.repo_slug(repo=repo)}-foreman"


def _repo_key(*, repo: str | os.PathLike[str]) -> str:
    return registry.norm(repo=Path(repo).resolve())


def _watch_set_repos(*, watch_set_path: Path) -> list[str]:
    return [
        registry.norm(repo=Path(repo).resolve())
        for repo in registry.watch_set_from_config(config_path=watch_set_path)
    ]


def _registry_matches(*, repo: Path, session_name: str, sessions: Sequence[ClaudeSession]) -> bool:
    repo_key = _repo_key(repo=repo)
    return any(
        session.name == session_name and _repo_key(repo=session.cwd) == repo_key
        for session in sessions
    )


def entry_gate(
    *,
    repo: str | os.PathLike[str],
    cwd: str | os.PathLike[str],
    watch_set_path: str | os.PathLike[str],
    tmux: _SessionExists,
    sessions: Sequence[ClaudeSession],
) -> EntryGateResult:
    repo_path = Path(repo).resolve()
    session_name = canonical_session_name(repo=repo_path)
    if _repo_key(repo=cwd) != _repo_key(repo=repo_path):
        return EntryGateResult(ok=False, session_name=session_name, reason="cwd is not repo")
    watched = _watch_set_repos(watch_set_path=Path(watch_set_path))
    if not watched or _repo_key(repo=repo_path) not in watched:
        return EntryGateResult(ok=False, session_name=session_name, reason="repo not in watch set")
    if not tmux.session_exists(session=session_name):
        return EntryGateResult(ok=False, session_name=session_name, reason="tmux session missing")
    if not _registry_matches(repo=repo_path, session_name=session_name, sessions=sessions):
        return EntryGateResult(
            ok=False, session_name=session_name, reason="runtime registry mismatch"
        )
    return EntryGateResult(ok=True, session_name=session_name)
