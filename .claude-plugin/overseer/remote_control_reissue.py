"""Re-issue Remote Control in tmux panes that lost it to a pushed account switch.

When the signed-in account changes under a running session on a pushed
credential, Claude Code drops Remote Control and shows it in one of FORMS, as a
real account switch under CLAUDE_CODE_VERSION showed (spec v099, contracts.md
"Remote Control re-issue"): a transcript line `Remote Control disconnected — `
+ NOTICE + `…` behind the transcript's status mark, or the footer status
`/rc failed` below the input box. After a pushed account switch, this sends
`/remote-control` to exactly the Claude Code panes showing either form, so
Remote Control resumes under the new account. A later Claude Code that changes
either form is a recorded drift from CLAUDE_CODE_VERSION.

Self-contained and stdlib-only on purpose: the push loop runs it on a listed
host over ssh as `python3 -` with this file on stdin, where no overseer package
is installed. It prints one JSON line naming the panes it re-issued.

A pane qualifies only when ALL of these hold:
- its foreground process is Claude Code, judged by the executable that process
  runs: basename `claude`, or a path under `~/.local/share/claude/versions/`.
  tmux's current-command name is never consulted, because Claude Code 2.1.323
  reports its version number (`2.1.323`) there;
- it is not in a tmux mode such as copy mode;
- its input box is visible and EMPTY: the last `❯` prompt line, between two
  `─` rules, holds no text and only blank lines precede the closing rule. A
  pane holding unsubmitted text is never typed into;
- EITHER a transcript line above the box begins, right behind a transcript
  status mark (`●`, or 2.1.322's `⎿`) and indentation only, with
  `Remote Control disconnected — ` + NOTICE, and no submitted `/remote-control`
  line follows it; OR a footer line below the box carries `/rc failed` as a
  whole item.
  Lines Ink hard-wrapped on a narrow pane are rejoined when indented to the
  column the text began at, and the comparison runs on the rejoined text. Only a
  `❯` prompt line AFTER the whole notice block counts as a submitted
  `/remote-control`. The form quoted anywhere else never matches.
"""

from __future__ import annotations

import itertools
import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path

__all__: list[str] = [
    "CLAUDE_CODE_VERSION",
    "FORMS",
    "NOTICE",
    "main",
    "panes_needing_reissue",
    "reissue",
]

CLAUDE_CODE_VERSION = "2.1.323"
NOTICE = (
    "signed-in claude.ai account or organization changed on this machine" " — run /remote-control"
)
FORMS = ("Remote Control disconnected — ", "/rc failed")
_COMMAND = "/remote-control"
_CLAUDE_BASENAME = "claude"
_VERSIONS_DIR = Path(".local", "share", "claude", "versions")
_PROMPT = "❯"
_TRANSCRIPT_MARKS = ("●", "⎿")
_FOOTER_STATUS = re.compile(r"(?:^|\s)" + re.escape(FORMS[1]) + r"(?:\s|$)")
_RULE = "─"
_TIMEOUT_S = 10

Tmux = Callable[..., str | None]
Ps = Callable[..., str | None]


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


def _run_ps(*, tty: str) -> str | None:
    """`stat args` of every process on one pane's tty; None on any failure."""
    try:
        done = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["ps", "-o", "stat=,args=", "-t", tty.removeprefix("/dev/")],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def _is_claude(*, executable: str) -> bool:
    """Claude Code's executable: basename `claude`, or under its versions directory."""
    path = Path(executable)
    return path.name == _CLAUDE_BASENAME or path.is_relative_to(Path.home() / _VERSIONS_DIR)


def _foreground_is_claude(*, tty: str, ps: Ps) -> bool:
    """Whether a process in the tty's foreground group (`+` in its stat) is Claude Code."""
    listing = ps(tty=tty)
    if listing is None:
        return False
    for row in listing.splitlines():
        stat, _, args = row.strip().partition(" ")
        words = args.split()
        if "+" in stat and words and _is_claude(executable=words[0]):
            return True
    return False


def _collapsed(*, text: str) -> str:
    return " ".join(text.split())


