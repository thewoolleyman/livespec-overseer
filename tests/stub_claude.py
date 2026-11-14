#!/usr/bin/env python3
"""A minimal idle Claude TUI for the private-tmux lifecycle exercise.

The fixture presents only the evidence the released overseer reads: Claude's
registry row, a live process identity, and the bordered idle composer parsed by
``signals.is_idle_input``.  It is not a Claude implementation.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import os
import select
import signal
import sys
import termios
import tty
from pathlib import Path
from typing import TextIO

__all__: list[str] = ["main"]

_CHECKOUT = Path(__file__).resolve().parents[1]
if str(_CHECKOUT) not in sys.path:
    sys.path.insert(0, str(_CHECKOUT))

_PR_SET_NAME = 15
_PROCESS_NAME = b"claude"
_ENABLE_BRACKETED_PASTE = "\x1b[?2004h"
_DISABLE_BRACKETED_PASTE = "\x1b[?2004l"
_PASTE_START = "\x1b[200~"
_PASTE_END = "\x1b[201~"
_CLEAR_SCREEN = "\x1b[2J\x1b[H"


def _process_starttime(*, pid: int) -> str:
    """Return proc stat's start-time field for the live registry identity."""
    raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    fields = raw[raw.rfind(")") + 1 :].split()
    return fields[19]


def _set_process_name() -> None:
    """Make the interpreter-backed fixture visible as ``claude`` in `/proc`."""
    with contextlib.suppress(OSError, AttributeError):
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(_PR_SET_NAME, _PROCESS_NAME, 0, 0, 0)


class StubClaude:
    """One registry-backed prompt which executes the exercise's shell submissions."""

    def __init__(self, *, topic: str, output: TextIO) -> None:
        self.topic = topic
        self.output = output
        self.never_idle = os.environ.get("STUB_CLAUDE_NEVER_IDLE") == "1"
        self.pending = ""
        self.pasting = False
        self.composer = ""
        self.pid = os.getpid()
        self.registry = Path.home() / ".claude" / "sessions" / f"{self.pid}.json"
        self._write_registry(status="idle")

    def _write_registry(self, *, status: str) -> None:
        self.registry.parent.mkdir(parents=True, exist_ok=True)
        _ = self.registry.write_text(
            json.dumps(
                {
                    "pid": self.pid,
                    "cwd": str(Path.cwd()),
                    "name": self.topic,
                    "status": status,
                    "procStart": _process_starttime(pid=self.pid),
                }
            ),
            encoding="utf-8",
        )

    def draw(self) -> None:
        """Render Claude's shipped empty-composer shape, or a deliberate busy frame."""
        prompt = "❯" if not self.never_idle else "Working…"
        frame = "\r\n".join(
            (
                _CLEAR_SCREEN + f"──── {self.topic} ────",
                prompt,
                "────────────────────",
                "Ctx: 75% left",
                "? for shortcuts",
            )
        )
        _ = self.output.write(frame + "\r\n")
        _ = self.output.flush()

    def submit(self, *, command: str) -> None:
        """Dispatch the two shipped exercise commands; other prompts are no-op turns."""
        self.composer = ""
        if "overseer-start" in command:
            self._write_registry(status="busy")
            from overseer.start import main as start

            _ = start()
            self._write_registry(status="idle")
        elif "declare.py" in command and command.rstrip().endswith(" ready"):
            self._write_registry(status="busy")
            from overseer.declare import main as declare

            _ = declare(argv=["ready"])
            self._write_registry(status="idle")
        self.draw()

    def feed(self, *, data: str) -> None:
        """Consume ordinary keys plus tmux's bracketed-paste protocol."""
        self.pending += data
        while self.pending:
            if self.pasting:
                end = self.pending.find(_PASTE_END)
                if end < 0:
                    self.composer += self.pending
                    self.pending = ""
                    return
                self.composer += self.pending[:end]
                self.pending = self.pending[end + len(_PASTE_END) :]
                self.pasting = False
                continue
            if self.pending.startswith(_PASTE_START):
                self.pending = self.pending[len(_PASTE_START) :]
                self.pasting = True
                continue
            character, self.pending = self.pending[0], self.pending[1:]
            if character in "\r\n":
                self.submit(command=self.composer.strip())
            elif character in "\x7f\b":
                self.composer = self.composer[:-1]
            else:
                self.composer += character


def _stop_on_termination(_signum: int, _frame: object) -> None:
    """Unwind through terminal restoration when `respawn-pane -k` terminates us."""
    raise KeyboardInterrupt


def _read_available(*, stream: TextIO) -> str:
    ready, _, _ = select.select([stream], [], [], 0.05)
    return os.read(stream.fileno(), 4096).decode(errors="replace") if ready else ""


def main(*, argv: list[str] | None = None) -> int:
    """Run the fixture until tmux replaces or closes its pane."""
    parser = argparse.ArgumentParser(prog="claude", add_help=False)
    _ = parser.add_argument("--dangerously-skip-permissions", action="store_true")
    _ = parser.add_argument("-n", dest="topic", required=True)
    parsed, _unknown = parser.parse_known_args(argv)
    _set_process_name()
    stub = StubClaude(topic=parsed.topic, output=sys.stdout)
    descriptor = sys.stdin.fileno()
    saved = termios.tcgetattr(descriptor)
    previous_sigterm = signal.signal(signal.SIGTERM, _stop_on_termination)
    try:
        tty.setraw(descriptor)
        _ = sys.stdout.write(_ENABLE_BRACKETED_PASTE)
        _ = sys.stdout.flush()
        stub.draw()
        while True:
            data = _read_available(stream=sys.stdin)
            if data:
                stub.feed(data=data)
    except (KeyboardInterrupt, OSError):
        return 0
    finally:
        _ = signal.signal(signal.SIGTERM, previous_sigterm)
        _ = sys.stdout.write(_DISABLE_BRACKETED_PASTE)
        _ = sys.stdout.flush()
        termios.tcsetattr(descriptor, termios.TCSADRAIN, saved)
        with contextlib.suppress(OSError):
            stub.registry.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
