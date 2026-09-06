"""Executable E2E gate for every shipped plugin ``bin/`` launcher.

The inventory is ENUMERATED FROM THE TREE rather than tabulated here, so the gate
follows the shipped surface as it changes: when the foreman seat was retired
(SPECIFICATION v047) its eight launchers left `bin/` and this test simply stopped
probing them. The three foreman-specific E2E cases that used to sit beside it --
the `foreman-act` plugin-cache filing, its occupied-tmux refusal, and the seeded
seed-session/attention/cadence walk -- went with the launchers they drove.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_BIN = ROOT / ".claude-plugin" / "bin"


def _scrubbed_env() -> dict[str, str]:
    removed = {"PYTHONPATH", "COVERAGE_PROCESS_START"}
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in removed and not key.startswith("COV_CORE_")
    }
    assert "PYTHONPATH" not in env
    return env


def test_every_plugin_bin_entrypoint_executes_help_from_clean_environment():
    entrypoints = sorted(path for path in PLUGIN_BIN.iterdir() if path.is_file())
    assert entrypoints, "plugin bin directory must ship executable entrypoints"

    failures: list[str] = []
    for entrypoint in entrypoints:
        completed = subprocess.run(  # noqa: S603
            [str(entrypoint), "--help"],
            cwd=ROOT,
            env=_scrubbed_env(),
            check=False,
            capture_output=True,
            text=True,
            timeout=15.0,
        )
        combined = completed.stdout + completed.stderr
        if completed.returncode != 0 or "Traceback" in combined:
            failures.append(
                f"{entrypoint.name} exited {completed.returncode}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
            continue
        assert f"usage: {entrypoint.name}" in combined

    assert failures == []
