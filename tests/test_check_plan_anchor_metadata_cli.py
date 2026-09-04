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


# The PATH the real credential wrapper leaves behind after its `env -i` hop,
# measured on the operator host. A double that scrubs to anything wider would
# prove less than the real thing imposes.
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


def test_pre_push_runs_plan_anchor_check_through_credential_wrapper(
    tmp_path: Path,
) -> None:
    completed, log = _run_pre_push_with_plan_anchor_wrapper(
        tmp_path=tmp_path,
        changed_file="scripts/check-plan-anchor-metadata.py",
    )

    assert completed.returncode == 0
    assert "LIVESPEC_STRICT_PLAN_ANCHOR_METADATA=true just check-plan-anchor-metadata" in log
    assert "just command=check-plan-anchor-metadata plan_anchor_env=true" in log
    assert '"scanned_plan_directories":1' in completed.stdout


def test_pre_push_doc_only_push_runs_plan_anchor_check_then_full_check_not_doc_only_subset(
    tmp_path: Path,
) -> None:
    # PR gate ≡ master gate (livespec plan pr-gate-master-parity R3, livespec-citqsd):
    # the retired zero-.py branch used to delegate a doc-only push to
    # `just check-pre-commit-doc-only`. With that branch gone, a doc-only push now
    # runs the plan-anchor check through the wrapper AND the FULL `just check`, so
    # pre-push no longer runs fewer gates than master on a doc-only changeset.
    completed, log = _run_pre_push_with_plan_anchor_wrapper(
        tmp_path=tmp_path,
        changed_file="plan/new-thread/supervisor-handoff.md",
    )

    assert completed.returncode == 0
    assert "LIVESPEC_STRICT_PLAN_ANCHOR_METADATA=true just check-plan-anchor-metadata" in log
    assert "just command=check-plan-anchor-metadata plan_anchor_env=true" in log
    assert "just command=check plan_anchor_env=<unset>" in log
    assert "check-pre-commit-doc-only" not in log
    assert '"scanned_plan_directories":1' in completed.stdout


def _run_pre_push_with_plan_anchor_wrapper(
    *,
    tmp_path: Path,
    changed_file: str,
) -> tuple[subprocess.CompletedProcess[str], str]:
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
  printf '%s\n' "$PRE_PUSH_CHANGED_FILE"
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
if [[ "$*" == "check-pre-commit-doc-only" ]]; then
  exit 0
fi
echo "unexpected just invocation: $*" >&2
exit 99
""",
    )
    # This double SCRUBS PATH, because the real wrapper does: it re-execs
    # through `sudo` + `env -i` with a short allowlist, so the caller's PATH
    # does not survive the hop. The earlier double called `exec "$@"` with the
    # caller's PATH intact, which made these two tests unable to fail for the
    # one thing they are positioned to catch — whether the check is REACHABLE
    # under the wrapper. With the scrub in place, the stub `just` below lives
    # only on a path the scrub removes, so it is found at all only if the gate
    # carried a usable PATH across the wrapper.
    _write_executable(
        path=bin_dir / "with-livespec-env.sh",
        body=f"""#!/usr/bin/env bash
set -euo pipefail
printf 'wrapper plan_anchor_env=%s command=%s\\n' \\
  "${{LIVESPEC_STRICT_PLAN_ANCHOR_METADATA:-<unset>}}" \\
  "$*" >> "{log_path}"
if [[ "${{1:-}}" == "--" ]]; then
  shift
fi
# FAITHFUL to the real credential wrapper: its stage-1 hop is an `exec env -i` with a
# short allowlist, so the inherited environment is DISCARDED. A stub that merely
# exec-ed its arguments would inherit, and would therefore pass against a caller that
# assigns the lever as a PREFIX on the wrapper -- the exact defect this control exists
# to catch. The allowlisted PATH below is the one the real wrapper hands downstream,
# and notably has no `just` on it.
exec env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin "$@"
""",
    )
    env = _scrub_coverage_env(env=os.environ.copy())
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["PRE_PUSH_CHANGED_FILE"] = changed_file

    completed = subprocess.run(  # noqa: S603
        [bash, str(script)],
        cwd=repo_root,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )

    return completed, log_path.read_text(encoding="utf-8")


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
