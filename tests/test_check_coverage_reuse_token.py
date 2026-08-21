"""Regression coverage for check-coverage's consume-once data reuse."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

__all__: list[str] = []


ROOT = Path(__file__).resolve().parent.parent
CHECK_COVERAGE = ROOT / "scripts" / "check-coverage.sh"
CHECK_PER_FILE_COVERAGE = ROOT / "scripts" / "check-per-file-coverage.sh"
REUSE_STAMP = ".coverage.livespec-reuse-token"
OLD_REUSE_STAMP = ".livespec-" "coverage-reuse-token"


def _clean_env(*, tmp_path: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {
        "HOME": str(tmp_path),
        "PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}",
        "UV_LOG": str(tmp_path / "uv.log"),
    }
    for key, value in os.environ.items():
        if key.startswith("COV_CORE_") or key == "COVERAGE_PROCESS_START":
            continue
        if key not in env:
            env[key] = value
    if extra:
        env.update(extra)
    return env


def _install_harness(*, tmp_path: Path) -> Path:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(CHECK_COVERAGE, scripts / "check-coverage.sh")
    shutil.copy2(CHECK_PER_FILE_COVERAGE, scripts / "check-per-file-coverage.sh")
    (scripts / "test-nprocs.sh").write_text(
        "#!/usr/bin/env bash\nprintf '1\\n'\n", encoding="utf-8"
    )
    (scripts / "test-nprocs.sh").chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$UV_LOG"
if [[ "$1 $2" == "run coverage" ]]; then
    total="$(cat .coverage)"
    printf 'TOTAL %s 0 100%%\\n' "$total"
    exit "${FAKE_REPORT_STATUS:-0}"
fi
if [[ "$1 $2" == "run pytest" ]]; then
    total="${FAKE_PYTEST_TOTAL:-1000}"
    printf '%s\\n' "$total" > .coverage
    printf 'TOTAL %s ${FAKE_PYTEST_MISSED:-0} ${FAKE_PYTEST_PERCENT:-100}%%\\n' "$total"
    exit "${FAKE_PYTEST_STATUS:-0}"
fi
if [[ "$1 $2" == "run python" ]]; then
    exit "${FAKE_PER_FILE_STATUS:-0}"
fi
exit 99
""",
        encoding="utf-8",
    )
    uv.chmod(0o755)
    return scripts


def _run_script(
    *, tmp_path: Path, script: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = _clean_env(tmp_path=tmp_path, extra=extra_env)
    return subprocess.run(  # noqa: S603
        ["bash", f"scripts/{script}"],  # noqa: S607
        cwd=tmp_path,
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )


def _uv_log(*, tmp_path: Path) -> list[str]:
    log = tmp_path / "uv.log"
    if not log.exists():
        return []
    return log.read_text(encoding="utf-8").splitlines()


def _reported_total(*, output: str) -> str:
    match = re.search(r"^TOTAL\s+(\d+)\s", output, flags=re.MULTILINE)
    assert match is not None, output
    return match.group(1)


def test_stale_green_coverage_file_cannot_vacuously_pass(*, tmp_path: Path) -> None:
    _install_harness(tmp_path=tmp_path)
    (tmp_path / ".coverage").write_text("9999\n", encoding="utf-8")

    result = _run_script(
        tmp_path=tmp_path,
        script="check-coverage.sh",
        extra_env={"FAKE_PYTEST_STATUS": "2", "FAKE_PYTEST_TOTAL": "1111"},
    )

    assert result.returncode == 2
    assert _uv_log(tmp_path=tmp_path) == [
        "run pytest -n 1 --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing"
    ]


def test_stale_partial_coverage_file_does_not_false_fail(*, tmp_path: Path) -> None:
    _install_harness(tmp_path=tmp_path)
    (tmp_path / ".coverage").write_text("9425\n", encoding="utf-8")

    result = _run_script(
        tmp_path=tmp_path,
        script="check-coverage.sh",
        extra_env={
            "FAKE_REPORT_STATUS": "2",
            "FAKE_PYTEST_STATUS": "0",
            "FAKE_PYTEST_TOTAL": "9380",
        },
    )

    assert result.returncode == 0
    assert _uv_log(tmp_path=tmp_path) == [
        "run pytest -n 1 --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing"
    ]


def test_current_aggregate_token_reuses_produced_coverage_once(*, tmp_path: Path) -> None:
    _install_harness(tmp_path=tmp_path)
    token = "aggregate-token"
    producer = _run_script(
        tmp_path=tmp_path,
        script="check-per-file-coverage.sh",
        extra_env={"LIVESPEC_COVERAGE_REUSE_TOKEN": token, "FAKE_PYTEST_TOTAL": "8675309"},
    )

    consumer = _run_script(
        tmp_path=tmp_path,
        script="check-coverage.sh",
        extra_env={"LIVESPEC_COVERAGE_REUSE_TOKEN": token},
    )

    assert producer.returncode == 0, producer.stderr
    assert consumer.returncode == 0, consumer.stderr
    assert _reported_total(output=consumer.stdout) == _reported_total(output=producer.stdout)
    assert _uv_log(tmp_path=tmp_path) == [
        "run pytest -n 1 --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing",
        "run python -m livespec_dev_tooling.checks.per_file_coverage",
        "run coverage report --fail-under=100",
    ]
    assert not (tmp_path / ".coverage").exists()
    assert not (tmp_path / REUSE_STAMP).exists()


def test_reuse_stamp_literal_is_shared_by_producer_consumer_and_contract() -> None:
    files = [
        CHECK_COVERAGE,
        CHECK_PER_FILE_COVERAGE,
        Path(__file__),
    ]

    for path in files:
        text = path.read_text(encoding="utf-8")
        assert REUSE_STAMP in text
        assert OLD_REUSE_STAMP not in text


def test_check_coverage_messages_do_not_assert_unproven_provenance() -> None:
    script = CHECK_COVERAGE.read_text(encoding="utf-8")

    assert "produced by check-per-file-coverage" not in script
    assert "CI standalone job" not in script
