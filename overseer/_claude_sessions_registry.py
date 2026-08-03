"""Claude Code registry-file parsing for live named sessions.

``adopt`` must learn each running worker's topic from its Claude Code display
name. That name is not reliably present in argv because maintained sessions can
run as ``claude --dangerously-skip-permissions`` and be renamed later with
``/rename``; screen-scraping the input-box border also fails whenever the pane
shows a prompt instead of the box (verified live 2026-07-13).

The robust source is Claude Code's per-session registry file at
``~/.claude/sessions/<pid>.json``. Its shape includes the process identity and
metadata this package needs, for example ``{"pid": 1067963, "cwd":
"/data/projects/livespec", "name": "driver-hook-body", "status": "idle",
"procStart": "34092476"}``. This module keeps only parseable, named entries
whose live ``/proc/<pid>/stat`` start-time still equals ``procStart``; that
filters dead sessions and defends against PID reuse.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from _claude_sessions_proc import proc_starttime
from _seams import PidToOptionalStr

__all__: list[str] = [
    "ClaudeSession",
    "default_sessions_dir",
    "read_live_sessions",
]


@dataclass(frozen=True, kw_only=True)
class ClaudeSession:
    """One live, named Claude Code session from the registry."""

    pid: int
    name: str
    cwd: str
    status: str  # Claude's own live self-report: "busy" / "idle" / "waiting" (or "" if absent)
    proc_start: str
    # How the display name was set. Claude writes "derived" when it AUTO-named the
    # session from the repo directory (`livespec-overseer-01`); a session launched
    # with an explicit `-n <topic>` carries no such marker. That distinction is the
    # only thing separating "this is our track, merely misnamed" (overseer-j1r) from
    # "this is a DIFFERENT topic's session in a reused window" (R2/SF5) — by name
    # alone the two are indistinguishable. Absent ⇒ "" (explicitly named).
    name_source: str = ""


def default_sessions_dir() -> Path:
    """``~/.claude/sessions`` — where Claude Code writes ``<pid>.json`` per session."""
    return Path.home() / ".claude" / "sessions"


def read_live_sessions(
    *,
    sessions_dir: str | os.PathLike[str],
    starttime_of: PidToOptionalStr = proc_starttime,
) -> list[ClaudeSession]:
    """Every LIVE, named session in the registry dir.

    A file qualifies only when it parses, carries a non-empty ``name`` + ``cwd`` +
    integer ``pid``, and its ``procStart`` equals the process's current
    ``/proc`` start-time (``starttime_of(pid)``) — so a stale file for a dead PID,
    or one whose PID has been reused by an unrelated process, is dropped
    (fail-soft: any bad/unreadable file is skipped, never raised).
    """
    directory = Path(sessions_dir)
    out: list[ClaudeSession] = []
    try:
        files = sorted(directory.glob("*.json"))
    except OSError:
        return out
    for file in files:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pid = data.get("pid")
        name = data.get("name")
        name_source = data.get("nameSource")
        cwd = data.get("cwd")
        proc_start = data.get("procStart")
        status = data.get("status")
        if not isinstance(pid, int) or not isinstance(name, str) or not isinstance(cwd, str):
            continue
        if not name or not cwd or proc_start is None:
            continue
        if starttime_of(pid=pid) != str(proc_start):
            continue  # dead PID, or reused by an unrelated process
        out.append(
            ClaudeSession(
                pid=pid,
                name=name,
                cwd=cwd,
                status=status if isinstance(status, str) else "",
                proc_start=str(proc_start),
                name_source=name_source if isinstance(name_source, str) else "",
            )
        )
    return out