def _empty_box(*, lines: list[str]) -> tuple[int, int] | None:
    """The input box's (top rule, closing rule) indexes, only when the box is EMPTY.

    The box is the last `❯` prompt line between two `─` rules. It is empty when
    the prompt line holds no text and only blank lines sit before the closing
    rule; anything else, including no box on screen, is None.
    """
    prompts = [index for index, line in enumerate(lines) if line.startswith(_PROMPT)]
    if not prompts or lines[prompts[-1]][len(_PROMPT) :].strip():
        return None
    prompt = prompts[-1]
    tops = [index for index in range(prompt) if lines[index].startswith(_RULE)]
    if not tops:
        return None
    for index in range(prompt + 1, len(lines)):
        if lines[index].startswith(_RULE):
            return tops[-1], index
        if lines[index].strip():
            return None
    return None


def _notice_block_end(*, lines: list[str], index: int) -> int | None:
    """The index past the notice block starting here, or None when none starts here.

    A block begins with a line holding a transcript mark behind indentation only, and
    continues through the following lines indented to exactly the column where
    its text began: Ink hard-wraps a long line at spaces on a narrow pane and
    indents each continuation that way, while `capture-pane -J` joins only tmux's
    own soft wraps. The block is a notice when its rejoined text, whitespace
    collapsed, begins with the transcript form + NOTICE, so a wrap anywhere
    inside the form or the notice still matches.
    """
    line = lines[index]
    body = line.lstrip(" ")
    mark = next((mark for mark in _TRANSCRIPT_MARKS if body.startswith(mark)), None)
    if mark is None:
        return None
    text = body[len(mark) :].lstrip(" ")
    column = len(line) - len(text)
    continuation = list(
        itertools.takewhile(
            lambda row: bool(row.strip()) and len(row) - len(row.lstrip(" ")) == column,
            lines[index + 1 :],
        )
    )
    joined = _collapsed(text=" ".join([text, *(row.strip() for row in continuation)]))
    stop = index + 1 + len(continuation)
    return stop if joined.startswith(_collapsed(text=FORMS[0] + NOTICE)) else None


def _submitted(*, line: str) -> bool:
    """A transcript prompt line showing `/remote-control` as submitted."""
    return line.startswith(_PROMPT) and line[len(_PROMPT) :].strip() == _COMMAND


def _needs_reissue(*, screen: str) -> bool:
    lines = screen.splitlines()
    box = _empty_box(lines=lines)
    if box is None:
        return False
    top, bottom = box
    ends = [
        end
        for index in range(top)
        if (end := _notice_block_end(lines=lines, index=index)) is not None
    ]
    if ends:
        return not any(_submitted(line=line) for line in lines[ends[-1] : top])
    return any(_FOOTER_STATUS.search(line) for line in lines[bottom + 1 :])


def panes_needing_reissue(*, tmux: Tmux = _run_tmux, ps: Ps = _run_ps) -> list[str]:
    """Claude Code pane ids showing the account-changed notice with an empty input box."""
    listing = tmux("list-panes", "-a", "-F", "#{pane_id} #{pane_tty} #{pane_in_mode}")
    if listing is None:
        return []
    found: list[str] = []
    for row in listing.splitlines():
        pane, tty, in_mode = [*row.split(), "", "", ""][:3]
        if in_mode != "0" or not _foreground_is_claude(tty=tty, ps=ps):
            continue
        screen = tmux("capture-pane", "-p", "-J", "-t", pane)
        if screen is not None and _needs_reissue(screen=screen):
            found.append(pane)
    return found


def reissue(*, tmux: Tmux = _run_tmux, ps: Ps = _run_ps) -> list[str]:
    """Send `/remote-control` and Enter to every qualifying pane; return those panes."""
    sent: list[str] = []
    for pane in panes_needing_reissue(tmux=tmux, ps=ps):
        if tmux("send-keys", "-t", pane, "-l", _COMMAND) is not None and (
            tmux("send-keys", "-t", pane, "Enter") is not None
        ):
            sent.append(pane)
    return sent


def main(*, tmux: Tmux = _run_tmux, ps: Ps = _run_ps) -> int:
    print(json.dumps({"reissued": reissue(tmux=tmux, ps=ps)}))  # noqa: T201 -- the script's one output line
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
