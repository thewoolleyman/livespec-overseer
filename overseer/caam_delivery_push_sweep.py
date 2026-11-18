"""The push service's Remote Control keep-alive sweep (contracts.md v111).

Every SWEEP_INTERVAL_S the service runs `remote_control_sweep.py` on the role
holder and, over ssh, on every listed Linux host, on a daemon thread so a sweep
never delays a delivery push, and never two at once. This module holds what the
sweep must remember between passes, in memory only (it starts empty with the
service):
- the panes sent `/remote-control` and when, by the sweep or by "Remote Control
  re-issue", so no pane gets it twice in REISSUE_CAP_S;
- the hosts with a re-issue run in progress, which the sweep skips;
- when each pane was first read off Remote Control, so one ntfy push goes out
  after ALERT_AFTER_S, and again only after it was seen back on;
- how many times each pane was released from REISSUE_CAP_S because the sweep
  found it at the not-connected Remote Control panel (`offline`), at most
  OFFLINE_RETRIES until it is seen back on Remote Control.
"""

# livespec-lloc-soft-band-owner: overseer-4z97.2

from __future__ import annotations

import http.client
import json
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import jsonio
from caam_delivery_push_state import HOSTS_FILE, load_hosts

__all__: list[str] = [
    "ALERT_AFTER_S",
    "LOCAL",
    "OFFLINE_RETRIES",
    "REISSUE_CAP_S",
    "SWEEP_INTERVAL_S",
    "SWEEP_TIMEOUT_S",
    "SweepState",
    "maybe_start",
    "ntfy_push",
    "ntfy_url",
    "reissue_finished",
    "reissue_started",
    "run_here",
    "sweep_all",
    "targets",
    "tracking",
]

SWEEP_INTERVAL_S = 30.0
REISSUE_CAP_S = 600.0
ALERT_AFTER_S = 300.0
OFFLINE_RETRIES = 4
LOCAL = "role-holder"
SWEEP_TIMEOUT_S = 60.0
_BLOCKED_LINE = 'BLOCKED_INPUT = "[]"'
_NTFY_DEFAULT = "https://ntfy.sh"

Runner = Callable[..., str]
Notify = Callable[..., str]
Write = Callable[..., None]
Post = Callable[..., str]

_LOCK = threading.Lock()
_REISSUING: set[str] = set()
_SENT: dict[str, float] = {}


@dataclass(kw_only=True)
class SweepState:
    """What the sweep remembers between passes; empty when the service starts."""

    due_at: float = 0.0
    running: bool = False
    off_since: dict[str, float] = field(default_factory=dict[str, float])
    alerted: set[str] = field(default_factory=set[str])
    session_of: dict[str, object] = field(default_factory=dict[str, object])
    retried: dict[str, int] = field(default_factory=dict[str, int])


def reissue_started(*, host: str) -> None:
    """A "Remote Control re-issue" run began on `host`: the sweep skips it until it ends."""
    with _LOCK:
        _REISSUING.add(host)


def reissue_finished(*, host: str, line: str, now: float) -> None:
    """The run on `host` ended; each pane its result line names counts as sent `now`."""
    parsed = jsonio.as_object(value=_loads(text=line))
    panes = _strings(value=None if parsed is None else parsed.get("reissued"))
    with _LOCK:
        _REISSUING.discard(host)
        for pane in panes:
            _SENT[f"{host}|{pane}"] = now


def _loads(*, text: str) -> object:
    try:
        return json.loads(text)
    except ValueError:
        return None


def _blocked(*, host: str, now: float) -> list[str]:
    with _LOCK:
        sent = [k.split("|", 1) for k, t in _SENT.items() if now - t < REISSUE_CAP_S]
    return [pane for label, pane in sent if label == host]


def _strings(*, value: object) -> list[str]:
    items: list[object] = cast("list[object]", value) if isinstance(value, list) else []
    return [str(item) for item in items]


def _sweep_host(
    *, host: str, runner: Runner, script: str, state: SweepState, now: float, notify: Notify
) -> str:
    """One host's sweep; its journal line."""
    if host in _REISSUING:
        return f"remote-control sweep {host}: skipped while its re-issue runs"
    blocked = json.dumps(json.dumps(_blocked(host=host, now=now)))
    line = runner(program=script.replace(_BLOCKED_LINE, f"BLOCKED_INPUT = {blocked}", 1))
    report = jsonio.as_object(value=_loads(text=line))
    if report is None:
        return f"remote-control sweep {host}: unread {line}"
    off = _strings(value=report.get("off_rc"))
    sessions = jsonio.as_object(value=report.get("sessions")) or {}
    with _LOCK:
        for pane in _strings(value=report.get("reissued")):
            _SENT[f"{host}|{pane}"] = now
        for pane in _strings(value=report.get("offline")):
            key = f"{host}|{pane}"
            if state.retried.get(key, 0) < OFFLINE_RETRIES:
                state.retried[key] = state.retried.get(key, 0) + 1
                _ = _SENT.pop(key, None)
    lines = [_report_line(host=host, report=report)]
    for pane, session in sessions.items():
        key = f"{host}|{pane}"
        if state.session_of.get(key, session) != session or pane not in off:
            _ = state.off_since.pop(key, None)
            _ = state.retried.pop(key, None)
            state.alerted.discard(key)
        state.session_of[key] = session
        since = state.off_since.setdefault(key, now) if pane in off else now
        if now - since > ALERT_AFTER_S and key not in state.alerted:
            state.alerted.add(key)
            outcome = notify(message=f"Claude seat off Remote Control over 5 min: {host} {pane}")
            lines.append(f"remote-control sweep {host}: ntfy {pane} {outcome}")
    return "\n".join(lines)


