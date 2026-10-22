#!/usr/bin/env python3
"""A stub Codex TUI the shipped daemon can discover, read, rename and replace.

This stands in for an authenticated `codex` binary in the isolated live exercise
(`overseer/live-exercise.md`). It implements only the surfaces the SHIPPED code
actually reads, and nothing else:

* **Discovery** (`overseer/codex_sessions.py`) joins a pid to a plan topic through
  `/proc`: `comm == "codex"`, an OPEN fd on a `rollout-<ts>-<uuid>.jsonl`, and a
  `session_index.jsonl` record mapping that uuid to a `thread_name`. So the stub
  sets its own `comm` with `prctl`, creates and HOLDS its rollout, and appends the
  index record when it is `/rename`d -- never before, because a fresh Codex rollout
  carries no `thread_name` until the rename lands, and the daemon's fresh-restart
  arm depends on exactly that ordering.
* **Observation** (`overseer/signals.py`) reads a pane CAPTURE. Codex idle is
  structural -- a `›` input line plus a `Context N% left` statusline, not busy and
  not a picker -- and a Codex submit is confirmed by the pane going BUSY, not by an
  emptied composer. So the stub renders that exact shape and prints a real busy
  marker while a turn runs.

It is deliberately NOT a Codex emulator: it has no model, and a turn is a sleep.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import os
import signal
import subprocess
import sys
import termios
import time
import tty
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

__all__: list[str] = [
    "StubCodex",
    "codex_home",
    "main",
    "render_screen",
    "rollout_path",
    "set_process_name",
]

# `comm` is what BOTH the discovery join and `overseer-start`'s agent-ancestry
# guard match on, and a `#!` script's comm is its INTERPRETER (`python3`), not its
# own name. PR_SET_NAME is the only way a Python stub can present as `codex`.
_PR_SET_NAME = 15
_PROCESS_NAME = b"codex"

# The busy marker is one of the literals `signals._BUSY_ACTIVE_RE` fires on. The
# idle frame must avoid every one of them -- in particular it carries no `…`, which
# the bare-spinner alternative (`^\s*\S\s+[A-Za-z][\w-]*…`) would match.
_BUSY_LINE = "  esc to interrupt"
_PROMPT_GLYPH = "›"
# The exact wire shape `overseer/herdr_write_calls.py` documents as the ONE usable
# delivery form: one bracketed paste carrying no carriage return, submitted by a
# separate `Enter`.
_PASTE_START = "\x1b[200~"
_PASTE_END = "\x1b[201~"
# A terminal only BRACKETS a paste for an application that asked it to. A real TUI
# sets this on startup; without it herdr delivers the payload unbracketed and a
# multi-line wrap-up fragments into one submitted prompt per line.
_ENABLE_BRACKETED_PASTE = "\x1b[?2004h"
_DISABLE_BRACKETED_PASTE = "\x1b[?2004l"
_CLEAR_SCREEN = "\x1b[2J\x1b[H"
_TURN_SECONDS = 1.0
_IDLE_POLL_SECONDS = 0.05
_TRANSCRIPT_ROWS = 24
_COMPOSER_WIDTH = 100


def set_process_name() -> None:
    """Present as `codex` in `/proc/<pid>/comm`, fail-soft on a libc without prctl."""
    with contextlib.suppress(OSError, AttributeError):
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(_PR_SET_NAME, _PROCESS_NAME, 0, 0, 0)


def codex_home() -> Path:
    """Where this stub keeps its rollouts and its session index."""
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))


def rollout_path(*, home: Path, session_id: str, now: datetime) -> Path:
    """The dated rollout path whose FILENAME carries `session_id`.

    The shipped join parses the uuid straight out of this basename and never opens
    the body, so the layout matters and the contents do not.
    """
    stamp = now.strftime("%Y-%m-%dT%H-%M-%S")
    directory = home / "sessions" / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d")
    return directory / f"rollout-{stamp}-{session_id}.jsonl"


def render_screen(*, transcript: list[str], composer: str, ctx_percent: int, busy: bool) -> str:
    """One full frame in the shape `signals.py` parses.

    The `›` composer sits directly above the statusline, and the statusline is
    inside the last four non-empty rows -- `parse_ctx_remaining` scans no further.
    """
    rows = [*transcript[-_TRANSCRIPT_ROWS:], ""]
    if busy:
        rows.append(_BUSY_LINE)
    # COLLAPSED to one row on purpose. A held multi-line payload rendered verbatim
    # would push the statusline out of the four trailing non-empty rows
    # `parse_ctx_remaining` scans, and the wrap-up's own numbered steps would sit in
    # the frame where `is_structured_gate` looks for a picker's option block.
    rows.append(f"{_PROMPT_GLYPH} {' '.join(composer.split())}"[:_COMPOSER_WIDTH])
    rows.append(f"  stub-codex  ·  Context {ctx_percent}% left")
    return _CLEAR_SCREEN + "\r\n".join(rows) + "\r\n"


class StubCodex:
    """One stub session: a held rollout, a composer, and a renameable index record."""

    def __init__(
        self,
        *,
        home: Path,
        ctx_percent: int,
        never_idle: bool,
        output: TextIO,
        turn_seconds: float = _TURN_SECONDS,
    ) -> None:
        self.home = home
        self.ctx_percent = ctx_percent
        self.never_idle = never_idle
        self.output = output
        self.turn_seconds = turn_seconds
        self.session_id = str(uuid.uuid4())
        self.transcript: list[str] = [f"stub codex session {self.session_id}"]
        self.composer = ""
        self.pending = ""
        self.pasting = False
        self.thread_name: str | None = None
        self.rollout = rollout_path(
            home=home, session_id=self.session_id, now=datetime.now(tz=timezone.utc)
        )
        self.rollout.parent.mkdir(parents=True, exist_ok=True)
        # HELD for the whole run: an open fd on this file is the live-process half of
        # the discovery join, and closing it would make the session undiscoverable.
        self.rollout_fd = self.rollout.open("a", encoding="utf-8")

    def draw(self, *, busy: bool = False) -> None:
        """Repaint the frame the daemon will capture."""
        frame = render_screen(
            transcript=self.transcript,
            composer=self.composer,
            ctx_percent=self.ctx_percent,
            busy=busy or self.never_idle,
        )
        _ = self.output.write(frame)
        self.output.flush()

    def index_record(self, *, thread_name: str) -> None:
        """Append the durable `id -> thread_name` record a `/rename` produces.

        The daemon's fresh-restart arm proves the successor's NAME from this record
        rather than from a live join, because the record is written while the
        successor is still idle and outlives the process.
        """
        self.thread_name = thread_name
        index = self.home / "session_index.jsonl"
        index.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "id": self.session_id,
            "thread_name": thread_name,
            "updated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        with index.open("a", encoding="utf-8") as handle:
            _ = handle.write(json.dumps(record) + "\n")

    def run_turn(self, *, submitted: str) -> None:
        """Handle one submitted composer line, busy for as long as it takes."""
        self.composer = ""
        self.transcript.append(f"{_PROMPT_GLYPH} {' '.join(submitted.split())}"[:_COMPOSER_WIDTH])
        self.draw(busy=True)
        if submitted.startswith("/rename "):
            # A slash command asks the model for nothing, so a real Codex never goes
            # busy for one. The daemon knows that and confirms a rename from the
            # index record instead -- so the stub returns straight to idle.
            self.index_record(thread_name=submitted[len("/rename ") :].strip())
            self.transcript.append(f"renamed to {self.thread_name}")
            self.draw()
            return
        if submitted.startswith("!"):
            self._run_shell(command=submitted[1:].strip())
            return
        time.sleep(self.turn_seconds)
        self.transcript.append("(stub turn complete)")
        self.draw()

    def _run_shell(self, *, command: str) -> None:
        """Run a shell command the way an agent asked to run one would."""
        completed = subprocess.run(  # noqa: S602 - a stub agent running what it is told
            command, shell=True, capture_output=True, text=True, check=False
        )
        self.transcript.append(f"$ {command}")
        self.transcript.extend((completed.stdout + completed.stderr).splitlines()[-8:])
        self.transcript.append(f"(exit {completed.returncode})")
        self.draw()

    def feed(self, *, data: str) -> None:
        """Apply one chunk of pane input, submitting only on a real Enter.

        BRACKETED PASTE IS LOAD-BEARING, not a nicety. The daemon delivers a
        multi-line payload as ONE `\\x1b[200~...\\x1b[201~` paste carrying no
        carriage return, and submits separately with `Enter` -- precisely so the
        payload cannot fragment into several submitted prompts. A stub that
        submitted on every newline would fragment the wrap-up into forty turns and
        prove the opposite of what the exercise is for.
        """
        self.pending += data
        while self.pending:
            if self.pasting:
                end = self.pending.find(_PASTE_END)
                if end < 0:
                    self.composer += self.pending
                    self.pending = ""
                    break
                self.composer += self.pending[:end]
                self.pending = self.pending[end + len(_PASTE_END) :]
                self.pasting = False
                self.draw()
                continue
            start = self.pending.find(_PASTE_START)
            if start == 0:
                self.pending = self.pending[len(_PASTE_START) :]
                self.pasting = True
                continue
            head, self.pending = (
                (self.pending, "") if start < 0 else (self.pending[:start], self.pending[start:])
            )
            self._feed_keys(keys=head)

    def _feed_keys(self, *, keys: str) -> None:
        """Apply ordinary (non-pasted) keystrokes."""
        for char in keys:
            if char in "\r\n":
                self.run_turn(submitted=self.composer.strip())
            elif char in "\x7f\b":
                self.composer = self.composer[:-1]
            elif char == "\x03":
                raise KeyboardInterrupt
            else:
                self.composer += char


def _read_available(*, stream: TextIO) -> str:
    """Whatever is on the pane's input right now, blocking for at most one poll."""
    import select

    ready, _, _ = select.select([stream], [], [], _IDLE_POLL_SECONDS)
    if not ready:
        return ""
    return os.read(stream.fileno(), 4096).decode(errors="replace")


