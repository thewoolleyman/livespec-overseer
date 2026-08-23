"""CLI wrapper behavior for the live plan-anchor metadata check."""

from __future__ import annotations

import importlib.util
import os
import shutil
import stat
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


def _write_executable(*, path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _scrub_coverage_env(*, env: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in env.items()
        if key != "COVERAGE_PROCESS_START" and not key.startswith("COV_CORE_")
    }


def test_pre_push_runs_plan_anchor_check_through_credential_wrapper(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "check-pre-push.sh"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    log_path = tmp_path / "pre-push.log"
    bash = shutil.which("bash")
    assert bash is not None
    _write_executable(
        path=bin_dir / "git",
        body="""#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == "diff --name-only origin/master...HEAD" ]]; then
  printf '%s\n' 'scripts/check-plan-anchor-metadata.py'
  exit 0
fi
echo "unexpected git invocation: $*" >&2
exit 99
""",
    )
    _write_executable(
        path=bin_dir / "just",
        body=f"""#!/usr/bin/env bash
set -euo pipefail
printf 'just command=%s plan_anchor_env=%s\\n' \\
  "$*" \\
  "${{LIVESPEC_STRICT_PLAN_ANCHOR_METADATA:-<unset>}}" >> "{log_path}"
if [[ "$*" == "check-plan-anchor-metadata" ]]; then
  printf '{{"check_id":"plan-anchor-metadata","scanned_plan_directories":1,"status":"pass"}}\\n'
  exit 0
fi
if [[ "$*" == "check" ]]; then
  exit 0
fi
echo "unexpected just invocation: $*" >&2
exit 99
""",
    )
    _write_executable(
        path=bin_dir / "with-livespec-env.sh",
        body=f"""#!/usr/bin/env bash
set -euo pipefail
printf 'wrapper plan_anchor_env=%s command=%s\\n' \\
  "${{LIVESPEC_STRICT_PLAN_ANCHOR_METADATA:-<unset>}}" \\
  "$*" >> "{log_path}"
if [[ "$*" != "-- just check-plan-anchor-metadata" ]]; then
  echo "unexpected wrapper invocation: $*" >&2
  exit 99
fi
exec "$@"
""",
    )
    env = _scrub_coverage_env(env=os.environ.copy())
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    completed = subprocess.run(  # noqa: S603
        [bash, str(script)],
        cwd=repo_root,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )

    log = log_path.read_text(encoding="utf-8")
    assert completed.returncode == 0
    assert "wrapper plan_anchor_env=true command=-- just check-plan-anchor-metadata" in log
    assert "just command=check-plan-anchor-metadata plan_anchor_env=true" in log
    assert '"scanned_plan_directories":1' in completed.stdout


def test_missing_bd_binary_skips_live_check_to_stderr_when_strict_unarmed(
    *,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    check = module()
    monkeypatch.setattr(check.shutil, "which", lambda _: None)
    monkeypatch.delenv("LIVESPEC_STRICT_PLAN_ANCHOR_METADATA", raising=False)

    assert check.main(argv=(str(tmp_path),)) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        "check-plan-anchor-metadata: bd not found; "
        "LIVESPEC_STRICT_PLAN_ANCHOR_METADATA unarmed; skipping live check"
    ) in captured.err


def test_missing_bd_binary_fails_when_strict_armed(
    *,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    check = module()
    monkeypatch.setattr(check.shutil, "which", lambda _: None)
    monkeypatch.setenv("LIVESPEC_STRICT_PLAN_ANCHOR_METADATA", "true")

    assert check.main(argv=(str(tmp_path),)) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        "check-plan-anchor-metadata: bd not found; "
        "LIVESPEC_STRICT_PLAN_ANCHOR_METADATA=true requires live check"
    ) in captured.err


def test_missing_bd_binary_legacy_skip_message_removed(
    *,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    check = module()
    monkeypatch.setattr(check.shutil, "which", lambda _: None)

    assert check.main(argv=(str(tmp_path),)) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "bd not found;" in captured.err
    assert "LIVESPEC_STRICT_PLAN_ANCHOR_METADATA unarmed" in captured.err


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
    monkeypatch.delenv("LIVESPEC_STRICT_PLAN_ANCHOR_METADATA", raising=False)

    def fail_bd(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=("bd",), returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(check.subprocess, "run", fail_bd)

    assert check.main(argv=(str(repo),)) == 0

    captured = capsys.readouterr()
    assert "bd exited 1" in captured.err
    assert captured.out == ""
    assert (
        "bd read failed; LIVESPEC_STRICT_PLAN_ANCHOR_METADATA unarmed; skipping live check"
        in captured.err
    )
    assert "plan/alpha" not in captured.err


def test_bd_nonzero_exit_fails_when_strict_armed(
    *,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    check = module()
    repo = tmp_path
    (repo / "plan" / "alpha").mkdir(parents=True)
    monkeypatch.setattr(check.shutil, "which", lambda _: "/usr/bin/bd")
    monkeypatch.setenv("LIVESPEC_STRICT_PLAN_ANCHOR_METADATA", "true")

    def fail_bd(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=("bd",), returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(check.subprocess, "run", fail_bd)

    assert check.main(argv=(str(repo),)) == 1

    captured = capsys.readouterr()
    assert "bd exited 1" in captured.err
    assert (
        "bd read failed; LIVESPEC_STRICT_PLAN_ANCHOR_METADATA=true requires live check"
    ) in captured.err
    assert captured.out == ""
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
    monkeypatch.delenv("LIVESPEC_STRICT_PLAN_ANCHOR_METADATA", raising=False)

    def invalid_json(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=("bd",), returncode=0, stdout="{", stderr="")

    monkeypatch.setattr(check.subprocess, "run", invalid_json)

    assert check.main(argv=(str(repo),)) == 0

    captured = capsys.readouterr()
    assert "bd returned invalid json" in captured.err
    assert captured.out == ""
    assert (
        "bd read failed; LIVESPEC_STRICT_PLAN_ANCHOR_METADATA unarmed; skipping live check"
        in captured.err
    )
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
    monkeypatch.delenv("LIVESPEC_STRICT_PLAN_ANCHOR_METADATA", raising=False)

    def timeout(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=("bd",), timeout=30)

    monkeypatch.setattr(check.subprocess, "run", timeout)

    assert check.main(argv=(str(repo),)) == 0

    captured = capsys.readouterr()
    assert "bd timed out" in captured.err
    assert captured.out == ""
    assert (
        "bd read failed; LIVESPEC_STRICT_PLAN_ANCHOR_METADATA unarmed; skipping live check"
        in captured.err
    )
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
    monkeypatch.delenv("LIVESPEC_STRICT_PLAN_ANCHOR_METADATA", raising=False)

    def non_list_json(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=("bd",), returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(check.subprocess, "run", non_list_json)

    assert check.main(argv=(str(repo),)) == 0

    captured = capsys.readouterr()
    assert "bd returned non-list json" in captured.err
    assert captured.out == ""
    assert (
        "bd read failed; LIVESPEC_STRICT_PLAN_ANCHOR_METADATA unarmed; skipping live check"
        in captured.err
    )
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
    monkeypatch.delenv("LIVESPEC_STRICT_PLAN_ANCHOR_METADATA", raising=False)

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
    monkeypatch.delenv("LIVESPEC_STRICT_PLAN_ANCHOR_METADATA", raising=False)

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