def _report_line(*, host: str, report: dict[str, object]) -> str:
    optional = tuple(part for part in ("refused_name", "offline") if part in report)
    parts = ("actions", "off_rc", "unknown", *optional)
    return f"remote-control sweep {host}: " + " ".join(
        f"{part}={_strings(value=report.get(part))}" for part in parts
    )


def sweep_all(
    *,
    targets: list[tuple[str, Runner]],
    script: str,
    state: SweepState,
    now: float,
    notify: Notify,
    write: Write,
) -> None:
    """Sweep every target in turn, journalling each, then allow the next sweep."""
    try:
        for host, runner in targets:
            write(
                line=_sweep_host(
                    host=host, runner=runner, script=script, state=state, now=now, notify=notify
                )
            )
    finally:
        state.running = False


def maybe_start(  # noqa: PLR0913 - each argument is an independent seam
    *,
    state: SweepState,
    now: float,
    targets: list[tuple[str, Runner]],
    script: str | None,
    notify: Notify,
    write: Write,
    start: Callable[..., None],
) -> bool:
    """Start one sweep on `start` when one is due and none is running; whether it started."""
    if script is None or not targets or state.running or now < state.due_at:
        return False
    state.running, state.due_at = True, now + SWEEP_INTERVAL_S

    def task() -> None:
        sweep_all(targets=targets, script=script, state=state, now=now, notify=notify, write=write)

    start(task=task)
    return True


def targets(
    *, home: Path, local: Runner, remote: Callable[..., Runner]
) -> list[tuple[str, Runner]]:
    """The role holder plus every listed Linux host; none until the service has a host list."""
    if not (home / HOSTS_FILE).exists():
        return []
    listed = [(h.label, remote(host=h)) for h in load_hosts(home=home) if h.platform != "macos"]
    return [(LOCAL, local), *listed]


def _post(*, url: str, message: str) -> str:
    """POST to ntfy; the outcome names only an error's type, never the URL holding the topic."""
    try:
        request = urllib.request.Request(url, data=message.encode(), method="POST")  # noqa: S310
        with urllib.request.urlopen(request, timeout=15) as reply:  # noqa: S310 - ntfy endpoint
            return f"sent {reply.status}"
    except (OSError, ValueError, http.client.HTTPException) as error:
        return f"failed {type(error).__name__}"


def ntfy_url(*, home: Path) -> str | None:
    """The role holder's Claude ntfy address, or None when none is configured."""
    settings = jsonio.as_object(value=_loads(text=_text(path=home / ".claude" / "settings.json")))
    env = jsonio.as_object(value=None if settings is None else settings.get("env")) or {}
    topic, server = env.get("CLAUDE_NTFY_TOPIC"), env.get("CLAUDE_NTFY_SERVER") or _NTFY_DEFAULT
    if not isinstance(topic, str) or not topic or not isinstance(server, str):
        return None
    return f"{server.rstrip('/')}/{topic}"


def ntfy_push(*, home: Path, message: str, post: Post | None = None) -> str:
    """Push `message` to the role holder's Claude ntfy address; the outcome, never the topic."""
    url = ntfy_url(home=home)
    if url is None:
        return "skipped no ntfy address"
    return (_post if post is None else post)(url=url, message=message)


def _text(*, path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def run_here(*, program: str) -> str:
    """Run a sweep program on this host under this interpreter; its whole last line."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed interpreter, repo-shipped program
            [sys.executable, "-"],
            input=program,
            capture_output=True,
            text=True,
            timeout=SWEEP_TIMEOUT_S,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        return f"failed {type(error).__name__}"
    lines = done.stdout.strip().splitlines()
    return lines[-1] if lines else f"failed exit {done.returncode}"


def tracking(
    *, run: Callable[..., tuple[int, str]], home: Path, script: str | None
) -> Callable[..., tuple[int, str]]:
    """The push's ssh runner, registering each "Remote Control re-issue" run for the sweep."""
    labels = {host.target: host.label for host in load_hosts(home=home)}

    def wrapped(**kwargs: object) -> tuple[int, str]:
        if script is None or kwargs.get("program") != script:
            return run(**kwargs)
        host = labels.get(str(kwargs.get("target")), str(kwargs.get("target")))
        reissue_started(host=host)
        result = (255, "failed")
        try:
            result = run(**kwargs)
        finally:
            reissue_finished(host=host, line=result[1], now=time.monotonic())
        return result

    return wrapped
