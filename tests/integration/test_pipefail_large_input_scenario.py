"""Integration scenario: a pipefail script reports a match in a large input as a match."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

__all__: list[str] = []

pytestmark = pytest.mark.integration

LIVE_EXERCISE = Path(__file__).resolve().parents[2] / "scripts" / "overseer-live-exercise.sh"


@pytest.mark.parametrize("exec_lines", [1, 20000])
def test_scenario_a_pipefail_script_reports_a_match_in_a_large_input_as_a_match(
    tmp_path: Path, exec_lines: int
) -> None:
    text = LIVE_EXERCISE.read_text(encoding="utf-8")
    start = text.index("launcher_exec_tokens() {")
    function = text[start : text.index("\n}\n", start) + 3]
    launcher = tmp_path / "launcher"
    launcher.write_text("#!/bin/sh\n" + "exec /bin/true arg\n" * exec_lines, encoding="utf-8")
    program = f'{function}\nlauncher_exec_tokens "$1"'

    completed = subprocess.run(  # noqa: S603 -- fixed bash invocation.
        ["bash", "-euo", "pipefail", "-c", program, "bash", str(launcher)],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )

    assert (completed.returncode, completed.stdout) == (0, "/bin/true\narg\n")
