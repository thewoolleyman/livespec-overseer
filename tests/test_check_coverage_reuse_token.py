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
REUSE_ID = ROOT / "scripts" / "coverage-reuse-id.sh"
REUSE_STAMP = ".livespec-coverage-reuse-token"
OLD_REUSE_STAMP = ".coverage." "livespec-reuse-token"


# Every environment variable scripts/coverage-reuse-id.sh reads. These are
# STRIPPED from the inherited environment so each test states the resolver's
# inputs itself. Without this the suite's verdict depends on where it runs: a
# developer host sets none of them and the resolver falls through to its
# tree-digest branch, while a GitHub runner exports GITHUB_RUN_ID and
# GITHUB_RUN_ATTEMPT into every process, so the resolver's FIRST branch wins and
# silently overrides whatever a test passed in. That is the ambient-state leak
# this repo's whole test-and-gate-integrity thread exists to remove — a test
# whose result is decided by its host is not a control.
_RESOLVER_INPUTS = ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "LIVESPEC_COVERAGE_REUSE_TOKEN")


def _clean_env(*, tmp_path: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {
        "HOME": str(tmp_path),
        "PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}",
        "UV_LOG": str(tmp_path / "uv.log"),
    }
    for key, value in os.environ.items():
        if key.startswith("COV_CORE_") or key == "COVERAGE_PROCESS_START":
            continue
        if key in _RESOLVER_INPUTS:
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
    shutil.copy2(REUSE_ID, scripts / "coverage-reuse-id.sh")
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


def _git(*, cwd: Path, args: list[str]) -> None:
    subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        env=_clean_env(tmp_path=cwd),
        text=True,
    )


