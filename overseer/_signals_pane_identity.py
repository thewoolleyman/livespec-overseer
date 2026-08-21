"""Process-identity helpers for tmux pane metadata."""

from __future__ import annotations

import os

__all__: list[str] = ["pane_is_claude", "pane_is_codex", "pane_is_shell", "path_in_repo"]

# A live Claude Code TUI runs as a `node` process; `claude` covers a wrapper.
_CLAUDE_COMMANDS = frozenset({"node", "claude"})
_SHELL_COMMANDS = frozenset({"zsh", "bash", "sh", "fish", "dash", "ksh"})
_CODEX_COMMANDS = frozenset({"codex", "bun"})


def pane_is_claude(*, pane_current_command: str | None) -> bool:
    """True if ``#{pane_current_command}`` looks like a running Claude TUI."""
    cmd = (pane_current_command or "").strip().lower()
    if not cmd:
        return False
    return cmd in _CLAUDE_COMMANDS or "claude" in cmd


def pane_is_codex(*, pane_current_command: str | None) -> bool:
    """True if ``#{pane_current_command}`` could be a Codex TUI.

    DELIBERATELY LOOSE, and safe only in combination. tmux reports a codex pane's
    foreground process as `bun` (the launcher; the vendored `codex` binary is its child),
    and `bun` matches ANY bun app — so this must NEVER gate anything on its own. Two
    callers, both safe: `_is_codex_track` pairs it with an exact live-session-map lookup
    and accepts separate exact argv evidence for ambiguous `node` panes (the map proves
    a real codex session for this topic is in this tmux; the pane read proves the PANE is
    the codex one, not a Claude pane in the same session); and `_do_codex_restart` uses
    it only as the `_await_pane` predicate DIRECTLY AFTER it respawned `codex resume` into
    that exact pane — so "did the codex process come up?" is all it needs to answer, and
    the identity was already established before the restart.
    """
    cmd = (pane_current_command or "").strip().lower()
    return cmd in _CODEX_COMMANDS


def pane_is_shell(*, pane_current_command: str | None) -> bool:
    """True if ``#{pane_current_command}`` is an interactive shell."""
    return (pane_current_command or "").strip().lower() in _SHELL_COMMANDS


def path_in_repo(*, pane_current_path: str | None, repo: str | os.PathLike[str]) -> bool:
    """True if ``#{pane_current_path}`` resolves inside ``repo``.

    Pure path prefix check (``os.path.normpath``, no symlink resolution, no fs
    access) used for the daemon's restart-proof and its auto-link guard (a live
    session is linked to a row only when its cwd is inside the row's repo —
    never by topic name alone, adversarial-review blocker #8).
    """
    if not pane_current_path or not str(repo):
        return False
    current = os.path.normpath(pane_current_path)
    root = os.path.normpath(str(repo))
    return current == root or current.startswith(root + os.sep)
