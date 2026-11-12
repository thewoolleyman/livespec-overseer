"""Re-issue Remote Control in tmux panes that lost it to a pushed account switch.

When the signed-in account changes under a running session on a pushed
credential, Claude Code drops Remote Control and renders the ACCOUNT-CHANGED
NOTICE (NOTICE, taken from Claude Code CLAUDE_CODE_VERSION) inside a longer
line, in one of FORMS: `Remote Control disconnected — <notice>…` in the
transcript, or `Remote Control failed · <notice>…` in the footer. After a pushed
account switch, this sends `/remote-control` to exactly the Claude Code panes
showing it, so Remote Control resumes under the new account. A later Claude Code
that changes the text is a recorded drift from CLAUDE_CODE_VERSION.

Self-contained and stdlib-only on purpose: the push loop runs it on a listed
host over ssh as `python3 -` with this file on stdin, where no overseer package
is installed. It prints one JSON line naming the panes it re-issued.

A pane qualifies only when ALL of these hold:
- its foreground command is Claude Code (`claude`);
- it is not in a tmux mode such as copy mode;
- a line of its joined screen (`capture-pane -p -J`) carries the notice in one
  of FORMS, as part of that line;
- no submitted `/remote-control` prompt line follows the latest such notice;
- its input box is visible and EMPTY: the last `❯` prompt line holds no text,
  and nothing but blank lines sits between it and the box's closing rule. A
  pane holding unsubmitted text is never typed into.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable

__all__: list[str] = [
    "CLAUDE_CODE_VERSION",
    "FORMS",
    "NOTICE",
    "main",
    "panes_needing_reissue",
    "reissue",
]

CLAUDE_CODE_VERSION = "2.1.322"
NOTICE = (
    "signed-in claude.ai account or organization changed on this machine" " — run /remote-control"
)
FORMS = ("Remote Control disconnected — ", "Remote Control failed · ")
_COMMAND = "/remote-control"
_CLAUDE_COMMANDS = frozenset({"claude"})
_PROMPT = "❯"
_RULE = "─"
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


def _shows_notice(*, line: str) -> bool:
    return any(form + NOTICE in line for form in FORMS)


def _input_is_empty(*, lines: list[str]) -> bool:
    """True only when the input box is on screen and holds no text."""
    prompts = [index for index, line in enumerate(lines) if line.startswith(_PROMPT)]
    if not prompts:
        return False
    if lines[prompts[-1]][len(_PROMPT) :].strip():
        return False
    for line in lines[prompts[-1] + 1 :]:
        if line.startswith(_RULE):
            return True
        if line.strip():
            return False
    return False


def _needs_reissue(*, screen: str) -> bool:
    lines = screen.splitlines()
    notices = [index for index, line in enumerate(lines) if _shows_notice(line=line)]
    if not notices or not _input_is_empty(lines=lines):
        return False
    return _COMMAND not in [_bare(line=line) for line in lines[notices[-1] + 1 :]]


def panes_needing_reissue(*, tmux: Tmux = _run_tmux) -> list[str]:
    """Claude Code pane ids showing the account-changed notice with an empty input box."""
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
