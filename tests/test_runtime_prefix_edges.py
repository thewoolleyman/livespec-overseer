"""Edge coverage for daemon runtime-prefix provisioning."""

import importlib
from pathlib import Path

__all__: list[str] = []


def test_ensure_runtime_reuses_existing_prefix_without_reinstall(*, tmp_path):
    mod = importlib.import_module("overseer.runtime_prefix")
    prefix = tmp_path / "prefix"
    target = prefix / "venv" / "bin" / "overseerd"
    target.parent.mkdir(parents=True)
    target.write_text("# existing\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fail_if_called(*, argv: list[str]) -> int:
        calls.append(argv)
        return 1

    assert mod.ensure_runtime(prefix=prefix, run=fail_if_called) == target
    assert calls == []


def test_ensure_runtime_reports_venv_creation_failure(*, tmp_path):
    mod = importlib.import_module("overseer.runtime_prefix")
    calls: list[list[str]] = []

    def fail_venv(*, argv: list[str]) -> int:
        calls.append(argv)
        return 1

    assert mod.ensure_runtime(prefix=tmp_path / "prefix", run=fail_venv) is None
    assert len(calls) == 1


def test_ensure_runtime_reports_install_failure(*, tmp_path):
    mod = importlib.import_module("overseer.runtime_prefix")
    calls: list[list[str]] = []

    def fail_install(*, argv: list[str]) -> int:
        calls.append(argv)
        return 1 if "pip" in argv else 0

    assert mod.ensure_runtime(prefix=tmp_path / "prefix", run=fail_install) is None
    assert len(calls) == 2


def test_real_runner_expands_the_semantic_venv_command(*, monkeypatch, tmp_path):
    mod = importlib.import_module("overseer.runtime_prefix")
    seen: list[list[str]] = []

    class _Completed:
        returncode = 0

    def fake_run(argv, *, check):
        assert check is False
        seen.append(list(argv))
        return _Completed()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    prefix = tmp_path / "prefix"
    assert mod.ensure_runtime(prefix=prefix) == prefix / "venv" / "bin" / "overseerd"
    assert seen[0][-3:] == ["-m", "venv", str(prefix / "venv")]


def test_ensure_current_runtime_uses_the_current_versioned_prefix(*, monkeypatch, tmp_path):
    mod = importlib.import_module("overseer.runtime_prefix")
    seen: dict[str, Path] = {}

    def fake_ensure(*, prefix):
        seen["prefix"] = prefix
        return prefix / "venv" / "bin" / "overseerd"

    monkeypatch.setattr(mod, "runtime_prefix", lambda: tmp_path / "runtime")
    monkeypatch.setattr(mod, "ensure_runtime", fake_ensure)

    assert mod.ensure_current_runtime() == tmp_path / "runtime" / "venv" / "bin" / "overseerd"
    assert seen == {"prefix": tmp_path / "runtime"}
