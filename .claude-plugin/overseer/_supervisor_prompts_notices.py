"""Prompt notices and legacy path builders."""

from __future__ import annotations

from pathlib import Path

import signals

__all__: list[str] = [
    "expiry_notice_message",
    "supervisor_epic_path",
    "supervisor_handoff_path",
]

_EXPIRY_NOTICE = """\
Your ready declaration EXPIRED: it stood past its maximum age without a verified
settled-idle observation, so it no longer authorizes a restart.

Declare your state by writing ONE line to the single state file
{state_file} — one of exactly these three values:

Writing that line is the declaration. Pane text, final-response prose, or saying
"Ready for restart" in this conversation is never a declaration channel.

    winding-down                  I got the wind-down message and am wrapping up now.
    ready                         I am at a clean stopping point — restart me.
    blocked: <one-line reason>    I need a human decision I cannot make myself.

A restart requires a fresh ready. The declaration that just expired will not restart
this session; write `ready` again only after you are truly at a clean stopping
point."""


def expiry_notice_message(*, repo: str, topic: str) -> str:
    """The bounded notice sent after a ready declaration expires past its maximum age."""
    return _EXPIRY_NOTICE.format(state_file=str(signals.state_path(repo=repo, topic=topic)))


def supervisor_handoff_path(*, repo: str, topic: str) -> Path:
    """The retired supervisor-handoff artifact path, for legacy certification only.

    Supervise-plan no longer AUTHORS this file: its binder is appended to the plan's
    ledger epic, and supervisor resume prompts now resolve that ledger state directly.
    Existing files can still certify old supervisor restart rounds while live plans are
    migrating. Callers on the daemon's discovery path must never open, read, hash, or
    depend on its content or mtime.
    """
    return Path(repo) / "plan" / topic / "supervisor-handoff.md"


def supervisor_epic_path(*, repo: str, topic: str) -> Path:
    """The migrated plan-shape file that names the governed ledger epic."""
    return Path(repo) / "plan" / topic / "epic.md"
