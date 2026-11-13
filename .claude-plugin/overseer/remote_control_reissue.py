"""Re-issue Remote Control in herdr and tmux panes that lost it to a pushed account switch.

When the signed-in account changes under a running session on a pushed
credential, Claude Code drops Remote Control and shows it in one of FORMS, as a
real account switch under CLAUDE_CODE_VERSION showed (spec v103, contracts.md
"Remote Control re-issue"): a transcript line `Remote Control disconnected — `
+ NOTICE + `…` behind the transcript's status mark, or the footer status
`/rc failed` below the input box. After a pushed account switch, this sends
`/remote-control` to exactly the Claude Code panes showing either form, so
Remote Control resumes under the new account. A later Claude Code that changes
either form is a recorded drift from CLAUDE_CODE_VERSION.

Self-contained and stdlib-only on purpose: the push loop runs it on a listed
host over ssh as `python3 -` with this file on stdin, where no overseer package
is installed. It prints one JSON line naming the panes it re-issued: a tmux pane
by its id (`%3`), a herdr pane as `herdr:<session>:<pane id>`.

The panes are those of the host's terminal multiplexer (spec v103): every pane of
every RUNNING herdr session, plus every tmux pane. The fleet runs herdr; tmux
stays because it costs one listing. herdr is driven through its own CLI, the
same client an operator types, because this file cannot import the overseer's
socket client (`herdr_transport`) on a host that has no overseer package. The
replies it reads are the shapes `herdr_calls` measured: `result.panes[]`,
`result.process_info.foreground_processes[]`, and the `Enter` key name. A pane
is captured with `pane read --source recent-unwrapped`, herdr's capture with
soft wraps joined, limited to the pane's viewport rows: the counterpart of
`tmux capture-pane -p -J`.

A pane qualifies only when ALL of these hold:
- its foreground process is Claude Code, judged by the executable that process
  runs: basename `claude`, or a path under `~/.local/share/claude/versions/`.
  The multiplexer's current-command or process name is never consulted,
  because Claude Code 2.1.323 reports its version number (`2.1.323`) there;
- it is not in a mode that takes over the pane: a tmux mode such as copy mode,
  or a herdr pane scrolled back from its bottom;
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

Every pane is re-read and re-checked immediately before its own send, so a box
a human started typing into during the scan of the other panes is left alone.
The panes are re-scanned every _RESCAN_S seconds over a window of _WINDOW_S
(the script's one optional argument; 0 makes one scan), because a host is
scanned as soon as it applies the delivery and Claude Code may not have drawn
the notice yet. A pane is sent to at most once per run.
"""

# livespec-lloc-soft-band-owner: overseer-9l63

from __future__ import annotations

import itertools
import json
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

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
_HERDR = "herdr"
_HERDR_FALLBACK = Path(".local", "bin", _HERDR)
_HERDR_SOURCE = "recent-unwrapped"
_ENTER = "Enter"
_WINDOW_S = 90.0
_RESCAN_S = 10.0

Tmux = Callable[..., str | None]
Ps = Callable[..., str | None]
Herdr = Callable[..., str | None]


def _run(*, argv: list[str]) -> str | None:
    """Run one command; None on any failure (no binary, no server, hang, nonzero exit)."""
    try:
        done = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            argv, capture_output=True, text=True, timeout=_TIMEOUT_S, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def _run_tmux(*args: str) -> str | None:
    return _run(argv=["tmux", *args])


def _run_ps(*, tty: str) -> str | None:
    """`stat args` of every process on one pane's tty."""
    return _run(argv=["ps", "-o", "stat=,args=", "-t", tty.removeprefix("/dev/")])


def _herdr_binary() -> str | None:
    """herdr on PATH, else the installer's `~/.local/bin/herdr`: a non-login ssh PATH lacks it."""
    fallback = Path.home() / _HERDR_FALLBACK
    return shutil.which(_HERDR) or (str(fallback) if fallback.is_file() else None)


def _run_herdr(*args: str) -> str | None:
    binary = _herdr_binary()
    return None if binary is None else _run(argv=[binary, *args])


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


def _at(*, value: object, path: tuple[str, ...]) -> object:
    """`value[path[0]][path[1]]...` of a parsed reply, None where a step is not an object."""
    for key in path:
        value = cast("dict[str, object]", value).get(key) if isinstance(value, dict) else None
    return value


def _list(*, value: object) -> list[object]:
    return value if isinstance(value, list) else []  # pyright: ignore[reportUnknownVariableType]


def _items(*, text: str | None, path: tuple[str, ...]) -> list[object]:
    """The list at `path` in one herdr CLI JSON reply; empty when unreadable."""
    try:
        return _list(value=_at(value=json.loads(text or ""), path=path))
    except ValueError:
        return []


def _count(*, value: object) -> int:
    """A JSON integer, or -1 for anything else (`true` included)."""
    return value if type(value) is int else -1


