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
  never Enter, and only while the record's status is not `busy`;
- the folder-trust prompt is answered `Yes, I trust this folder` only when the
  directory it names, real-pathed, is the pane's herdr cwd and lies strictly
  below `~/workspace` or `~/.worktrees`;
- a session whose record exists without a `bridgeSessionId`, whose status is
  `idle` and whose input box is empty gets `/remote-control` + Enter, then its
  enable dialog answered, unless the service lists the pane in BLOCKED_INPUT
  (sent within its ten-minute cap).

It prints one JSON line: `actions` (what it sent), `reissued`, `off_rc`,
`unknown` (no readable record) and `sessions` (pane label -> session id).
Dialog wording was pinned from real captures of Claude Code _CLAUDE_CODE_VERSION.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

__all__: list[str] = ["BLOCKED_INPUT", "dialog_kind", "main", "sweep", "trust_allowed"]

_CLAUDE_CODE_VERSION = "2.1.325"
# The service replaces this list with the pane labels sent `/remote-control`
# within the last ten minutes.
BLOCKED_INPUT = "[]"
_COMMAND = "/remote-control"
_PROMPT, _RULE = "❯", "─"
_ENABLE, _NEVER = "1. Enable Remote Control", "2. Never mind"
_PANEL = ("Disconnect this session", "Esc to continue")
_TRUST_YES, _TRUST_HEADER = "Yes, I trust this folder", "Accessing workspace:"
_TRUST_HINT = "Enter to confirm · Esc to cancel"
_ROOTS = ("workspace", ".worktrees")
_VERSIONS = ".local/share/claude/versions/"
_MODAL_LINES = 30
_SETTLE_S, _DIALOG_WAIT_S, _TIMEOUT_S = 0.8, 3.0, 10

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
    return screen.splitlines()[-_MODAL_LINES:]


def _selected(*, lines: list[str], text: str) -> bool:
    return any(line.strip().startswith(_PROMPT) and text in line for line in lines)


def dialog_kind(*, screen: str) -> str:
    """`enable`, `enable-other`, `panel`, `trust` or `` for the dialog at the pane's bottom."""
    lines = _modal(screen=screen)
    body = "\n".join(lines)
    if _NEVER in body and "Enable Remote Control" in body:
        return "enable" if _selected(lines=lines, text=_ENABLE) else "enable-other"
    if all(marker in body for marker in _PANEL):
        return "panel"
    if _TRUST_YES in body and _TRUST_HINT in body:
        return "trust"
    return ""


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
        if allowed and _selected(lines=_modal(screen=screen), text=_TRUST_YES):
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
        return "panel:Escape" if _keys(herdr=herdr, pane=pane, keys=("esc",)) else ""
    return _answer_trust(herdr=herdr, pane=pane, sleep=sleep) if kind == "trust" else ""


def _reissue(*, herdr: Herdr, pane: Pane, sleep: Callable[[float], None]) -> bool:
    if not _empty_box(screen=_read(herdr=herdr, pane=pane)):
        return False
    target = ("--session", pane[0], "pane")
    sent = herdr(*target, "send-text", pane[1], _COMMAND) is not None
    if sent:
        sleep(_SETTLE_S)
    return sent and _keys(herdr=herdr, pane=pane, keys=("Enter",))


def sweep(
    *,
    blocked: list[str],
    herdr: Herdr = _run_herdr,
    record_of: Callable[..., dict[str, object]] = _read_record,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """One sweep of every Claude Code pane on this host; the report the service journals."""
    actions: list[str] = []
    reissued: list[str] = []
    off: list[str] = []
    unknown: list[str] = []
    sessions: dict[str, object] = {}
    for pane in _panes(herdr=herdr):
        label, record = f"herdr:{pane[0]}:{pane[1]}", record_of(pid=pane[4])
        answered = _answer(herdr=herdr, pane=pane, record=record, sleep=sleep)
        if record:
            sessions[label] = record.get("sessionId")
        if answered or not record or record.get("bridgeSessionId"):
            actions += [f"{label} {answered}"] if answered else []
            unknown += [] if answered or record else [label]
            continue
        off.append(label)
        if record.get("status") != "idle" or label in blocked:
            continue
        if _reissue(herdr=herdr, pane=pane, sleep=sleep):
            reissued.append(label)
            sleep(_DIALOG_WAIT_S)
            followed = _answer(herdr=herdr, pane=pane, record=record, sleep=sleep)
            actions += [f"{label} {_COMMAND}"] + ([f"{label} {followed}"] if followed else [])
    return {
        "actions": actions,
        "reissued": reissued,
        "off_rc": off,
        "unknown": unknown,
        "sessions": sessions,
    }


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
