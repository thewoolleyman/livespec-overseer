"""Binaries installed under the operator home must stay reachable inside the namespace.

Measured on a namespace-capable host 2026-10-12: Herdr was installed at
``~/.local/bin/herdr``. The exercise replaces the operator home with a scratch home,
so the namespaced backend start failed with ``herdr: command not found`` and the
isolation check never reached a live backend. The same holds for an agent client
installed under the home, such as ``~/.local/bin/claude``.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
LIVE_EXERCISE = ROOT / "scripts" / "overseer-live-exercise.sh"


def _install(*, bin_dir: Path, name: str) -> Path:
    binary = bin_dir / name
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    return binary


def test_home_installed_backend_and_agent_are_bound_into_the_namespace(tmp_path: Path) -> None:
    home = tmp_path / "home"
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    herdr = _install(bin_dir=bin_dir, name="herdr")
    claude = _install(bin_dir=bin_dir, name="claude")
    evidence = tmp_path / "evidence"
    environment = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}

    subprocess.run(  # noqa: S603 -- fixed repo-owned script.
        [
            str(LIVE_EXERCISE),
            "run",
            "--plan-only",
            "--backend",
            "herdr",
            "--agent",
            "claude",
            "--topic",
            "home-binaries",
            "--checkout",
            str(ROOT),
            "--evidence",
            str(evidence),
            "--",
            "/bin/true",
        ],
        check=True,
        text=True,
        capture_output=True,
        env=environment,
    )

    argv = (evidence / "namespace.argv").read_text(encoding="utf-8").splitlines()
    mounts = [
        tuple(argv[index : index + 3]) for index, token in enumerate(argv) if token == "--ro-bind"
    ]
    assert ("--ro-bind", str(herdr), str(herdr)) in mounts
    assert ("--ro-bind", str(claude), str(claude)) in mounts
    home_bind = argv.index(str(home))
    assert all(argv.index(str(path)) > home_bind for path in (herdr, claude))
