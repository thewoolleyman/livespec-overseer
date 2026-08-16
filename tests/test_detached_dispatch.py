"""Detached-dispatch helper survival demo."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from contextlib import suppress
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent
_HELPER = _REPO_ROOT / "scripts" / "detached-dispatch.sh"


def _wait_for_text(*, path: Path, text: str, timeout: float = 10.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            body = path.read_text(encoding="utf-8")
            if text in body:
                return body
        time.sleep(0.05)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def _wait_for_file(*, path: Path, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            return
        time.sleep(0.05)
    raise AssertionError(f"{path} was not created before timeout")


def test_detached_dispatch_survives_parent_process_group_termination(*, tmp_path: Path) -> None:
    """A launched command must outlive the bash process tree that spawned it."""
    run_dir = tmp_path / "dispatch"
    parent_ready = tmp_path / "parent-ready"
    parent_script = tmp_path / "parent.sh"
    parent_script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f'"{_HELPER}" "{run_dir}" -- bash -c '
                "'sleep 1; printf \"%s\\n\" survived; exit 7'",
                f': > "{parent_ready}"',
                "sleep 60",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.Popen(  # noqa: S603
        ["/usr/bin/setsid", "/usr/bin/bash", str(parent_script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_file(path=parent_ready, timeout=5.0)
        os.killpg(proc.pid, signal.SIGTERM)

        output = _wait_for_text(path=run_dir / "output.log", text="survived")
        verdict = _wait_for_text(path=run_dir / "verdict.env", text="status=failed")
    finally:
        with suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)

    assert output == "survived\n"
    assert "status=failed\n" in verdict
    assert "exit_code=7\n" in verdict
    assert (run_dir / "pid").read_text(encoding="utf-8").strip().isdigit()


def test_loop_parked_dispatch_guidance_points_to_detached_disk_verdict() -> None:
    """The retired task-notification pattern must stay superseded in owned docs."""
    docs = [
        _REPO_ROOT / "AGENTS.md",
        _REPO_ROOT / "overseer" / "AGENTS.md",
        _REPO_ROOT / ".claude-plugin" / "prose" / "overseer.md",
        _REPO_ROOT / ".claude-plugin" / "prose" / "supervise-plan.md",
    ]
    for path in docs:
        text = path.read_text(encoding="utf-8")
        assert "scripts/detached-dispatch.sh" in text
        assert "verdict.env" in text
        assert "run_in_background: true" in text
        assert "ScheduleWakeup" in text
