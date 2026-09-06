"""Prompt notices and legacy path builders."""

from __future__ import annotations

from pathlib import Path

import signals

__all__: list[str] = [
    "busy_blocker_callout",
    "expiry_notice_message",
    "supervisor_epic_path",
    "supervisor_handoff_path",
]


def busy_blocker_callout(*, blocker: str | None) -> str:
    """A leading callout naming the concrete busy evidence that is blocking a restart.

    Returns "" when the daemon holds NO such evidence, so the message is unchanged — the
    blocker line is never invented. When it DOES hold evidence, the wrap-up and the
    ready-expiry notice are the daemon's only lever (nothing is force-restarted), so they
    must point at the real obstacle: a session that believes it is at a clean stopping
    point otherwise re-declares ``ready`` in a loop that can never certify while the
    blocker holds the restart interlock open.

    This does NOT weaken the cardinal rule — it names a fact the daemon already knows and
    tells the session to clear it; the daemon still restarts on nothing but a fresh
    certifiable ``ready``.
    """
    if blocker is None:
        return ""
    return (
        f"BLOCKING YOUR RESTART RIGHT NOW: {blocker}. A `ready` declaration cannot certify "
        "for restart while this is live — the overseer never kills a session with "
        "background work still running under its pane — so declaring `ready` now only "
        "loops until the declaration expires. Reap it FIRST, then declare.\n\n"
    )


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


def expiry_notice_message(*, repo: str, topic: str, blocker: str | None = None) -> str:
    """The bounded notice sent after a ready declaration expires past its maximum age.

    ``blocker`` names the concrete busy evidence the daemon holds for this track when the
    notice fires (see :func:`busy_blocker_callout`); it is prepended as a leading callout
    so the session reaps the real obstacle instead of re-declaring ``ready`` into the
    ready -> expire loop this repair exists to break.
    """
    body = _EXPIRY_NOTICE.format(state_file=str(signals.state_path(repo=repo, topic=topic)))
    return f"{busy_blocker_callout(blocker=blocker)}{body}"


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