def _herdr_sessions(*, herdr: Herdr) -> list[str]:
    """The names of the host's RUNNING herdr sessions; a stopped one has no panes to reach."""
    rows = _items(text=herdr("session", "list", "--json"), path=("sessions",))
    names = [
        _at(value=row, path=("name",)) for row in rows if _at(value=row, path=("running",)) is True
    ]
    return [name for name in names if isinstance(name, str)]


def _herdr_viewports(*, herdr: Herdr, session: str) -> list[tuple[str, int]]:
    """(pane id, viewport rows) of each pane at its bottom; a scrolled-back pane is skipped."""
    found: list[tuple[str, int]] = []
    for row in _items(text=herdr("--session", session, "pane", "list"), path=("result", "panes")):
        pane = _at(value=row, path=("pane_id",))
        rows = _count(value=_at(value=row, path=("scroll", "viewport_rows")))
        offset = _count(value=_at(value=row, path=("scroll", "offset_from_bottom")))
        if isinstance(pane, str) and pane and offset == 0 and rows > 0:
            found.append((pane, rows))
    return found


def _herdr_foreground_is_claude(*, herdr: Herdr, session: str, pane: str) -> bool:
    """Whether a process in the pane's foreground group runs Claude Code's executable."""
    info = herdr("--session", session, "pane", "process-info", "--pane", pane)
    path = ("result", "process_info", "foreground_processes")
    heads = [
        next(iter(_list(value=_at(value=p, path=("argv",)))), None)
        for p in _items(text=info, path=path)
    ]
    return any(isinstance(head, str) and _is_claude(executable=head) for head in heads)


def _herdr_qualifies(*, herdr: Herdr, session: str, pane: str, rows: int) -> bool:
    """Whether this herdr pane, read now, shows the notice with its input box empty."""
    read = ("pane", "read", pane, "--source", _HERDR_SOURCE, "--lines", str(rows))
    return _needs_reissue(screen=herdr("--session", session, *read) or "")


def _herdr_candidates(*, herdr: Herdr) -> list[tuple[str, str, int]]:
    """(session, pane id, viewport rows) of each herdr Claude Code pane that qualifies."""
    return [
        (session, pane, rows)
        for session in _herdr_sessions(herdr=herdr)
        for pane, rows in _herdr_viewports(herdr=herdr, session=session)
        if _herdr_foreground_is_claude(herdr=herdr, session=session, pane=pane)
        and _herdr_qualifies(herdr=herdr, session=session, pane=pane, rows=rows)
    ]


def _send_tmux(*, tmux: Tmux, pane: str) -> bool:
    """Re-check the pane right before typing, then send; a box gaining text is left alone."""
    screen = tmux("capture-pane", "-p", "-J", "-t", pane)
    return (
        screen is not None
        and _needs_reissue(screen=screen)
        and tmux("send-keys", "-t", pane, "-l", _COMMAND) is not None
        and tmux("send-keys", "-t", pane, "Enter") is not None
    )


def _send_herdr(*, herdr: Herdr, session: str, pane: str, rows: int) -> bool:
    """Re-check the herdr pane right before typing, then send."""
    target = ("--session", session, "pane")
    return (
        _herdr_qualifies(herdr=herdr, session=session, pane=pane, rows=rows)
        and herdr(*target, "send-text", pane, _COMMAND) is not None
        and herdr(*target, "send-keys", pane, _ENTER) is not None
    )


def _sweep(*, tmux: Tmux, ps: Ps, herdr: Herdr, done: list[str]) -> None:
    """One scan of every pane, sending to each qualifying pane not already in `done`."""
    for pane in panes_needing_reissue(tmux=tmux, ps=ps):
        if pane not in done and _send_tmux(tmux=tmux, pane=pane):
            done.append(pane)
    for session, pane, rows in _herdr_candidates(herdr=herdr):
        label = f"herdr:{session}:{pane}"
        if label not in done and _send_herdr(herdr=herdr, session=session, pane=pane, rows=rows):
            done.append(label)


def reissue(
    *,
    tmux: Tmux = _run_tmux,
    ps: Ps = _run_ps,
    herdr: Herdr = _run_herdr,
    window_s: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> list[str]:
    """Send `/remote-control` and Enter to every qualifying pane over the window; return them."""
    deadline = clock() + window_s
    sent: list[str] = []
    _sweep(tmux=tmux, ps=ps, herdr=herdr, done=sent)
    while clock() + _RESCAN_S <= deadline:
        sleep(_RESCAN_S)
        _sweep(tmux=tmux, ps=ps, herdr=herdr, done=sent)
    return sent


def main(
    *,
    argv: list[str] | None = None,
    tmux: Tmux = _run_tmux,
    ps: Ps = _run_ps,
    herdr: Herdr = _run_herdr,
) -> int:
    """Re-issue over the window named by the one optional argument, default _WINDOW_S."""
    window_s = float(argv[0]) if argv else _WINDOW_S
    sent = reissue(tmux=tmux, ps=ps, herdr=herdr, window_s=window_s)
    print(json.dumps({"reissued": sent}))  # noqa: T201 -- the script's one output line
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
