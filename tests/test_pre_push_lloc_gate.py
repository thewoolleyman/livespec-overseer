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
# The PATH the real credential wrapper leaves behind after its `env -i` hop.
_SCRUBBED_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


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
    bin_dir.mkdir(parents=True)
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
if [[ "$*" == "check-plan-anchor-metadata" ]]; then
  exit 0
fi
if [[ "$*" == "check-pre-commit-doc-only" ]]; then
  exit 0
fi
if [[ "$*" != "check" ]]; then
  echo "unexpected just invocation: $*" >&2
  exit 99
fi
if [[ "${{{_FAIL_ENV_VAR}:-}}" == "true" && "${{SOFT_OWNER_MARKED}}" != "true" ]]; then
  echo '{{"file":"overseer/foreman_act_dispatch.py","lloc":211,'\
' "failing":true,'\
'"expected_marker":"# livespec-lloc-soft-band-owner: <work-item-id>"}}' >&2
  exit 1
fi
exit 0
""",
    )

    # ⛔ WITHOUT THIS STUB this test reaches for the OPERATOR HOST's real
    # `with-livespec-env.sh`, because the gate resolves the wrapper by
    # `command -v`. That made the test non-hermetic in the direction that hides
    # a defect rather than inventing one: CI has no wrapper, so the gate takes
    # its "remains unarmed" branch and the test is green there, while every
    # operator host runs the real wrapper — whose `env -i` hop drops PATH — and
    # sees `env: 'just': No such file or directory`, exit 127, before any LLOC
    # assertion is reached. The double below reproduces the scrub, so the test
    # now measures the same thing in both places.
    _write_executable(
        path=bin_dir / "with-livespec-env.sh",
        body=f"""#!/usr/bin/env bash
set -euo pipefail
if [[ "${{1:-}}" == "--" ]]; then
  shift
fi
PATH="{_SCRUBBED_PATH}" exec "$@"
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


def _run_instructed_check(
    *,
    tmp_path: Path,
    soft_owner_marked: bool,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    log_path = tmp_path / "just-check.log"
    just = shutil.which("just")
    assert just is not None
    _write_executable(
        path=bin_dir / "uv",
        body="""#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == "sync --all-groups" ]]; then
  exit 0
fi
if [[ "$*" == "run python -m livespec_dev_tooling.green_token write" ]]; then
  exit 0
fi
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
if [[ "$*" == "check-no-lloc-soft-warnings" ]]; then
  if [[ "${{{_FAIL_ENV_VAR}:-}}" == "true" && "${{SOFT_OWNER_MARKED}}" != "true" ]]; then
    echo '{{"file":"overseer/foreman_act_dispatch.py","lloc":211,'\
' "failing":true,'\
'"expected_marker":"# livespec-lloc-soft-band-owner: <work-item-id>"}}' >&2
    exit 1
  fi
  exit 0
fi
exit 0
""",
    )

    env = _scrub_coverage_env(env=os.environ.copy())
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "SOFT_OWNER_MARKED": "true" if soft_owner_marked else "false",
        }
    )
    env.pop(_FAIL_ENV_VAR, None)
    return subprocess.run(  # noqa: S603
        [just, "check"],
        cwd=_REPO_ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )


def test_instructed_check_and_pre_push_refuse_unmarked_soft_band_python_change(
    tmp_path: Path,
) -> None:
    instructed = _run_instructed_check(
        tmp_path=tmp_path / "instructed",
        soft_owner_marked=False,
    )
    pre_push = _run_pre_push(
        tmp_path=tmp_path / "pre-push",
        changed_files="overseer/foreman_act_dispatch.py",
        soft_owner_marked=False,
    )

    assert instructed.returncode == 1
    assert pre_push.returncode == 1
    assert "check-no-lloc-soft-warnings" in instructed.stdout
    assert '"failing":true' in instructed.stderr
    assert '"failing":true' in pre_push.stderr


def test_instructed_check_and_pre_push_accept_marked_soft_band_python_change(
    tmp_path: Path,
) -> None:
    instructed = _run_instructed_check(
        tmp_path=tmp_path / "instructed",
        soft_owner_marked=True,
    )
    pre_push = _run_pre_push(
        tmp_path=tmp_path / "pre-push",
        changed_files="overseer/foreman_act_dispatch.py",
        soft_owner_marked=True,
    )

    assert instructed.returncode == 0
    assert pre_push.returncode == 0


def test_pre_push_refuses_unmarked_soft_band_python_change(tmp_path: Path) -> None:
    completed = _run_pre_push(
        tmp_path=tmp_path,
        changed_files="overseer/foreman_act_dispatch.py",
        soft_owner_marked=False,
    )

    assert completed.returncode == 1
    assert ":: pre-push: failing diagnostics reported by the gate:" in completed.stderr
    assert "overseer/foreman_act_dispatch.py" in completed.stderr
    assert '"lloc":211' in completed.stderr
    assert '"failing":true' in completed.stderr
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
