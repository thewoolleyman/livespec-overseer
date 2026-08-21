"""Controls for the pre-push LLOC soft-band severity wiring."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "check-pre-push.sh"
_FAIL_ENV_VAR = "LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST"


def _write_executable(*, path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _scrub_coverage_env(*, env: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in env.items()
        if key != "COVERAGE_PROCESS_START" and not key.startswith("COV_CORE_")
    }


def _run_pre_push(
    *,
    tmp_path: Path,
    changed_files: str,
    soft_owner_marked: bool,
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
if [[ "$*" == "diff --name-only origin/master...HEAD" ]]; then
  printf '%s\n' "$PRE_PUSH_CHANGED_FILES"
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
if [[ "$*" == "run python -m livespec_dev_tooling.green_token check" ]]; then
  exit 1
fi
echo "unexpected uv invocation: $*" >&2
exit 99
""",
    )
    _write_executable(
        path=bin_dir / "just",
        body=f"""#!/usr/bin/env bash
set -euo pipefail
printf '%s env=%s\\n' "$*" "${{{_FAIL_ENV_VAR}:-<unset>}}" >> "{log_path}"
if [[ "$*" == "check-pre-commit-doc-only" ]]; then
  exit 0
fi
if [[ "$*" != "check" ]]; then
  echo "unexpected just invocation: $*" >&2
  exit 99
fi
if [[ "${{{_FAIL_ENV_VAR}:-}}" == "true" && "${{SOFT_OWNER_MARKED}}" != "true" ]]; then
  echo '{{"file":"overseer/foreman_act_dispatch.py","lloc":211,'\
'"expected_marker":"# livespec-lloc-soft-band-owner: <work-item-id>"}}' >&2
  exit 1
fi
exit 0
""",
    )

    env = _scrub_coverage_env(env=os.environ.copy())
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "PRE_PUSH_CHANGED_FILES": changed_files,
            "SOFT_OWNER_MARKED": "true" if soft_owner_marked else "false",
        }
    )
    return subprocess.run(  # noqa: S603
        [bash, str(_SCRIPT)],
        cwd=_REPO_ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )


def test_pre_push_refuses_unmarked_soft_band_python_change(tmp_path: Path) -> None:
    completed = _run_pre_push(
        tmp_path=tmp_path,
        changed_files="overseer/foreman_act_dispatch.py",
        soft_owner_marked=False,
    )

    assert completed.returncode == 1
    assert "overseer/foreman_act_dispatch.py" in completed.stderr
    assert '"lloc":211' in completed.stderr
    assert "# livespec-lloc-soft-band-owner: <work-item-id>" in completed.stderr


def test_pre_push_accepts_marked_soft_band_python_change(tmp_path: Path) -> None:
    completed = _run_pre_push(
        tmp_path=tmp_path,
        changed_files="overseer/foreman_act_dispatch.py",
        soft_owner_marked=True,
    )

    assert completed.returncode == 0


def test_pre_push_doc_only_fast_path_does_not_arm_lloc_release_tier(
    tmp_path: Path,
) -> None:
    completed = _run_pre_push(
        tmp_path=tmp_path,
        changed_files="README.md",
        soft_owner_marked=False,
    )

    assert completed.returncode == 0
