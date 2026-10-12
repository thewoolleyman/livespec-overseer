"""A mise-shimmed uv under the operator home must reach the namespace as the real tool.

`overseer-start` is a `uv run --script` shim, so a lifecycle run needs `uv` inside the
namespace. On the operator host `uv` resolves to `~/.local/share/mise/shims/uv`, a
link to `mise` that dispatches on its own name and reads mise's install tree under
the home. The scratch home hides that tree, so binding the shim (which is `mise`
itself) would still leave no working `uv`. The real binary must be bound at the
shim's path.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
LIVE_EXERCISE = ROOT / "scripts" / "overseer-live-exercise.sh"


def _executable(*, path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_a_mise_shimmed_uv_is_bound_as_the_real_binary(tmp_path: Path) -> None:
    home = tmp_path / "home"
    real_uv = _executable(path=home / ".local/share/mise/installs/uv/0.9.0/uv", body="exit 0")
    tools = tmp_path / "tools"
    mise = _executable(
        path=tools / "mise",
        body=f'[ "$1" = which ] && [ "$2" = uv ] && echo {real_uv} && exit 0\nexit 1',
    )
    shims = home / ".local/share/mise/shims"
    shims.mkdir(parents=True)
    shim = shims / "uv"
    shim.symlink_to(mise)
    evidence = tmp_path / "evidence"
    environment = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{shims}:{tools}:{os.environ['PATH']}",
    }

    subprocess.run(  # noqa: S603 -- fixed repo-owned script.
        [
            str(LIVE_EXERCISE),
            "run",
            "--plan-only",
            "--backend",
            "tmux",
            "--agent",
            "claude",
            "--topic",
            "shim-tools",
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
    mounts = [tuple(argv[i : i + 3]) for i, token in enumerate(argv) if token == "--ro-bind"]
    assert ("--ro-bind", str(real_uv), str(shim)) in mounts
