"""A Herdr launch must leave the agent itself as the pane's foreground leader.

Reproduced on 2026-10-12 in the isolated live exercise: after a ready restart the
successor ran as ``sh -c claude ...``, so the pane's foreground group leader was
``sh`` with Claude as its child. The daemon's managed-Claude check then refused its
own successor ("observed process is not the recorded Claude runtime"), and the
continuation prompt was never sent.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

import herdr_launch

__all__: list[str] = []

_REPORT = (
    "import os; " "parent = open(f'/proc/{os.getppid()}/comm').read().strip(); " "print(parent)"
)


def test_the_launched_command_replaces_the_wrapper_shell(tmp_path: Path) -> None:
    command = shlex.join([sys.executable, "-c", _REPORT])
    rendered = herdr_launch.render_launch(cwd=str(tmp_path), command=command, env={"X_PROOF": "1"})

    completed = subprocess.run(  # noqa: S603 -- the rendered line under test.
        ["/bin/bash", "-c", f"{rendered}; true"],
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "bash"
