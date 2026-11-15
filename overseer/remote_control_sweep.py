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
- the status panel (`Disconnect this session` + `Esc to continue`) gets Escape,
  never Enter, and only while the record's status is not `busy`; on a session
  whose record has no `bridgeSessionId` it is the not-connected case (what
  `/remote-control` opens right after an account switch), reported as
  `offline` so the service can retry that pane before its cap runs out;
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
not-connected panel it dismissed) when there is one.
Dialog wording was pinned from real captures of Claude Code _CLAUDE_CODE_VERSION.
"""

# livespec-lloc-soft-band-owner: overseer-4z97.2

from __future__ import annotations

import json
import os
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
_COMMAND, _PROMPT, _RULE = "/remote-control", "❯", "─"
_ENABLE, _NEVER = "1. Enable Remote Control", "2. Never mind"
_PANEL = ("Disconnect this session", "Esc to continue")
_PANEL_OPTIONS = ("Disconnect this session", "Show QR code", "Continue")
_TRUST_YES, _TRUST_HEADER = "Yes, I trust this folder", "Accessing workspace:"
_TRUST_HINT, _TRUST_NO = "Enter to confirm · Esc to cancel", "No, exit"
_ROOTS, _VERSIONS = ("workspace", ".worktrees"), ".local/share/claude/versions/"
_SETTLE_S, _DIALOG_WAIT_S, _TIMEOUT_S, _NAME_MAX = 0.8, 3.0, 10, 200
# A sweep stops typing once this much of its run is spent, well inside the
# service's 60 s SWEEP_TIMEOUT_S: a sweep that times out loses its report, and
# with it the cap on every pane it typed into.
_REISSUE_BUDGET_S = 40.0
# Code points a typed name must not hold: C0 controls (newline, tab, escape) and DEL.
_CONTROL = frozenset(map(chr, [*range(0x20), 0x7F]))

Herdr = Callable[..., str | None]
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
    if not prompts or lines[prompts[-1]][len(_PROMPT) :].strip():
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
    return herdr("--session", pane[0], *read) or ""


def _keys(*, herdr: Herdr, pane: Pane, keys: tuple[str, ...]) -> bool:
    return herdr("--session", pane[0], "pane", "send-keys", pane[1], *keys) is not None


def _answer_trust(*, herdr: Herdr, pane: Pane, sleep: Callable[[float], None]) -> str:
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


def _answer(
    *, herdr: Herdr, pane: Pane, record: dict[str, object], sleep: Callable[[float], None]
) -> str:
    """Answer the dialog the pane shows, re-reading before each key; the action taken, or ``."""
    kind = dialog_kind(screen=_read(herdr=herdr, pane=pane))
    if kind == "enable":
        return "enable:Enter" if _keys(herdr=herdr, pane=pane, keys=("Enter",)) else ""
    if kind == "panel" and record and record.get("status") != "busy":
        panel = "panel" if record.get("bridgeSessionId") else "offline"
        return f"{panel}:Escape" if _keys(herdr=herdr, pane=pane, keys=("esc",)) else ""
    return _answer_trust(herdr=herdr, pane=pane, sleep=sleep) if kind == "trust" else ""


def reconnect_command(*, record: dict[str, object]) -> tuple[str, bool]:
    """The text to type for this record, and whether its name was refused."""
    if record.get("name") is None:  # absent, or JSON null
        return _COMMAND, False
    name = record["name"]
    if (
        not isinstance(name, str)
        or not name
        or len(name) > _NAME_MAX
        or not _CONTROL.isdisjoint(name)
    ):
        return _COMMAND, True
    return f"{_COMMAND} {name}", False


def _reissue(*, herdr: Herdr, pane: Pane, command: str, sleep: Callable[[float], None]) -> bool:
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
    *,
    herdr: Herdr,
    pane: Pane,
    command: str,
    record_of: Callable[..., dict[str, object]],
    sleep: Callable[[float], None],
) -> list[str]:
    """Type `command` and answer the dialog it opens; the actions taken, `[]` if not typed.

    The dialog is answered on the record read again AFTER the command, since the
    seat may have started a turn in the seconds since the sweep first read it.
    """
    if not _reissue(herdr=herdr, pane=pane, command=command, sleep=sleep):
        return []
    sleep(_DIALOG_WAIT_S)
    followed = _answer(herdr=herdr, pane=pane, record=record_of(pid=pane[4]), sleep=sleep)
    return [command, *([followed] if followed else [])]


def sweep(
    *,
    blocked: list[str],
    herdr: Herdr = _run_herdr,
    record_of: Callable[..., dict[str, object]] = _read_record,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, object]:
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
        if record and not record.get("bridgeSessionId"):
            off.append(label)
        if answered or not record or record.get("bridgeSessionId"):
            actions += [f"{label} {answered}"] if answered else []
            unknown += [] if answered or record else [label]
            continue
        if record.get("status") != "idle" or label in blocked:
            continue
        if clock() - start >= _REISSUE_BUDGET_S:
            continue
        command, was_refused = reconnect_command(record=record)
        refused += [label] if was_refused else []
        done = _reconnect(herdr=herdr, pane=pane, command=command, record_of=record_of, sleep=sleep)
        reissued += [label] if done else []
        actions += [f"{label} {action}" for action in done]
    report: dict[str, object] = {
        "actions": actions,
        "reissued": reissued,
        "off_rc": off,
        "unknown": unknown,
        "sessions": sessions,
    }
    offline = [action.split(" ", 1)[0] for action in actions if action.endswith(" offline:Escape")]
    extra = {"refused_name": refused, "offline": offline}
    return {**report, **{key: value for key, value in extra.items() if value}}


def main(
    *,
    herdr: Herdr = _run_herdr,
    record_of: Callable[..., dict[str, object]] = _read_record,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Run one sweep with the service's blocked list and print its report as one JSON line."""
    blocked = [str(item) for item in _rows(value={"b": _parsed(text=BLOCKED_INPUT)}, path=("b",))]
    report = sweep(blocked=blocked, herdr=herdr, record_of=record_of, sleep=sleep)
    print(json.dumps(report))  # noqa: T201 -- the script's one output line
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
