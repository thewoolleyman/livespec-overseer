"""Controls for the pre-push green-token clean-tree short-circuit (overseer-h200).

Every other fleet member's pre-push probes the green token first and skips the
full `just check` aggregate when the working tree is byte-identical to the last
successful green run. These tests pin that behavior for this repo:

- a token MATCH (green_token check exits 0) skips the aggregate — `just check`
  is never invoked and the push completes in seconds;
- a token MISS (green_token check exits 1) still runs the full aggregate.

The plan-anchor metadata check runs in BOTH cases: it is cheap and
ledger-dependent, so it sits deliberately outside the skip.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "check-pre-push.sh"


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
    green_token_matches: bool,
) -> tuple[subprocess.CompletedProcess[str], Path]:
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
if [[ "$*" == "run python -m livespec_dev_tooling.green_token check" ]]; then
  exit {"0" if green_token_matches else "1"}
fi
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
# Faithful to the real credential wrapper, whose stage-1 hop is an `exec env -i`
# with a short allowlist: the inherited environment is DISCARDED, so a caller
# that assigns variables as a PREFIX on the wrapper cannot pass them through.
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
    return completed, just_log


def _just_invocations(*, just_log: Path) -> list[str]:
    if not just_log.exists():
        return []
    return [line for line in just_log.read_text(encoding="utf-8").splitlines() if line]


def test_matching_green_token_skips_the_full_aggregate(tmp_path: Path) -> None:
    completed, just_log = _run_pre_push(tmp_path=tmp_path, green_token_matches=True)

    assert completed.returncode == 0
    assert "green token matched" in completed.stdout
    invocations = _just_invocations(just_log=just_log)
    # The plan-anchor check still runs; the full aggregate does NOT.
    assert "check-plan-anchor-metadata" in invocations
    assert "check" not in invocations


def test_missing_green_token_runs_the_full_aggregate(tmp_path: Path) -> None:
    completed, just_log = _run_pre_push(tmp_path=tmp_path, green_token_matches=False)

    assert completed.returncode == 0
    assert "green token matched" not in completed.stdout
    invocations = _just_invocations(just_log=just_log)
    # A tree change (token miss) still runs the plan-anchor check AND the aggregate.
    assert "check-plan-anchor-metadata" in invocations
    assert "check" in invocations
