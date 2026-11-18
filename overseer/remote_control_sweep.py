"""One keep-alive sweep of a host's herdr panes: keep every Claude Code seat on Remote Control.

contracts.md "Remote Control keep-alive sweep" (spec v111). The push loop runs
this every 30 s on the role holder and, over ssh as `python3 -` with this file on
stdin, on every listed host, where no overseer package is installed: it is
self-contained and stdlib-only for that reason, like `remote_control_reissue.py`.

Whether a session is on Remote Control is read from the session's own record,
`~/.claude/sessions/<pid>.json` (its `bridgeSessionId`), never from the pane's
text, which can keep showing a disconnected notice after the session
reconnected. The text is read only to recognise a dialog and the input box.

Per Claude Code pane at the bottom of its scroll, re-reading before every key:
- the enable dialog with `1. Enable Remote Control` selected gets Enter;
- the status panel (`Disconnect this session` + `Esc to continue`) of a CONNECTED
  session gets Escape, never Enter, and only while the record's status is not
  `busy`. On a session whose record has no `bridgeSessionId` it is the NOT-CONNECTED
  panel (what Claude Code opens after an account switch, with or without a typed
  `/remote-control`): it gets Enter, never Escape, only once a re-read shows
  `Continue` selected, whatever the status, and is reported as `offline` (continued)
  so the service can retry that pane before its cap runs out. An idle seat is then
  given at least _CONTINUE_WAIT_S seconds for Remote Control to turn off and sent
  the reconnect command; a busy seat is sent no text. Escape only dismissed this
  panel without reconnecting (measured at the 2026-11-16 and 2026-11-18 rotations);
- the folder-trust prompt is answered `Yes, I trust this folder` only when the
  directory it names, real-pathed, is the pane's herdr cwd and lies strictly
  below `~/workspace` or `~/.worktrees`;
- a session whose record exists without a `bridgeSessionId`, whose status is
  `idle` and whose input box is empty gets the reconnect command + Enter, then
  its enable dialog answered, unless the service lists the pane in BLOCKED_INPUT
  (sent within its ten-minute cap). The reconnect command is
  `/remote-control <name>` with the record's own `name`, so the seat comes back
  under the name other seats address it by; it is the bare `/remote-control`
  when the record has no name (or a null one), and when the name is refused: not a string,
  empty, over _NAME_MAX characters, or holding a control character.

It prints one JSON line: `actions` (what it sent), `reissued`, `off_rc`,
`unknown` (no readable record) and `sessions` (pane label -> session id), plus
`refused_name` (panes whose record name was refused) and `offline` (panes whose
not-connected panel it continued) when there is one.
Dialog wording was pinned from real captures of Claude Code _CLAUDE_CODE_VERSION.
"""

# livespec-lloc-soft-band-owner: overseer-4z97.2

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

__all__: list[str] = [
    "BLOCKED_INPUT",
    "dialog_kind",
    "main",
    "reconnect_command",
    "sweep",
    "trust_allowed",
]

_CLAUDE_CODE_VERSION = "2.1.325"
# The service replaces this list with the pane labels sent `/remote-control`
# within the last ten minutes.
BLOCKED_INPUT = "[]"
_COMMAND, _PROMPT, _RULE, _CONTINUE = "/remote-control", "❯", "─", "Continue"
_ENABLE, _NEVER = "1. Enable Remote Control", "2. Never mind"
_PANEL = ("Disconnect this session", "Esc to continue")
_PANEL_OPTIONS = ("Disconnect this session", "Show QR code", "Continue")
_TRUST_YES, _TRUST_HEADER = "Yes, I trust this folder", "Accessing workspace:"
_TRUST_HINT, _TRUST_NO = "Enter to confirm · Esc to cancel", "No, exit"
_ROOTS, _VERSIONS = ("workspace", ".worktrees"), ".local/share/claude/versions/"
# _REISSUE_BUDGET_S: a sweep stops typing once this much of its run is spent, well inside the
# service's 60 s SWEEP_TIMEOUT_S: a sweep that times out loses its report, and with it the cap
# on every pane it typed into.
_SETTLE_S, _DIALOG_WAIT_S, _TIMEOUT_S, _NAME_MAX, _REISSUE_BUDGET_S = 0.8, 3.0, 10, 200, 40.0
# The NOT-CONNECTED panel's own text says to choose Continue, wait about 10 seconds for
# Remote Control to turn off, then run /remote-control: wait a little longer than that.
_CONTINUE_WAIT_S, _CONTINUED = 12.0, "offline:Continue"
# Code points a typed name must not hold: C0 controls (newline, tab, escape) and DEL.
_CONTROL = frozenset(map(chr, [*range(0x20), 0x7F]))
_SUGGESTION = re.compile(
    r"^(?:[ \xa0]|\x1b\[[0-9;]*m)*(?:\x1b\[2m|\x1b\[38;2;(?P<grey>\d+);"
    r"(?P=grey);(?P=grey)m)[^\x1b\r\n]+(?:\x1b\[[0-9;]*m)*$"
)

