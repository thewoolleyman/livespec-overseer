"""Controls for the delegated pre-push gate opt-in (overseer-cakxxq).

This repository opts in to livespec-dev-tooling's delegated pre-push gate. A push
from a host that can read the gates kubeconfig runs the delegation client in place
of `just check`; any other host (a Fabro sandbox) runs the gate locally. These
tests pin the three load-bearing properties:

- the version-controlled opt-in (`delegated_gate = true`) is declared;
- when `enabled` answers yes the recipe `exec`s the client, and the client's
  result is the push's result with no branch to a local `just check`;
- when `enabled` answers no the local aggregate still runs.

The plan-anchor metadata check sits OUTSIDE the swap: it runs on the pushing host
in both cases. It is not a declared authority-reading member of the delegated
gate (`check_authority members` names only `check-branch-protection-alignment`
and `check-no-workflow-edits`), so its silent skip when the credential wrapper is
absent is not an "unable to evaluate" refusal.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

from livespec_dev_tooling.config import load_delegated_gate

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "check-pre-push.sh"
_CLIENT = "livespec_dev_tooling.gate_remote_delegate"


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
    enabled_exit: int,
    run_exit: int,
) -> tuple[subprocess.CompletedProcess[str], list[str], list[str]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    just_log = tmp_path / "just.log"
    uv_log = tmp_path / "uv.log"
    bash = shutil.which("bash")
    assert bash is not None

    _write_executable(
        path=bin_dir / "uv",
        body=f"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "{uv_log}"
case "$*" in
  "run python -m livespec_dev_tooling.green_token check") exit 1 ;;
  "run python -m {_CLIENT} enabled") exit {enabled_exit} ;;
  "run python -m {_CLIENT} run") exit {run_exit} ;;
esac
echo "unexpected uv invocation: $*" >&2
exit 99
""",
    )
    _write_executable(
        path=bin_dir / "just",
        body=f"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "{just_log}"
if [[ "$*" == "check-plan-anchor-metadata" || "$*" == "check" ]]; then
  exit 0
fi
echo "unexpected just invocation: $*" >&2
exit 99
""",
    )
    _write_executable(
        path=bin_dir / "with-livespec-env.sh",
        body="""#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--" ]]; then
  shift
fi
exec env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin "$@"
""",
    )

    env = _scrub_coverage_env(env=os.environ.copy())
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    completed = subprocess.run(  # noqa: S603
        [bash, str(_SCRIPT)],
        cwd=_REPO_ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    return completed, _lines(path=just_log), _lines(path=uv_log)


def _lines(*, path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_repository_declares_the_delegated_gate_opt_in() -> None:
    assert load_delegated_gate(repo_root=_REPO_ROOT) is True


def test_delegating_push_runs_the_client_and_never_the_local_aggregate(
    tmp_path: Path,
) -> None:
    completed, just_calls, uv_calls = _run_pre_push(tmp_path=tmp_path, enabled_exit=0, run_exit=0)

    assert completed.returncode == 0
    assert f"run python -m {_CLIENT} run" in uv_calls
    assert "check" not in just_calls
    assert "check-plan-anchor-metadata" in just_calls


def test_delegated_refusal_is_the_push_result_with_no_local_fallthrough(
    tmp_path: Path,
) -> None:
    completed, just_calls, uv_calls = _run_pre_push(tmp_path=tmp_path, enabled_exit=0, run_exit=1)

    assert completed.returncode == 1
    assert f"run python -m {_CLIENT} run" in uv_calls
    assert "check" not in just_calls


def test_non_delegating_host_gates_locally_without_calling_the_client(
    tmp_path: Path,
) -> None:
    completed, just_calls, uv_calls = _run_pre_push(tmp_path=tmp_path, enabled_exit=1, run_exit=1)

    assert completed.returncode == 0
    assert f"run python -m {_CLIENT} enabled" in uv_calls
    assert f"run python -m {_CLIENT} run" not in uv_calls
    assert "check" in just_calls
