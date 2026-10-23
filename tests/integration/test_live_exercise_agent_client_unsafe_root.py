"""An install root the exercise itself owns is refused, never bound read-only over it.

The runner writes four operator-home directories inside the namespace: the scratch home
at the operator home path, the agent credential under `~/.claude` or `~/.codex`, and the
Herdr client socket under `~/.config` (`scripts/overseer-live-exercise-inside.sh`). A
launcher whose executed content resolves to one of those roots cannot be made runnable by
binding it: binding the operator home would defeat the scratch home outright, and binding
one of the other three would make read-only a directory the exercise must write.

This set is the runner's OWN fixed list of the roots it writes. It is deliberately not a
denylist of home paths a launcher may name -- that list grows with every launcher, which
is why the first attempt at this fix could not converge -- so adding a root here means
the exercise started writing somewhere new.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent.parent
LIVE_EXERCISE = ROOT / "scripts" / "overseer-live-exercise.sh"

# Each case names the first-level home directory the fixture's launcher executes from.
# The empty one puts that content directly in the operator home, whose install root is
# the home itself.
_EXERCISE_OWNED_ROOTS = ("", ".claude", ".codex", ".config")


def _install_client(*, home: Path, inside: str) -> tuple[Path, Path]:
    """A launcher executing content inside one home directory; returns it and that root."""
    prefix = f"{inside}/bin/" if inside else ""
    runtime = home / f"{prefix}bun"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    runtime.chmod(0o755)
    (home / f"{prefix}codex").write_text("// codex\n", encoding="utf-8")
    launcher = home / ".local" / "bin" / "codex"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(
        f'#!/usr/bin/env bash\nexec "$HOME/{prefix}bun" "$HOME/{prefix}codex" "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    return launcher, (home / inside if inside else home)


@pytest.mark.parametrize("inside", _EXERCISE_OWNED_ROOTS)
def test_an_install_root_the_exercise_writes_is_refused_by_name(
    tmp_path: Path, inside: str
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    launcher, install_root = _install_client(home=home, inside=inside)
    evidence = tmp_path / "evidence"

    completed = subprocess.run(  # noqa: S603 -- fixed repo-owned script.
        [
            str(LIVE_EXERCISE),
            "run",
            "--backend",
            "herdr",
            "--agent",
            "codex",
            "--topic",
            "unsafe-install-root",
            "--checkout",
            str(ROOT),
            "--evidence",
            str(evidence),
            "--",
            "/bin/true",
        ],
        check=False,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "HOME": str(home),
            "TMPDIR": str(tmp_path),
            "PATH": f"{launcher.parent}{os.pathsep}{os.environ['PATH']}",
        },
    )

    assert completed.returncode != 0, completed.stdout
    assert str(install_root) in completed.stderr, completed.stderr
    # A full run rather than `--plan-only`, so an evidence directory the runner never
    # wrote to is itself the proof that no terminal backend was started.
    assert list(evidence.iterdir()) == [], "the runner wrote evidence before refusing"
