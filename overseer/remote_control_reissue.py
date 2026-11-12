"""Re-issue Remote Control in tmux panes that lost it to an account switch.

When the signed-in account changes, Claude Code stops Remote Control, keeps the
local session running, and shows NOTICE (the string in the Claude Code 2.1.322
binary). After a pushed account switch, this sends `/remote-control` to exactly
the Claude Code panes showing that notice, so Remote Control resumes under the
new account.

Self-contained and stdlib-only on purpose: the push loop runs it on a listed
host over ssh as `python3 - < remote_control_reissue.py`, where no overseer
package is installed. It prints one JSON line naming the panes it re-issued.

A pane qualifies only when ALL of these hold:
- its foreground command is Claude Code (`claude`);
- it is not in a tmux mode such as copy mode;
- the notice is a whole line of its joined screen (`capture-pane -p -J`), after
  leading box or glyph characters are stripped;
- no submitted `/remote-control` prompt line follows that notice.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable

__all__: list[str] = ["NOTICE", "main", "panes_needing_reissue", "reissue"]

NOTICE = (
    "Remote Control stopped — the app running this session is now signed in"
    " to a different Claude account"
)
_COMMAND = "/remote-control"
_CLAUDE_COMMANDS = frozenset({"claude"})
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


def _bare(*, line: str) -> str:
    """The line without leading box/glyph characters or surrounding whitespace."""
    start = 0
    while start < len(line) and not (line[start].isalnum() or line[start] == "/"):
        start += 1
    return line[start:].rstrip()


def _needs_reissue(*, screen: str) -> bool:
    lines = [_bare(line=line) for line in screen.splitlines()]
    notices = [index for index, line in enumerate(lines) if line == NOTICE]
    if not notices:
        return False
    return _COMMAND not in lines[notices[-1] + 1 :]


def panes_needing_reissue(*, tmux: Tmux = _run_tmux) -> list[str]:
    """Claude Code pane ids showing the account-change notice, not yet re-issued."""
    listing = tmux("list-panes", "-a", "-F", "#{pane_id} #{pane_current_command} #{pane_in_mode}")
    if listing is None:
        return []
    found: list[str] = []
    for row in listing.splitlines():
        pane, command, in_mode = [*row.split(), "", "", ""][:3]
        if command not in _CLAUDE_COMMANDS or in_mode != "0":
            continue
        screen = tmux("capture-pane", "-p", "-J", "-t", pane)
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
