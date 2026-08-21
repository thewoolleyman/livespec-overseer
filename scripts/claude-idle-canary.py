#!/usr/bin/env python3
"""Check version-keyed Claude idle-prompt fixtures."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OVERSEER_DIR = _REPO_ROOT / "overseer"
if str(_OVERSEER_DIR) not in sys.path:
    sys.path.insert(0, str(_OVERSEER_DIR))

import signals  # noqa: E402

__all__: list[str] = [
    "installed_claude_version",
    "main",
]

_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "claude-idle"
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
    capture = path.read_text(encoding="utf-8")
    return (
        signals.is_idle_input(capture_text=capture)
        and signals.input_box_ready(capture_text=capture)
        and signals.parse_ctx_remaining(capture_text=capture) is not None
    )


def _fixtures_are_valid() -> bool:
    paths = _registered_fixture_paths()
    return bool(paths) and all(_fixture_is_valid(path=path) for path in paths)


def _check(*, run: CommandRunner) -> int:
    if not _fixtures_are_valid():  # pragma: no cover
        _write_stderr(text="CLAUDE_IDLE_CANARY_DETECTOR_FAILURE: registered idle fixture failed\n")
        return 1
    version = installed_claude_version(run=run)
    if version is None:  # pragma: no cover
        _write_stderr(text="CLAUDE_IDLE_CANARY_SKIPPED: claude --version is unavailable on PATH\n")
        return 0
    if version not in _registered_versions():
        _write_stderr(
            text=(
                "CLAUDE_IDLE_CANARY_MISSING_FIXTURE: installed Claude Code "
                f"{version} has no idle fixture; run `just capture-claude-idle-canary`\n"
            )
        )
        return 1
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