Herdr = Callable[..., str | None]
Record = dict[str, object]
Sleep = Callable[[float], None]
RecordOf = Callable[..., Record]
# (herdr session, pane id, viewport rows, cwd, Claude Code pid)
Pane = tuple[str, str, int, str, int]


def _run_herdr(*args: str) -> str | None:
    fallback = Path.home() / ".local" / "bin" / "herdr"
    binary = shutil.which("herdr") or (str(fallback) if fallback.is_file() else None)
    if binary is None:
        return None
    try:
        done = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            [binary, *args], capture_output=True, text=True, timeout=_TIMEOUT_S, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def _parsed(*, text: str | None) -> object:
    try:
        return json.loads(text or "null")
    except ValueError:
        return None


def _read_record(*, pid: int) -> dict[str, object]:
    path = Path.home() / ".claude" / "sessions" / f"{pid}.json"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    value = _parsed(text=text)
    record = cast("dict[str, object]", value) if isinstance(value, dict) else {}
    return record if record.get("pid") == pid else {}


def _at(*, value: object, path: tuple[str, ...]) -> object:
    for key in path:
        value = cast("dict[str, object]", value).get(key) if isinstance(value, dict) else None
    return value


def _rows(*, value: object, path: tuple[str, ...]) -> list[object]:
    found = _at(value=value, path=path)
    return cast("list[object]", found) if isinstance(found, list) else []


def _modal(*, screen: str) -> list[str]:
    return screen.splitlines()[-30:]  # a dialog fills at most the bottom 30 rows


def _last_prompt(*, lines: list[str]) -> str:
    """The bottom-most `❯` line: a dialog's selected option, or the input box below a stale one."""
    return next((line for line in reversed(lines) if line.strip().startswith(_PROMPT)), "")


def dialog_kind(*, screen: str) -> str:
    """`enable`, `enable-other`, `panel`, `trust` or `` for the dialog at the pane's bottom."""
    lines = _modal(screen=screen)
    body, last = "\n".join(lines), _last_prompt(lines=lines)
    if _NEVER in body and _ENABLE in body and (_ENABLE in last or _NEVER in last):
        return "enable" if _ENABLE in last else "enable-other"
    if all(marker in body for marker in _PANEL) and any(o in last for o in _PANEL_OPTIONS):
        return "panel"
    trust = _TRUST_YES in body and _TRUST_HINT in body
    return "trust" if trust and (_TRUST_YES in last or _TRUST_NO in last) else ""


def trust_allowed(*, screen: str, cwd: str, home: Path) -> bool:
    """Whether the trust prompt names the pane's own cwd, strictly below an allowed root."""
    lines = [line.strip() for line in _modal(screen=screen)]
    after = lines[lines.index(_TRUST_HEADER) + 1 :] if _TRUST_HEADER in lines else []
    named = next((line for line in after if line), "")
    if not named or not cwd or os.path.realpath(named) != os.path.realpath(cwd):
        return False
    real = Path(os.path.realpath(named))
    roots = [Path(os.path.realpath(home / root)) for root in _ROOTS]
    return any(real != root and real.is_relative_to(root) for root in roots)


def _empty_box(*, screen: str) -> bool:
    lines = screen.splitlines()
    prompts = [i for i, line in enumerate(lines) if line.startswith(_PROMPT)]
    text = lines[prompts[-1]][len(_PROMPT) :] if prompts else ""
    if not prompts or (text.strip() and _SUGGESTION.fullmatch(text) is None):
        return False
    if not any(line.startswith(_RULE) for line in lines[: prompts[-1]]):
        return False
    for line in lines[prompts[-1] + 1 :]:
        if line.strip():
            return line.startswith(_RULE)
    return False


