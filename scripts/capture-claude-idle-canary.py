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

__all__: list[str] = ["capture_is_ready", "main"]

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
    completed = _run(argv=["tmux", "capture-pane", "-t", session, "-p", "-S", "-200"])
    if completed.returncode != 0:
        return ""
    return completed.stdout


def _start_canary_session(*, session: str) -> bool:
    completed = _run(
        argv=[
            "tmux",
            "new-session",
            "-d",
            "-s",
            session,
            "claude",
            "--dangerously-skip-permissions",
            "-n",
            _CANARY_TOPIC,
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


def main() -> int:
    version = _installed_version()
    if version is None:
        _write_stderr(text="CLAUDE_IDLE_CANARY_CAPTURE_FAILED: claude --version unavailable\n")
        return 1
    session = f"claude-idle-canary-{os.getpid()}"
    if not _start_canary_session(session=session):
        _write_stderr(text="CLAUDE_IDLE_CANARY_CAPTURE_FAILED: tmux canary session did not start\n")
        return 1
    try:
        capture = _await_idle_capture(session=session)
    finally:
        _kill_canary_session(session=session)
    if capture is None:
        _write_stderr(
            text="CLAUDE_IDLE_CANARY_CAPTURE_FAILED: idle prompt did not render in time\n"
        )
        return 1
    _FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = _FIXTURE_DIR / f"{version}.txt"
    path.write_text(capture, encoding="utf-8")
    _write_stdout(text=f"wrote {path.relative_to(_REPO_ROOT)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
