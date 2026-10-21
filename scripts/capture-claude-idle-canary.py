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


def _await_idle_capture(*, session: str) -> str | None:
    deadline = time.monotonic() + _CAPTURE_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        capture = _tmux_capture(session=session)
        if capture_is_ready(capture=capture):
            return capture.rstrip() + "\n"
        time.sleep(_POLL_SECONDS)
    return None


class IdleCaptureAttempt:
    """One disposable-session capture attempt: the pane text, or why there is none.

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
    the same two read-only-by-convention fields and loads anywhere.
    """

    def __init__(self, *, text: str | None, failure: str | None) -> None:
        self.text = text
        self.failure = failure


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
        return IdleCaptureAttempt(text=None, failure="tmux canary session did not start")
    try:
        capture = _await_idle_capture(session=session)
    finally:
        _kill_canary_session(session=session)
    if capture is None:
        return IdleCaptureAttempt(text=None, failure="idle prompt did not render in time")
    return IdleCaptureAttempt(text=capture, failure=None)


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
