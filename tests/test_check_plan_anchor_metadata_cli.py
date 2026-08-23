"""CLI wrapper behavior for the live plan-anchor metadata check."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType


def module() -> ModuleType:
    path = Path(__file__).resolve().parent.parent / "scripts" / "check-plan-anchor-metadata.py"
    spec = importlib.util.spec_from_file_location("check_plan_anchor_metadata", path)
    assert spec is not None
    loaded = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(loaded)
    return loaded


def test_missing_bd_binary_skips_live_check(
    *,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    check = module()
    monkeypatch.setattr(check.shutil, "which", lambda _: None)

    assert check.main(argv=(str(tmp_path),)) == 0

    captured = capsys.readouterr()
    assert "bd not found; skipping live check" in captured.out
    assert captured.err == ""


def test_bd_nonzero_exit_skips_instead_of_reporting_every_plan_directory(
    *,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    check = module()
    repo = tmp_path
    (repo / "plan" / "alpha").mkdir(parents=True)
    monkeypatch.setattr(check.shutil, "which", lambda _: "/usr/bin/bd")

    def fail_bd(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=("bd",), returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(check.subprocess, "run", fail_bd)

    assert check.main(argv=(str(repo),)) == 0

    captured = capsys.readouterr()
    assert "bd exited 1" in captured.err
    assert "bd read failed; skipping live check" in captured.out
    assert "plan/alpha" not in captured.err


def test_bd_invalid_json_skips_instead_of_reporting_every_plan_directory(
    *,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    check = module()
    repo = tmp_path
    (repo / "plan" / "alpha").mkdir(parents=True)
    monkeypatch.setattr(check.shutil, "which", lambda _: "/usr/bin/bd")

    def invalid_json(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=("bd",), returncode=0, stdout="{", stderr="")

    monkeypatch.setattr(check.subprocess, "run", invalid_json)

    assert check.main(argv=(str(repo),)) == 0

    captured = capsys.readouterr()
    assert "bd returned invalid json" in captured.err
    assert "bd read failed; skipping live check" in captured.out
    assert "plan/alpha" not in captured.err


def test_bd_timeout_skips_instead_of_reporting_every_plan_directory(
    *,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    check = module()
    repo = tmp_path
    (repo / "plan" / "alpha").mkdir(parents=True)
    monkeypatch.setattr(check.shutil, "which", lambda _: "/usr/bin/bd")

    def timeout(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=("bd",), timeout=30)

    monkeypatch.setattr(check.subprocess, "run", timeout)

    assert check.main(argv=(str(repo),)) == 0

    captured = capsys.readouterr()
    assert "bd timed out" in captured.err
    assert "bd read failed; skipping live check" in captured.out
    assert "plan/alpha" not in captured.err


def test_bd_non_list_json_skips_instead_of_reporting_every_plan_directory(
    *,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    check = module()
    repo = tmp_path
    (repo / "plan" / "alpha").mkdir(parents=True)
    monkeypatch.setattr(check.shutil, "which", lambda _: "/usr/bin/bd")

    def non_list_json(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=("bd",), returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(check.subprocess, "run", non_list_json)

    assert check.main(argv=(str(repo),)) == 0

    captured = capsys.readouterr()
    assert "bd returned non-list json" in captured.err
    assert "bd read failed; skipping live check" in captured.out
    assert "plan/alpha" not in captured.err


def test_successful_empty_bd_result_still_reports_missing_anchor(
    *,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    check = module()
    repo = tmp_path
    (repo / "plan" / "alpha").mkdir(parents=True)
    monkeypatch.setattr(check.shutil, "which", lambda _: "/usr/bin/bd")

    def empty_list(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=("bd",), returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr(check.subprocess, "run", empty_list)

    assert check.main(argv=(str(repo),)) == 1

    captured = capsys.readouterr()
    assert "plan/alpha" in captured.err


def test_successful_tagged_anchor_result_passes(
    *,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    check = module()
    repo = tmp_path
    (repo / "plan" / "alpha").mkdir(parents=True)
    monkeypatch.setattr(check.shutil, "which", lambda _: "/usr/bin/bd")

    def tagged_anchor(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=("bd",),
            returncode=0,
            stdout=(
                '[{"id":"overseer-alpha","issue_type":"epic","status":"ready",'
                '"metadata":{"plan_slug":"alpha"}}]'
            ),
            stderr="",
        )

    monkeypatch.setattr(check.subprocess, "run", tagged_anchor)

    assert check.main(argv=(str(repo),)) == 0

    captured = capsys.readouterr()
    assert '"status": "pass"' in captured.out
    assert '"scanned_plan_directories": 1' in captured.out
    assert captured.err == ""