def _panes(*, herdr: Herdr) -> list[Pane]:
    found: list[Pane] = []
    sessions = _rows(value=_parsed(text=herdr("session", "list", "--json")), path=("sessions",))
    for item in sessions:
        session = _at(value=item, path=("name",))
        if not isinstance(session, str) or _at(value=item, path=("running",)) is not True:
            continue
        listing = _parsed(text=herdr("--session", session, "pane", "list"))
        for row in _rows(value=listing, path=("result", "panes")):
            pane, cwd = _at(value=row, path=("pane_id",)), _at(value=row, path=("cwd",))
            rows = _at(value=row, path=("scroll", "viewport_rows"))
            offset = _at(value=row, path=("scroll", "offset_from_bottom"))
            if not isinstance(pane, str) or offset != 0 or type(rows) is not int or rows <= 0:
                continue
            info = _parsed(text=herdr("--session", session, "pane", "process-info", "--pane", pane))
            procs = _rows(value=info, path=("result", "process_info", "foreground_processes"))
            pids = [
                _at(value=p, path=("pid",))
                for p in procs
                if Path(str(next(iter(_rows(value=p, path=("argv",))), ""))).name == "claude"
                or _VERSIONS in str(next(iter(_rows(value=p, path=("argv",))), ""))
            ]
            if pids and type(pids[0]) is int:
                found.append((session, pane, rows, cwd if isinstance(cwd, str) else "", pids[0]))
    return found


def _read(*, herdr: Herdr, pane: Pane) -> str:
    read = ("pane", "read", pane[1], "--source", "recent-unwrapped", "--lines", str(pane[2]))
    return herdr("--session", pane[0], *(*read, "--format", "ansi")) or ""


def _keys(*, herdr: Herdr, pane: Pane, keys: tuple[str, ...]) -> bool:
    return herdr("--session", pane[0], "pane", "send-keys", pane[1], *keys) is not None


def _answer_trust(*, herdr: Herdr, pane: Pane, sleep: Sleep) -> str:
    """Select `Yes, I trust this folder` and confirm it, only for an allowed directory."""
    for _ in range(3):
        screen = _read(herdr=herdr, pane=pane)
        allowed = dialog_kind(screen=screen) == "trust" and trust_allowed(
            screen=screen, cwd=pane[3], home=Path.home()
        )
        if allowed and _TRUST_YES in _last_prompt(lines=_modal(screen=screen)):
            return "trust:Enter" if _keys(herdr=herdr, pane=pane, keys=("Enter",)) else ""
        if not allowed or not _keys(herdr=herdr, pane=pane, keys=("down",)):
            return ""
        sleep(_SETTLE_S)
    return ""


def _answer(*, herdr: Herdr, pane: Pane, record: Record, sleep: Sleep) -> str:
    """Answer the dialog the pane shows, re-reading before each key; the action taken, or ``.

    The status panel of a CONNECTED session gets Escape unless the seat is busy. On a record
    with no `bridgeSessionId` it is the NOT-CONNECTED panel: Enter once a re-read shows
    `Continue` selected, whatever the status, since Continue cannot disconnect or interrupt.
    """
    screen = _read(herdr=herdr, pane=pane)
    kind = dialog_kind(screen=screen)
    if kind == "panel" and record:
        bridged, busy = record.get("bridgeSessionId"), record.get("status") == "busy"
        go = _CONTINUE in _last_prompt(lines=_modal(screen=screen)) and not bridged
        key = "esc" if bridged and not busy else "Enter" if go else ""
        done = bool(key) and _keys(herdr=herdr, pane=pane, keys=(key,))
        return ("panel:Escape" if bridged else _CONTINUED) if done else ""
    if kind == "enable":
        return "enable:Enter" if _keys(herdr=herdr, pane=pane, keys=("Enter",)) else ""
    return _answer_trust(herdr=herdr, pane=pane, sleep=sleep) if kind == "trust" else ""


def reconnect_command(*, record: Record) -> tuple[str, bool]:
    """The text to type for this record, and whether its name was refused."""
    name = record.get("name")  # absent, or JSON null: the bare command
    if name is None:
        return _COMMAND, False
    ok = isinstance(name, str) and 0 < len(name) <= _NAME_MAX and _CONTROL.isdisjoint(name)
    return (f"{_COMMAND} {name}", False) if ok else (_COMMAND, True)


def _reissue(*, herdr: Herdr, pane: Pane, command: str, sleep: Sleep) -> bool:
    if not _empty_box(screen=_read(herdr=herdr, pane=pane)):
        return False
    target = ("--session", pane[0], "pane")
    if herdr(*target, "send-text", pane[1], command) is None:
        return False
    sleep(_SETTLE_S)
    lines = _read(herdr=herdr, pane=pane).splitlines()
    typed = next((line for line in reversed(lines) if line.startswith(_PROMPT)), "")
    return typed[len(_PROMPT) :].strip() == command and _keys(
        herdr=herdr, pane=pane, keys=("Enter",)
    )


