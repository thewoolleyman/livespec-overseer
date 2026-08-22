"""Install and locate the daemon-owned overseer runtime prefix."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from version import APP_VERSION

__all__: list[str] = [
    "daemon_executable",
    "ensure_current_runtime",
    "ensure_runtime",
    "runtime_install_source",
    "runtime_prefix",
]

_PROJECT_NAME = "livespec-overseer"
_PROJECT_GIT_URL = "https://github.com/thewoolleyman/livespec-overseer.git"
_VENV_COMMAND_LEN = 4


def runtime_prefix(*, home: Path | None = None) -> Path:
    """Versioned daemon-owned prefix, independent of any checkout."""
    root = Path.home() if home is None else home
    return root / ".local" / "share" / "livespec-overseer" / "runtime" / APP_VERSION


def daemon_executable(*, prefix: Path) -> Path:
    """The ``overseerd`` console script inside a runtime prefix's venv."""
    return prefix / "venv" / "bin" / "overseerd"


def runtime_install_source() -> str:
    """Immutable git source for the adopted release, never the working tree."""
    return f"{_PROJECT_NAME} @ git+{_PROJECT_GIT_URL}@v{APP_VERSION}"


def _venv_python(*, prefix: Path) -> Path:
    return prefix / "venv" / "bin" / "python"


def _run_command(*, argv: list[str]) -> int:
    actual = argv
    if len(argv) == _VENV_COMMAND_LEN and argv[-2:] == ["-m", "venv"]:
        actual = [argv[0], "-m", "venv", argv[1]]
    completed = subprocess.run(actual, check=False)  # noqa: S603 - fixed provisioning argv.
    return completed.returncode


def ensure_runtime(
    *,
    prefix: Path,
    run: Callable[..., int] | None = None,
) -> Path | None:
    """Ensure ``prefix`` contains a non-editable install of the adopted release."""
    target = daemon_executable(prefix=prefix)
    if target.is_file():
        return target

    runner = _run_command if run is None else run
    prefix.mkdir(parents=True, exist_ok=True)
    venv_rc = runner(argv=[sys.executable, str(prefix / "venv"), "-m", "venv"])
    if venv_rc != 0:
        return None

    install_rc = runner(
        argv=[
            str(_venv_python(prefix=prefix)),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            runtime_install_source(),
        ]
    )
    if install_rc != 0:
        return None
    return target


def ensure_current_runtime() -> Path | None:
    """Ensure the current package version exists under the daemon-owned prefix."""
    return ensure_runtime(prefix=runtime_prefix())
