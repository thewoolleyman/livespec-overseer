#!/usr/bin/env python3
"""Check version-keyed Claude idle-prompt fixtures."""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OVERSEER_DIR = _REPO_ROOT / "overseer"
if str(_OVERSEER_DIR) not in sys.path:
    sys.path.insert(0, str(_OVERSEER_DIR))

import signals  # noqa: E402

__all__: list[str] = [
    "installed_claude_version",
    "live_idle_capture",
    "main",
]

_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "claude-idle"
_CAPTURE_SCRIPT = _REPO_ROOT / "scripts" / "capture-claude-idle-canary.py"
_VERSION_RE = re.compile(r"\b(\d+\.\d+\.\d+)\b")
_COMMAND_TIMEOUT_SECONDS = 5.0

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _write_stderr(*, text: str) -> None:
    _ = sys.stderr.write(text)


def _write_stdout(*, text: str) -> None:
    _ = sys.stdout.write(text)


def installed_claude_version(*, run: CommandRunner = subprocess.run) -> str | None:
    try:
        completed = run(
            ["claude", "--version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):  # pragma: no cover
        return None
    if completed.returncode != 0:  # pragma: no cover
        return None
    return next(iter(_VERSION_RE.findall(completed.stdout)), None)


def _registered_fixture_paths() -> list[Path]:
    return sorted(_FIXTURE_DIR.glob("*.txt"))


def _registered_versions() -> set[str]:
    return {path.stem for path in _registered_fixture_paths()}


def _fixture_is_valid(*, path: Path) -> bool:
    """Whether the detector still sees this registered build's idle INPUT BOX.

    Deliberately the box predicates only. A context percentage is NOT required,
    for the same reason the capture no longer waits for one: a freshly launched
    `claude -n <topic>` pane renders the input box immediately while its
    statusline carries no context segment at all, so a fixture captured from one
    legitimately has no reading to parse. Requiring it here would reject every
    fixture the repaired capture can actually produce, which is how this check
    came to block every commit on a host whose Claude had auto-updated.

    The context parse is still guarded, just not here:
    `test_every_registered_idle_fixture_matches_the_detector` asserts each
    fixture parses to exactly the reading it literally carries, or to `None`
    when it carries none — so a detector that mis-parsed or hallucinated a
    percentage still fails, while an extendable registry stays extendable.
    """
    capture = path.read_text(encoding="utf-8")
    return signals.is_idle_input(capture_text=capture) and signals.input_box_ready(
        capture_text=capture
    )


def _fixtures_are_valid() -> bool:
    paths = _registered_fixture_paths()
    return bool(paths) and all(_fixture_is_valid(path=path) for path in paths)


def _capture_module() -> ModuleType:
    """The capture script, loaded by path because its filename is not importable."""
    spec = importlib.util.spec_from_file_location("capture_claude_idle_canary", _CAPTURE_SCRIPT)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise AssertionError(_CAPTURE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def live_idle_capture() -> str | None:
    """One live idle capture from the capture recipe's own disposable tmux session.

    Deliberately the capture script's implementation rather than a second copy
    of it: the evidence this check accepts for an unregistered build has to be
    the same evidence `just capture-claude-idle-canary` would store as that
    build's fixture, and two copies of the capture would be free to drift.
    """
    text: str | None = _capture_module().live_idle_capture().text
    return text


def _live_capture_is_valid(*, capture: str, version: str) -> bool:
    """Judge a LIVE capture by exactly the registered-fixture predicates.

    Written to a temp file so it runs through `_fixture_is_valid` itself rather
    than through a restatement of it — the registered corpus and the live probe
    must agree on what "the detector still sees the idle input box" means, or
    the gate stops standing for anything.
    """
    with tempfile.TemporaryDirectory() as directory:
        probe = Path(directory) / f"{version}.txt"
        probe.write_text(capture, encoding="utf-8")
        return _fixture_is_valid(path=probe)


def _unregistered_build_outcome(*, version: str) -> int:
    """Judge an installed build that has no registered fixture.

    A missing fixture file is REGISTRY LAG, and the registry lags on every host
    Claude Code auto-update. The property this canary actually protects is that
    the detector still recognizes the installed build's idle input box, so the
    live capture is what separates the two, into three outcomes:

    - the detector ACCEPTS the capture: supervision is intact and the gap is
      only unrecorded, so the gate passes with an advisory;
    - the detector REJECTS it: supervision cannot see this host's idle input box
      and that is the real stop-the-line, so it keeps the loud DETECTOR_FAILURE
      diagnosis rather than being dressed up as routine registry lag — pointing
      an operator at the capture recipe would be the wrong instruction, since a
      fixture the detector cannot read fixes nothing;
    - no capture can be OBTAINED: there is no evidence either way, and the gate
      must never pass on none, so today's refusal stands unchanged.
    """
    capture = live_idle_capture()
    if capture is None:
        _write_stderr(
            text=(
                "CLAUDE_IDLE_CANARY_MISSING_FIXTURE: installed Claude Code "
                f"{version} has no idle fixture and no live idle capture could be "
                "obtained; run `just capture-claude-idle-canary`\n"
            )
        )
        return 1
    if not _live_capture_is_valid(capture=capture, version=version):
        _write_stderr(
            text=(
                "CLAUDE_IDLE_CANARY_DETECTOR_FAILURE: the idle detector does not "
                f"recognize the live idle input box of installed Claude Code {version}\n"
            )
        )
        return 1
    _write_stderr(
        text=(
            f"CLAUDE_IDLE_CANARY_UNREGISTERED: installed Claude Code {version} has no "
            "registered idle fixture, but the detector recognizes its live idle input "
            "box; run `just capture-claude-idle-canary` to register it\n"
        )
    )
    return 0


def _check(*, run: CommandRunner) -> int:
    if not _fixtures_are_valid():  # pragma: no cover
        _write_stderr(text="CLAUDE_IDLE_CANARY_DETECTOR_FAILURE: registered idle fixture failed\n")
        return 1
    version = installed_claude_version(run=run)
    if version is None:  # pragma: no cover
        _write_stderr(text="CLAUDE_IDLE_CANARY_SKIPPED: claude --version is unavailable on PATH\n")
        return 0
    if version not in _registered_versions():
        return _unregistered_build_outcome(version=version)
    _write_stdout(text=f"claude idle canary ok for Claude Code {version}\n")
    return 0


def main(*, argv: Sequence[str] | None = None, run: CommandRunner = subprocess.run) -> int:
    parser = argparse.ArgumentParser(prog="claude-idle-canary")
    subcommands = parser.add_subparsers(dest="command", required=True)
    _ = subcommands.add_parser("check", help="validate registered fixtures and installed build")
    args = parser.parse_args(argv)
    if args.command == "check":
        return _check(run=run)
    raise AssertionError(args.command)  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