def _reconnect(
    *, herdr: Herdr, pane: Pane, command: str, record_of: RecordOf, sleep: Sleep
) -> list[str]:
    """Type `command` and answer the dialog it opens; the actions taken, `[]` if not typed.

    The dialog is answered on the record read again AFTER the command, since the
    seat may have started a turn in the seconds since the sweep first read it.
    """
    if not _reissue(herdr=herdr, pane=pane, command=command, sleep=sleep):
        return []
    sleep(_DIALOG_WAIT_S)
    record = record_of(pid=pane[4])
    followed = _answer(herdr=herdr, pane=pane, record=record, sleep=sleep)
    idle = followed == _CONTINUED and record.get("status") == "idle"
    again = _retype(herdr=herdr, pane=pane, record_of=record_of, sleep=sleep) if idle else []
    return [command, *([followed] if followed else []), *again]


def _retype(*, herdr: Herdr, pane: Pane, record_of: RecordOf, sleep: Sleep) -> list[str]:
    """After Continue: wait for Remote Control to turn off, then reconnect a seat still idle."""
    sleep(_CONTINUE_WAIT_S)
    record = record_of(pid=pane[4])
    command = reconnect_command(record=record)[0]
    fresh = not record.get("bridgeSessionId") and record.get("status") == "idle"
    typed = fresh and _reissue(herdr=herdr, pane=pane, command=command, sleep=sleep)
    return [command] if typed else []


def _report(*, actions: list[str], reissued: list[str], off: list[str], found: Record) -> Record:
    """The sweep's one report: what it sent, what it found, and the optional parts when present."""
    continued = [a.split(" ", 1)[0] for a in actions if a.endswith(f" {_CONTINUED}")]
    report: Record = {"actions": actions, "reissued": reissued, "off_rc": off}
    report |= {"unknown": found["unknown"], "sessions": found["sessions"]}
    extra = {"refused_name": found["refused"], "offline": continued}
    return {**report, **{key: value for key, value in extra.items() if value}}


def sweep(
    *,
    blocked: list[str],
    herdr: Herdr = _run_herdr,
    record_of: RecordOf = _read_record,
    sleep: Sleep = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Record:
    """One sweep of every Claude Code pane on this host; the report the service journals."""
    start = clock()
    actions: list[str] = []
    reissued: list[str] = []
    off: list[str] = []
    unknown: list[str] = []
    refused: list[str] = []
    sessions: dict[str, object] = {}
    for pane in _panes(herdr=herdr):
        label, record = f"herdr:{pane[0]}:{pane[1]}", record_of(pid=pane[4])
        answered = _answer(herdr=herdr, pane=pane, record=record, sleep=sleep)
        if record:
            sessions[label] = record.get("sessionId")
            off += [] if record.get("bridgeSessionId") else [label]
        spent = clock() - start >= _REISSUE_BUDGET_S
        retype = answered == _CONTINUED and record.get("status") == "idle" and not spent
        more = _retype(herdr=herdr, pane=pane, record_of=record_of, sleep=sleep) if retype else []
        if answered or not record or record.get("bridgeSessionId"):
            actions += [f"{label} {action}" for action in (answered, *more) if action]
            unknown += [] if answered or record else [label]
            reissued += [label] if more else []
            continue
        if record.get("status") != "idle" or label in blocked or spent:
            continue
        command, was_refused = reconnect_command(record=record)
        refused += [label] if was_refused else []
        done = _reconnect(herdr=herdr, pane=pane, command=command, record_of=record_of, sleep=sleep)
        reissued += [label] if done else []
        actions += [f"{label} {action}" for action in done]
    found: Record = {"unknown": unknown, "sessions": sessions, "refused": refused}
    return _report(actions=actions, reissued=reissued, off=off, found=found)


def main(
    *, herdr: Herdr = _run_herdr, record_of: RecordOf = _read_record, sleep: Sleep = time.sleep
) -> int:
    """Run one sweep with the service's blocked list and print its report as one JSON line."""
    blocked = [str(item) for item in _rows(value={"b": _parsed(text=BLOCKED_INPUT)}, path=("b",))]
    report = sweep(blocked=blocked, herdr=herdr, record_of=record_of, sleep=sleep)
    print(json.dumps(report))  # noqa: T201 -- the script's one output line
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
