"""Repo-level tests for the daemon-owned runtime prefix."""

import importlib
import json
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

    assert calls[0] == ["uv", "venv", str(prefix / "venv")]
    install = calls[1]
    assert install[:4] == ["uv", "pip", "install", "--python"]
    assert install[4] == str(prefix / "venv" / "bin" / "python")
    assert "--no-deps" in install
    assert "-m" not in install
    assert "pip" not in install[4:]
    assert mod.runtime_install_source() in install
    assert mod.runtime_install_source().endswith(f"@v{APP_VERSION}")
    assert "git+https://github.com/thewoolleyman/livespec-overseer.git" in (
        mod.runtime_install_source()
    )
    assert all(str(Path.cwd()) not in arg for arg in install)


def test_failed_runtime_provision_removes_the_partial_prefix(*, tmp_path):
    mod = importlib.import_module("overseer.runtime_prefix")
    prefix = tmp_path / "prefix"
    calls: list[list[str]] = []

    def fail_venv(*, argv: list[str]) -> int:
        calls.append(argv)
        (prefix / "venv" / "bin").mkdir(parents=True)
        (prefix / "venv" / "pyvenv.cfg").write_text("broken\n", encoding="utf-8")
        (prefix / "venv" / "bin" / "python").write_text("broken\n", encoding="utf-8")
        return 1

    assert mod.ensure_runtime(prefix=prefix, run=fail_venv) is None
    assert calls == [["uv", "venv", str(prefix / "venv")]]
    assert not prefix.exists()


def test_runtime_provision_install_step_uses_uv_and_cleans_failure(*, tmp_path):
    mod = importlib.import_module("overseer.runtime_prefix")
    prefix = tmp_path / "prefix"
    calls: list[list[str]] = []

    def fail_install(*, argv: list[str]) -> int:
        calls.append(argv)
        if str(prefix / "venv") in argv and "install" not in argv:
            (prefix / "venv" / "bin").mkdir(parents=True)
            (prefix / "venv" / "pyvenv.cfg").write_text("uv\n", encoding="utf-8")
            (prefix / "venv" / "bin" / "python").write_text("python\n", encoding="utf-8")
            return 0
        return 1

    assert mod.ensure_runtime(prefix=prefix, run=fail_install) is None
    assert calls[1][:5] == [
        "uv",
        "pip",
        "install",
        "--python",
        str(prefix / "venv" / "bin" / "python"),
    ]
    assert "-m" not in calls[1]
    assert not prefix.exists()


def test_runtime_provision_failure_blocks_the_release_currency_verdict(*, tmp_path):
    mod = importlib.import_module("overseer._supervisor_release_runtime")
    release = "2222222222222222222222222222222222222222"
    current = "1111111111111111111111111111111111111111"
    installs: list[str] = []

    class Completed:
        def __init__(self, *, stdout: str) -> None:
            self.stdout = stdout

    def run(argv, *, capture_output, text, check, timeout):
        endpoint = argv[-1]
        if endpoint.endswith("/commits/release"):
            return Completed(stdout=json.dumps({"sha": release}))
        if endpoint.endswith(f"/commits/v{mod.APP_VERSION}"):
            return Completed(stdout=json.dumps({"sha": current}))
        return Completed(stdout=json.dumps({"check_runs": [{"conclusion": "success"}]}))

    def ensure_release_runtime(*, release: str) -> Path | None:
        installs.append(release)
        return None

    adapter = mod.ReleaseRuntimeAdapter(
        sup=object(),
        run=run,
        ensure_release_runtime=ensure_release_runtime,
    )

    verdict = adapter.currency_check()

    assert verdict["eligible"] is False
    assert verdict["blocked"] is True
    assert verdict["target"] == release
    assert verdict["reason"] == "release runtime provisioning failed"
    assert adapter.reexec_target() is None
    assert installs == [release]


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
