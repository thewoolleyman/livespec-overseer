#!/usr/bin/env python3
"""Capture a throwaway Claude -n idle prompt fixture for the installed build."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OVERSEER_DIR = _REPO_ROOT / "overseer"
if str(_OVERSEER_DIR) not in sys.path:
    sys.path.insert(0, str(_OVERSEER_DIR))

import signals  # noqa: E402
from tmuxio import new_session_args  # noqa: E402

__all__: list[str] = ["IdleCaptureAttempt", "capture_is_ready", "live_idle_capture", "main"]

_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "claude-idle"
_VERSION_RE = re.compile(r"\b(\d+\.\d+\.\d+)\b")
_CANARY_TOPIC = "overseer-idle-canary"
_CAPTURE_TIMEOUT_SECONDS = 45.0
_POLL_SECONDS = 1.0


def _write_stderr(*, text: str) -> None:
    _ = sys.stderr.write(text)


def _write_stdout(*, text: str) -> None:
    _ = sys.stdout.write(text)


def _run(*, argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        argv,
        capture_output=True,
        check=False,
        text=True,
        timeout=_CAPTURE_TIMEOUT_SECONDS,
    )


def _installed_version() -> str | None:
    try:
        completed = _run(argv=["claude", "--version"])
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return next(iter(_VERSION_RE.findall(completed.stdout)), None)


def _tmux_capture(*, session: str) -> str:
    completed = _run(argv=["tmux", "capture-pane", "-e", "-t", session, "-p", "-S", "-200"])
    if completed.returncode != 0:
        return ""
    return completed.stdout


def _start_canary_session(*, session: str) -> bool:
    completed = _run(
        argv=[
            "tmux",
            *new_session_args(
                args=[
                    "-d",
                    "-s",
                    session,
                    "claude",
                    "--dangerously-skip-permissions",
                    "-n",
                    _CANARY_TOPIC,
                ]
            ),
        ]
    )
    return completed.returncode == 0


def _kill_canary_session(*, session: str) -> None:
    try:
        _ = _run(argv=["tmux", "kill-session", "-t", session])
    except (OSError, subprocess.TimeoutExpired):
        return


def capture_is_ready(*, capture: str) -> bool:
    return signals.is_idle_input(capture_text=capture) and signals.input_box_ready(
        capture_text=capture
    )


class IdleCaptureAttempt:
    """One disposable-session capture attempt: what the pane showed, and what is storable.

    THREE fields rather than two, because "no storable capture" has two causes
    its callers must tell apart:

    - `text` is a capture this attempt judged READY — the only thing that may
      ever be stored as a fixture, so an unreadable pane cannot leak into the
      regression corpus;
    - `pane_text` is the last NON-EMPTY pane text seen, ready or not. It is the
      evidence the canary CHECK judges for itself, and the only way that check
      can distinguish a pane the detector could not read (a real detector
      failure) from a session that rendered nothing at all (no evidence either
      way). Without it the check sees only `text`, which this module never
      offers unless the detector already accepted it, so its rejection branch
      would be unreachable on every real host;
    - `failure` is why there is no ready capture, which `main` reports.

    DELIBERATELY NOT a `@dataclass(frozen=True, kw_only=True)`, which is this
    repo's normal shape for a record like this — do not "upgrade" it back. This
    file is a dash-named script, so every consumer loads it with
    `importlib.util.spec_from_file_location` + `exec_module` WITHOUT registering
    it in `sys.modules`: the canary check does, and so does its beside-test. On
    Python 3.10, `dataclasses` resolves each `from __future__ import
    annotations` string annotation through `sys.modules[cls.__module__]` while
    screening for the `KW_ONLY` sentinel, so under that loader the decorator
    raises `AttributeError` on a `None` module at class-definition time and the
    whole script becomes unimportable. A plain keyword-only `__init__` carries
    the same read-only-by-convention fields and loads anywhere.
    """

    def __init__(self, *, text: str | None, pane_text: str | None, failure: str | None) -> None:
        self.text = text
        self.pane_text = pane_text
        self.failure = failure


def _await_idle_capture(*, session: str) -> IdleCaptureAttempt:
    deadline = time.monotonic() + _CAPTURE_TIMEOUT_SECONDS
    pane_text: str | None = None
    while time.monotonic() < deadline:
        capture = _tmux_capture(session=session)
        if capture.strip():
            pane_text = capture.rstrip() + "\n"
        if capture_is_ready(capture=capture):
            return IdleCaptureAttempt(text=pane_text, pane_text=pane_text, failure=None)
        time.sleep(_POLL_SECONDS)
    if pane_text is None:
        return IdleCaptureAttempt(
            text=None,
            pane_text=None,
            failure="the canary session rendered no pane text in time",
        )
    return IdleCaptureAttempt(
        text=None,
        pane_text=pane_text,
        failure="the idle detector could not read the pane text the canary session rendered",
    )


def live_idle_capture() -> IdleCaptureAttempt:
    """Render the installed build's idle box in a disposable session and read it back.

    PUBLIC because the canary CHECK calls it too. When the installed build has
    no registered fixture, that check needs exactly the live evidence this
    function produces, and reaching into the private start/await/kill helpers
    from another module would be a cross-module private call. So the whole
    attempt is one public function and the failure wording `main` reports rides
    on its outcome rather than being decided by the caller.
    """
    session = f"claude-idle-canary-{os.getpid()}"
    if not _start_canary_session(session=session):
        return IdleCaptureAttempt(
            text=None, pane_text=None, failure="tmux canary session did not start"
        )
    try:
        return _await_idle_capture(session=session)
    finally:
        _kill_canary_session(session=session)


def main() -> int:
    version = _installed_version()
    if version is None:
        _write_stderr(text="CLAUDE_IDLE_CANARY_CAPTURE_FAILED: claude --version unavailable\n")
        return 1
    attempt = live_idle_capture()
    if attempt.text is None:
        _write_stderr(text=f"CLAUDE_IDLE_CANARY_CAPTURE_FAILED: {attempt.failure}\n")
        return 1
    _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = _FIXTURE_DIR / f"{version}.txt"
    path.write_text(attempt.text, encoding="utf-8")
    _write_stdout(text=f"wrote {path.relative_to(_REPO_ROOT)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
