"""Controls for the repo-local pre-commit shape wrapper."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

from overseer.pre_commit_gate import union_skip_targets

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "check-pre-commit.sh"


def _write_executable(*, path: Path, body: str) -> None:
    _ = path.write_text(body, encoding="utf-8")
    _ = path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _scrub_coverage_env(*, env: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in env.items()
        if key != "COVERAGE_PROCESS_START" and not key.startswith("COV_CORE_")
    }


def _run_pre_commit(
    *,
    tmp_path: Path,
    staged_files: str,
    impl_staged: str,
    existing_skip: str = "",
    refuse_uv: bool = False,
    just_exit: int = 0,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "just.log"
    bash = shutil.which("bash")
    assert bash is not None
    _write_executable(
        path=bin_dir / "git",
        body="""#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == "diff --cached --name-only --diff-filter=AM" ]]; then
  printf '%s\n' "$PRE_COMMIT_STAGED_FILES"
  exit 0
fi
if [[ "$*" == "log -1 --format=%B" ]]; then
  printf '%s\n' "$PRE_COMMIT_HEAD_MESSAGE"
  exit 0
fi
echo "unexpected git invocation: $*" >&2
exit 99
""",
    )
    _write_executable(
        path=bin_dir / "uv",
        body="""#!/usr/bin/env bash
set -euo pipefail
if [[ "${PRE_COMMIT_REFUSE_UV:-}" == "true" ]]; then
  echo "uv should not have been called" >&2
  exit 98
fi
if [[ "$*" == "run python -" ]]; then
  cat >/dev/null
  if [[ -n "${LIVESPEC_REQUIRED_SKIP:-}" ]]; then
    declare -A seen=()
    joined=""
    for target in ${LIVESPEC_EXISTING_SKIP:-} ${LIVESPEC_REQUIRED_SKIP}; do
      if [[ -z "$target" || -n "${seen[$target]+x}" ]]; then
        continue
      fi
      seen[$target]=1
      if [[ -z "$joined" ]]; then
        joined="$target"
      else
        joined+=" $target"
      fi
    done
    printf '%s\n' "$joined"
  else
    printf '%s\n' "$PRE_COMMIT_IMPL_STAGED"
  fi
  exit 0
fi
echo "unexpected uv invocation: $*" >&2
exit 99
""",
    )
    _write_executable(
        path=bin_dir / "just",
        body=f"""#!/usr/bin/env bash
set -euo pipefail
printf '%s env=%s\\n' "$*" "${{LIVESPEC_CHECK_SKIP:-<unset>}}" >> "{log_path}"
exit "${{PRE_COMMIT_JUST_EXIT}}"
""",
    )

    env = _scrub_coverage_env(env=os.environ.copy())
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "PRE_COMMIT_STAGED_FILES": staged_files,
            "PRE_COMMIT_IMPL_STAGED": impl_staged,
            "PRE_COMMIT_HEAD_MESSAGE": "",
            "PRE_COMMIT_REFUSE_UV": "true" if refuse_uv else "false",
            "PRE_COMMIT_JUST_EXIT": str(just_exit),
        }
    )
    if existing_skip:
        env["LIVESPEC_CHECK_SKIP"] = existing_skip
    else:
        _ = env.pop("LIVESPEC_CHECK_SKIP", None)
    return subprocess.run(  # noqa: S603
        [bash, str(_SCRIPT)],
        cwd=_REPO_ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )


def _just_log(*, tmp_path: Path) -> str:
    return (tmp_path / "just.log").read_text(encoding="utf-8")


def test_union_skip_targets_preserves_external_order_and_deduplicates() -> None:
    assert (
        union_skip_targets(
            existing="check-claude-idle-canary check-coverage",
            required=("check-coverage", "check-per-file-coverage"),
        )
        == "check-claude-idle-canary check-coverage check-per-file-coverage"
    )


def test_red_mode_unions_external_skip_with_builtin_coverage_skips(tmp_path: Path) -> None:
    completed = _run_pre_commit(
        tmp_path=tmp_path,
        staged_files="tests/test_gate.py",
        impl_staged="",
        existing_skip="check-claude-idle-canary check-coverage",
    )

    assert completed.returncode == 0, completed.stderr
    assert ":: Red-mode shape detected: tests/test_gate.py" in completed.stdout
    assert _just_log(tmp_path=tmp_path) == (
        "check env=check-claude-idle-canary check-coverage check-per-file-coverage\n"
    )


def test_doc_only_fast_path_does_not_load_python_classifier(tmp_path: Path) -> None:
    completed = _run_pre_commit(
        tmp_path=tmp_path,
        staged_files="AGENTS.md",
        impl_staged="unexpected-uv-call",
        refuse_uv=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "doc-only mode detected" in completed.stdout
    assert _just_log(tmp_path=tmp_path) == "check-pre-commit-doc-only env=<unset>\n"


def test_impl_plus_tests_enters_full_check_shape(tmp_path: Path) -> None:
    completed = _run_pre_commit(
        tmp_path=tmp_path,
        staged_files="overseer/signals.py\ntests/test_signals.py",
        impl_staged="overseer/signals.py",
    )

    assert completed.returncode == 0, completed.stderr
    assert "Red-mode shape detected" not in completed.stdout
    assert _just_log(tmp_path=tmp_path) == "check env=<unset>\n"


def test_impl_plus_tests_propagates_full_check_failure(tmp_path: Path) -> None:
    completed = _run_pre_commit(
        tmp_path=tmp_path,
        staged_files="overseer/signals.py\ntests/test_signals.py",
        impl_staged="overseer/signals.py",
        just_exit=7,
    )

    assert completed.returncode == 7
    assert "Red-mode shape detected" not in completed.stdout
    assert _just_log(tmp_path=tmp_path) == "check env=<unset>\n"
