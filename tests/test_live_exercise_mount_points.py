"""Every Bubblewrap mount the live exercise requests must have a creatable mount point.

Measured on a namespace-capable host 2026-10-12: the exercise ro-binds the host root
and then bound the evidence directory at ``/evidence``. A read-only root cannot grow
a new top-level directory, so bwrap aborted with ``Can't mkdir /evidence: Read-only
file system`` before any backend started. The factory sandbox denies namespaces
outright, so only a real host run could reach the defect.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
LIVE_EXERCISE = ROOT / "scripts" / "overseer-live-exercise.sh"
_MOUNT_OPTIONS = {"--bind", "--ro-bind"}


def _namespace_argv(*, evidence: Path) -> list[str]:
    completed = subprocess.run(  # noqa: S603 -- fixed repo-owned script.
        [
            str(LIVE_EXERCISE),
            "run",
            "--plan-only",
            "--backend",
            "herdr",
            "--agent",
            "claude",
            "--topic",
            "mount-points",
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
    )
    assert "no namespace or terminal was started" in completed.stdout
    return (evidence / "namespace.argv").read_text(encoding="utf-8").splitlines()


def _destinations(*, argv: list[str]) -> list[tuple[str, str]]:
    mounts: list[tuple[str, str]] = []
    for index, token in enumerate(argv):
        if token in _MOUNT_OPTIONS:
            mounts.append((token, argv[index + 2]))
    return mounts


def _host_supplied() -> set[str]:
    # The only mount points the exercise may expect the operator host to provide.
    # Fixed by contract rather than read from this machine's filesystem, so the
    # verdict cannot depend on the host the test runs on.
    return {"/", "/tmp", os.environ["HOME"], f"/run/user/{os.getuid()}", str(ROOT)}


def test_every_mount_point_is_host_supplied_or_under_a_writable_bind(tmp_path: Path) -> None:
    argv = _namespace_argv(evidence=tmp_path / "evidence")
    host_supplied = _host_supplied()
    writable: list[str] = []
    for option, destination in _destinations(argv=argv):
        creatable = destination in host_supplied or any(
            destination.startswith(f"{parent.rstrip('/')}/") for parent in writable
        )
        assert creatable, f"bwrap cannot create mount point {destination} on a read-only root"
        if option == "--bind" and destination != "/":
            writable.append(destination)