def _init_git_repo(*, tmp_path: Path) -> None:
    _git(cwd=tmp_path, args=["init", "-q", "-b", "master"])
    _git(cwd=tmp_path, args=["config", "user.name", "Test User"])
    _git(cwd=tmp_path, args=["config", "user.email", "test@example.com"])
    (tmp_path / "tracked.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(cwd=tmp_path, args=["add", "tracked.py"])
    _git(cwd=tmp_path, args=["commit", "-q", "-m", "base"])


def _reuse_id(*, tmp_path: Path, extra_env: dict[str, str] | None = None) -> str:
    env = _clean_env(tmp_path=tmp_path, extra=extra_env)
    result = subprocess.run(  # noqa: S603
        ["bash", "scripts/coverage-reuse-id.sh"],  # noqa: S607
        cwd=tmp_path,
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


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
    _init_git_repo(tmp_path=tmp_path)
    producer = _run_script(
        tmp_path=tmp_path,
        script="check-per-file-coverage.sh",
        extra_env={"FAKE_PYTEST_TOTAL": "8675309"},
    )

    consumer = _run_script(
        tmp_path=tmp_path,
        script="check-coverage.sh",
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


def test_github_run_attempt_reuse_id_matches_within_run_and_changes_across_runs(
    *, tmp_path: Path
) -> None:
    _install_harness(tmp_path=tmp_path)

    first = _reuse_id(
        tmp_path=tmp_path,
        extra_env={"GITHUB_RUN_ID": "32452743372", "GITHUB_RUN_ATTEMPT": "1"},
    )
    same = _reuse_id(
        tmp_path=tmp_path,
        extra_env={"GITHUB_RUN_ID": "32452743372", "GITHUB_RUN_ATTEMPT": "1"},
    )
    new_run = _reuse_id(
        tmp_path=tmp_path,
        extra_env={"GITHUB_RUN_ID": "32452743373", "GITHUB_RUN_ATTEMPT": "1"},
    )
    new_attempt = _reuse_id(
        tmp_path=tmp_path,
        extra_env={"GITHUB_RUN_ID": "32452743372", "GITHUB_RUN_ATTEMPT": "2"},
    )

    assert first == same
    assert first == "github-run:32452743372:attempt:1"
    assert first != new_run
    assert first != new_attempt


def test_missing_marker_falls_back_nonfatally_and_does_not_report_stale_data(
    *, tmp_path: Path
) -> None:
    _install_harness(tmp_path=tmp_path)
    _init_git_repo(tmp_path=tmp_path)
    (tmp_path / ".coverage").write_text("9999\n", encoding="utf-8")

    result = _run_script(
        tmp_path=tmp_path,
        script="check-coverage.sh",
        extra_env={"FAKE_PYTEST_TOTAL": "2222"},
    )

    assert result.returncode == 0, result.stderr
    assert _reported_total(output=result.stdout) == "2222"
    assert _uv_log(tmp_path=tmp_path) == [
        "run pytest -n 1 --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing"
    ]


def test_mismatched_marker_falls_back_nonfatally_and_does_not_report_stale_data(
    *, tmp_path: Path
) -> None:
    _install_harness(tmp_path=tmp_path)
    _init_git_repo(tmp_path=tmp_path)
    (tmp_path / ".coverage").write_text("9999\n", encoding="utf-8")
    (tmp_path / REUSE_STAMP).write_text("github-run:other:attempt:1\n", encoding="utf-8")

    result = _run_script(
        tmp_path=tmp_path,
        script="check-coverage.sh",
        extra_env={
            "GITHUB_RUN_ID": "32452743372",
            "GITHUB_RUN_ATTEMPT": "1",
            "FAKE_PYTEST_TOTAL": "3333",
        },
    )

    assert result.returncode == 0, result.stderr
    assert _reported_total(output=result.stdout) == "3333"
    assert _uv_log(tmp_path=tmp_path) == [
        "run pytest -n 1 --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing"
    ]


def test_missing_reuse_id_falls_back_nonfatally_and_does_not_report_stale_data(
    *, tmp_path: Path
) -> None:
    _install_harness(tmp_path=tmp_path)
    (tmp_path / ".coverage").write_text("9999\n", encoding="utf-8")
    (tmp_path / REUSE_STAMP).write_text("github-run:32452743372:attempt:1\n", encoding="utf-8")

    result = _run_script(
        tmp_path=tmp_path,
        script="check-coverage.sh",
        extra_env={"GITHUB_RUN_ID": "32452743372", "FAKE_PYTEST_TOTAL": "4444"},
    )

    assert result.returncode == 0, result.stderr
    assert _reported_total(output=result.stdout) == "4444"
    assert _uv_log(tmp_path=tmp_path) == [
        "run pytest -n 1 --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing"
    ]


def test_local_reuse_id_changes_when_tracked_tree_changes(*, tmp_path: Path) -> None:
    _install_harness(tmp_path=tmp_path)
    _init_git_repo(tmp_path=tmp_path)
    before = _reuse_id(tmp_path=tmp_path)

    (tmp_path / "tracked.py").write_text("VALUE = 2\n", encoding="utf-8")
    after = _reuse_id(tmp_path=tmp_path)

    assert before.startswith("git-tree:")
    assert before != after


def test_reuse_stamp_literal_is_shared_by_producer_consumer_and_contract() -> None:
    files = [
        CHECK_COVERAGE,
        CHECK_PER_FILE_COVERAGE,
        REUSE_ID,
        Path(__file__),
    ]

    for path in files:
        text = path.read_text(encoding="utf-8")
        assert REUSE_STAMP in text
        assert OLD_REUSE_STAMP not in text


def test_reuse_stamp_name_is_outside_coverage_parallel_data_namespace() -> None:
    assert not REUSE_STAMP.startswith(".coverage")


def test_check_coverage_messages_do_not_assert_unproven_provenance() -> None:
    script = CHECK_COVERAGE.read_text(encoding="utf-8")

    assert "produced by check-per-file-coverage" not in script
    assert "CI standalone job" not in script


def test_explicit_token_round_trip_mismatch_falls_back_and_clears_the_marker(
    *, tmp_path: Path
) -> None:
    """A marker the PRODUCER wrote must not unlock reuse under a different token.

    Carried from overseer-hgq4wi.26, which landed this control against the
    aggregate-local token before overseer-bnutz7 replaced that token with the
    shared resolver. The sibling mismatch tests above hand-write the marker;
    this one drives the real producer-then-consumer round trip through the
    resolver's explicit-token branch, and additionally pins that the refused
    marker is DELETED rather than left on disk to confuse a later run.
    """
    _install_harness(tmp_path=tmp_path)
    producer = _run_script(
        tmp_path=tmp_path,
        script="check-per-file-coverage.sh",
        extra_env={"LIVESPEC_COVERAGE_REUSE_TOKEN": "ci-111-1", "FAKE_PYTEST_TOTAL": "4242"},
    )
    assert producer.returncode == 0, producer.stderr
    assert (tmp_path / REUSE_STAMP).read_text(encoding="utf-8").strip() == "explicit:ci-111-1"

    consumer = _run_script(
        tmp_path=tmp_path,
        script="check-coverage.sh",
        extra_env={"LIVESPEC_COVERAGE_REUSE_TOKEN": "ci-222-1", "FAKE_PYTEST_TOTAL": "7"},
    )

    assert consumer.returncode == 0, consumer.stderr
    assert "ignoring existing .coverage without matching provenance marker" in consumer.stdout
    assert "reading current .coverage from matching provenance marker" not in consumer.stdout
    assert _uv_log(tmp_path=tmp_path)[-1] == (
        "run pytest -n 1 --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing"
    )
    assert not (tmp_path / REUSE_STAMP).exists()


def test_clean_env_strips_the_resolver_inputs_the_host_may_already_set(
    *, tmp_path: Path, monkeypatch
) -> None:
    """The harness must own every input the resolver reads, whatever the host sets.

    This is the control for the CI-only failure that reddened PR 1412: on a
    GitHub runner GITHUB_RUN_ID and GITHUB_RUN_ATTEMPT are exported into every
    process, so the resolver's first branch won and the tests below measured the
    runner's identity instead of the value they passed. Locally none of these
    are set, so the suite passed and the leak was invisible. Assert the strip
    directly rather than inferring it from those tests, since they only fail on
    a host that happens to set the variables.
    """
    for name in _RESOLVER_INPUTS:
        monkeypatch.setenv(name, "leaked-from-the-host")

    env = _clean_env(tmp_path=tmp_path)

    for name in _RESOLVER_INPUTS:
        assert name not in env, name

    # ...and an explicit value still reaches the script, so stripping did not
    # simply make these variables unusable.
    override = _clean_env(tmp_path=tmp_path, extra={"GITHUB_RUN_ID": "chosen"})
    assert override["GITHUB_RUN_ID"] == "chosen"
