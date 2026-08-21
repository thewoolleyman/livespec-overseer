"""Data models for live Codex session discovery."""

from __future__ import annotations

from dataclasses import dataclass

__all__: list[str] = ["CODEX_COMM", "CodexSession", "UnindexedCodexSession"]

# `#{pane_current_command}` / `/proc/<pid>/comm` for a real Codex TUI. The launcher is
# `bun` (`~/.bun/bin/codex`), which EXECS the vendored binary; verified live, the `bun`
# process is the codex process's PARENT and holds NO rollout fd, so requiring an open
# rollout (below) excludes it structurally — this name matches only the real thing.
CODEX_COMM = "codex"


@dataclass(frozen=True, kw_only=True)
class CodexSession:
    """One live, NAMED Codex TUI session, joined to its plan topic.

    Mirrors :class:`claude_sessions.ClaudeSession` field-for-field where the two
    runtimes agree, so adoption can consume either. ``name`` is the index
    ``thread_name`` and carries the same meaning as Claude's registry ``name``: the
    plan topic. There is no ``status`` twin — Codex self-reports nothing, so busy
    detection falls back to the process-tree shell-walk
    (``claude_sessions.has_active_subshell``), which exists for exactly this case.
    """

    pid: int
    name: str
    cwd: str
    session_id: str


@dataclass(frozen=True, kw_only=True)
class UnindexedCodexSession:
    """One live Codex process with a rollout id that has no index name.

    This is not adoptable: without ``thread_name`` there is no plan topic to match.
    It is still useful process evidence for the supervisor to show the operator when
    it occurs inside a watched repo.
    """

    pid: int
    cwd: str
    session_id: str
    tmux_session: str
