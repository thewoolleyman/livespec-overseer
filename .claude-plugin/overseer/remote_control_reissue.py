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
- its input box is visible and EMPTY: the last `❯` prompt line, between two
  `─` rules, holds no text and only blank lines precede the closing rule. A
  pane holding unsubmitted text is never typed into;
- EITHER a transcript line above the box begins, right behind `⎿` and
  indentation only, with `Remote Control disconnected — ` + NOTICE, and no
  submitted `/remote-control` line follows it; OR a footer line below the box
  begins, behind indentation only, with `Remote Control failed · ` + NOTICE.
  Lines Ink hard-wrapped on a narrow pane are rejoined when indented to the
  column the text began at. The form quoted anywhere else never matches.
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
_TRANSCRIPT_MARK = "⎿"
_RULE = "─"
_TIMEOUT_S = 10
_WRAP_LINES = 6

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


def _starts_notice(*, lines: list[str], index: int, mark: str, form: str) -> bool:
    """`form` + NOTICE begins this line right behind `mark` and indentation only.

    Ink hard-wraps a long line at spaces on a narrow pane, indenting each
    continuation to the column where the text began; `capture-pane -J` joins
    only tmux's own soft wraps. So only following lines indented to exactly
    that column are rejoined, with whitespace collapsed, before comparing.
    """
    line = lines[index]
    body = line.lstrip(" ")
    if not body.startswith(mark):
        return False
    text = body[len(mark) :].lstrip(" ")
    if not text.startswith(form):
        return False
    column = len(line) - len(text)
    parts = [text]
    for following in lines[index + 1 : index + _WRAP_LINES]:
        if not following.strip() or len(following) - len(following.lstrip(" ")) != column:
            break
        parts.append(following.strip())
    return _collapsed(text=" ".join(parts)).startswith(_collapsed(text=form + NOTICE))


def _needs_reissue(*, screen: str) -> bool:
    lines = screen.splitlines()
    box = _empty_box(lines=lines)
    if box is None:
        return False
    top, bottom = box
    transcript = [
        index
        for index in range(top)
        if _starts_notice(lines=lines, index=index, mark=_TRANSCRIPT_MARK, form=FORMS[0])
    ]
    if transcript:
        later = [_bare(line=line) for line in lines[transcript[-1] + 1 : top]]
        return _COMMAND not in later
    return any(
        _starts_notice(lines=lines, index=index, mark="", form=FORMS[1])
        for index in range(bottom + 1, len(lines))
    )


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
