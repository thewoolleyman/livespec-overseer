"""Re-issue Remote Control in tmux panes that lost it to an account switch.

Claude Code stops a Remote Control session as soon as the signed-in account
changes, prints "Remote Control stopped because the signed-in account changed",
and keeps the local session running (Claude Code errors reference). After a
pushed account switch, this sends `/remote-control` to exactly the panes that
show that line, so Remote Control resumes under the new account.

Self-contained and stdlib-only on purpose: the push loop runs it on a listed
host over ssh as `python3 - < remote_control_reissue.py`, where no overseer
package is installed. It prints one JSON line naming the panes it re-issued.

A pane qualifies only when the marker appears AFTER the last `/remote-control`
on its screen, so a pane already re-issued is not sent the command again.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable

__all__: list[str] = ["MARKER", "main", "panes_needing_reissue", "reissue"]

MARKER = "Remote Control stopped because the signed-in account changed"
_COMMAND = "/remote-control"
_TIMEOUT_S = 10

Tmux = Callable[..., str | None]


def _run_tmux(*args: str) -> str | None:
    """Run one tmux command; None on any failure (no server, no binary, hang)."""
    try:
        done = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["tmux", *args],  # noqa: S607 -- tmux resolved on the host's PATH
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def _needs_reissue(*, screen: str) -> bool:
    marker_at = screen.rfind(MARKER)
    return marker_at >= 0 and marker_at > screen.rfind(_COMMAND)


def panes_needing_reissue(*, tmux: Tmux = _run_tmux) -> list[str]:
    """Pane ids whose visible screen shows the account-change stop, not yet re-issued."""
    listing = tmux("list-panes", "-a", "-F", "#{pane_id}")
    if listing is None:
        return []
    found: list[str] = []
    for pane in listing.split():
        screen = tmux("capture-pane", "-p", "-t", pane)
        if screen is not None and _needs_reissue(screen=screen):
            found.append(pane)
    return found


def reissue(*, tmux: Tmux = _run_tmux) -> list[str]:
    """Send `/remote-control` and Enter to every qualifying pane; return those panes."""
    sent: list[str] = []
    for pane in panes_needing_reissue(tmux=tmux):
        if tmux("send-keys", "-t", pane, "-l", _COMMAND) is not None and (
            tmux("send-keys", "-t", pane, "Enter") is not None
        ):
            sent.append(pane)
    return sent


def main(*, tmux: Tmux = _run_tmux) -> int:
    print(json.dumps({"reissued": reissue(tmux=tmux)}))  # noqa: T201 -- the script's one output line
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
