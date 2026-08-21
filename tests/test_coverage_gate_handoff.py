"""Regression coverage for the check-per-file/check-coverage handoff."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CHECK_COVERAGE = _REPO_ROOT / "scripts" / "check-coverage.sh"
_CHECK_PER_FILE_COVERAGE = _REPO_ROOT / "scripts" / "check-per-file-coverage.sh"
_HANDOFF = ".coverage.livespec-check-run"


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _write_stub_tools(*, tmp_path: Path, uv_body: str) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "uv", uv_body)
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    _write_executable(scripts_dir / "test-nprocs.sh", "#!/bin/sh\nprintf '2\\n'\n")
    return bin_dir


def _run_script(
    script: Path,
    *,
    cwd: Path,
    bin_dir: Path,
    run_id: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    if run_id is None:
        env.pop("LIVESPEC_CHECK_RUN_ID", None)
    else:
        env["LIVESPEC_CHECK_RUN_ID"] = run_id
    return subprocess.run(  # noqa: S603
        [str(script)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_check_coverage_rejects_a_root_coverage_file_without_a_run_handoff(
    *, tmp_path: Path
) -> None:
    bin_dir = _write_stub_tools(
        tmp_path=tmp_path,
        uv_body="#!/bin/sh\necho uv-called >> uv.log\nexit 0\n",
    )
    (tmp_path / ".coverage").write_text("stale-green-data", encoding="utf-8")

    result = _run_script(_CHECK_COVERAGE, cwd=tmp_path, bin_dir=bin_dir)

    assert result.returncode != 0
    assert "stale .coverage" in result.stderr
    assert not (tmp_path / "uv.log").exists()
    assert (tmp_path / ".coverage").read_text(encoding="utf-8") == "stale-green-data"


def test_check_coverage_rejects_a_root_coverage_file_from_another_check_run(
    *, tmp_path: Path
) -> None:
    bin_dir = _write_stub_tools(
        tmp_path=tmp_path,
        uv_body="#!/bin/sh\necho uv-called >> uv.log\nexit 0\n",
    )
    (tmp_path / ".coverage").write_text("other-run-data", encoding="utf-8")
    (tmp_path / _HANDOFF).write_text("other-run\n", encoding="utf-8")

    result = _run_script(
        _CHECK_COVERAGE,
        cwd=tmp_path,
        bin_dir=bin_dir,
        run_id="this-run",
    )

    assert result.returncode != 0
    assert "stale .coverage" in result.stderr
    assert "other-run" in result.stderr
    assert "this-run" in result.stderr
    assert not (tmp_path / "uv.log").exists()


def test_per_file_coverage_writes_the_current_check_run_handoff(*, tmp_path: Path) -> None:
    bin_dir = _write_stub_tools(
        tmp_path=tmp_path,
        uv_body=(
            "#!/bin/sh\n"
            'echo "$*" >> uv.log\n'
            'case "$*" in *pytest*) printf data > .coverage ;; esac\n'
            "exit 0\n"
        ),
    )

    result = _run_script(
        _CHECK_PER_FILE_COVERAGE,
        cwd=tmp_path,
        bin_dir=bin_dir,
        run_id="aggregate-123",
    )

    assert result.returncode == 0
    assert (tmp_path / _HANDOFF).read_text(encoding="utf-8") == "aggregate-123\n"


def test_check_coverage_consumes_only_the_matching_check_run_handoff(*, tmp_path: Path) -> None:
    bin_dir = _write_stub_tools(
        tmp_path=tmp_path,
        uv_body='#!/bin/sh\necho "$*" >> uv.log\nexit 0\n',
    )
    (tmp_path / ".coverage").write_text("fresh-data", encoding="utf-8")
    (tmp_path / _HANDOFF).write_text("aggregate-123\n", encoding="utf-8")

    result = _run_script(
        _CHECK_COVERAGE,
        cwd=tmp_path,
        bin_dir=bin_dir,
        run_id="aggregate-123",
    )

    assert result.returncode == 0
    assert "coverage report --fail-under=100" in (tmp_path / "uv.log").read_text(encoding="utf-8")
    assert not (tmp_path / ".coverage").exists()
    assert not (tmp_path / _HANDOFF).exists()