def _loop(*, session: StubCodex, stdin: TextIO) -> None:
    _ = session.output.write(_ENABLE_BRACKETED_PASTE)
    session.output.flush()
    session.draw()
    while True:
        chunk = _read_available(stream=stdin)
        if chunk:
            session.feed(data=chunk)


def _stop_on_termination(_signum: int, _frame: object) -> None:
    """Leave the raw terminal through ``main``'s restoration path on SIGTERM."""
    raise KeyboardInterrupt


def main(*, argv: list[str] | None = None) -> int:
    """Run the stub until it is interrupted or its pane is closed."""
    set_process_name()
    parser = argparse.ArgumentParser(prog="codex", add_help=False)
    _ = parser.add_argument("--dangerously-bypass-approvals-and-sandbox", action="store_true")
    _ = parser.add_argument("-m", "--model", default=None)
    _ = parser.add_argument("-c", "--config", action="append", default=[])
    _ = parser.add_argument("prompt", nargs="*")
    _, _unknown = parser.parse_known_args(argv)
    session = StubCodex(
        home=codex_home(),
        ctx_percent=int(os.environ.get("STUB_CODEX_CTX_PERCENT", "60")),
        never_idle=os.environ.get("STUB_CODEX_NEVER_IDLE") == "1",
        output=sys.stdout,
    )
    descriptor = sys.stdin.fileno()
    saved = termios.tcgetattr(descriptor)
    previous_sigterm = signal.signal(signal.SIGTERM, _stop_on_termination)
    try:
        tty.setraw(descriptor)
        _loop(session=session, stdin=sys.stdin)
    except (KeyboardInterrupt, OSError):
        return 0
    finally:
        _ = signal.signal(signal.SIGTERM, previous_sigterm)
        _ = session.output.write(_DISABLE_BRACKETED_PASTE)
        session.output.flush()
        termios.tcsetattr(descriptor, termios.TCSADRAIN, saved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
