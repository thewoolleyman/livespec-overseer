"""Repo-level tests for the daemon-owned runtime prefix."""

import importlib
import shlex
from pathlib import Path

from overseer.version import APP_VERSION

__all__: list[str] = []

_MODULE_PATH = Path(__file__).resolve().parent.parent / "overseer" / "runtime_prefix.py"


def test_runtime_prefix_is_versioned_under_daemon_owned_home(*, tmp_path):
    assert _MODULE_PATH.is_file()
    mod = importlib.import_module("overseer.runtime_prefix")

    assert mod.runtime_prefix(home=tmp_path) == (
        tmp_path / ".local" / "share" / "livespec-overseer" / "runtime" / APP_VERSION
    )


def test_daemon_executable_points_inside_the_runtime_venv(*, tmp_path):
    assert _MODULE_PATH.is_file()
    mod = importlib.import_module("overseer.runtime_prefix")

    assert mod.daemon_executable(prefix=tmp_path) == tmp_path / "venv" / "bin" / "overseerd"


def test_ensure_runtime_installs_the_released_distribution_not_the_checkout(*, tmp_path):
    assert _MODULE_PATH.is_file()
    mod = importlib.import_module("overseer.runtime_prefix")
    calls: list[list[str]] = []

    def fake_run(*, argv: list[str]) -> int:
        calls.append(argv)
        return 0

    prefix = tmp_path / "prefix"

    assert mod.ensure_runtime(prefix=prefix, run=fake_run) == prefix / "venv" / "bin" / "overseerd"

    assert calls[0][-2:] == ["-m", "venv"]
    install = calls[1]
    assert install[:3] == [str(prefix / "venv" / "bin" / "python"), "-m", "pip"]
    assert f"livespec-overseer=={APP_VERSION}" in install
    assert all(str(Path.cwd()) not in arg for arg in install)


def test_daemon_command_can_target_an_isolated_runtime_executable(*, tmp_path):
    mod = importlib.import_module("overseer.start")
    runtime_overseerd = tmp_path / "runtime" / "1.28.3" / "venv" / "bin" / "overseerd"
    log_path = tmp_path / "daemon.log"

    command = mod.daemon_command(
        warn_percent=30,
        log_path=log_path,
        daemon_executable=runtime_overseerd,
    )

    assert command == (
        f"{shlex.quote(str(runtime_overseerd))} --warn-percent 30 "
        f"2>> {shlex.quote(str(log_path))}"
    )
