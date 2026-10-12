"""Delivery contract for the dual-backend overseer operator surface."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Protocol, cast

import _supervisor_table_layout
import _supervisor_view
import herdr_identity
import pytest

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
OPERATOR_CONTRACT = ROOT / ".claude-plugin" / "prose" / "overseer.md"
LIVE_EXERCISE = ROOT / "scripts" / "overseer-live-exercise.sh"
EVIDENCE_VERIFIER = ROOT / "scripts" / "overseer_live_exercise_evidence.py"
LIVE_EXERCISE_DOC = ROOT / "overseer" / "live-exercise.md"


class EvidenceModule(Protocol):
    def main(self, *, argv: list[str] | None = None) -> int: ...


def _load_evidence_verifier() -> EvidenceModule:
    assert EVIDENCE_VERIFIER.is_file()
    spec = importlib.util.spec_from_file_location("exercise_evidence", EVIDENCE_VERIFIER)
    assert spec is not None
    assert spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return cast("EvidenceModule", loaded)


def test_the_shipped_contract_bootstraps_the_nearest_verified_backend_without_an_override() -> None:
    prose = OPERATOR_CONTRACT.read_text(encoding="utf-8")

    assert "Linux with either tmux or Herdr" in prose
    assert "nearest positively verified terminal owner" in prose
    assert '"$OVERSEER_START"' in prose
    assert '"$OVERSEER_START" --backend' not in prose
    assert "same original LLM pane" in prose
    assert "running bootstrap again" in prose


def test_the_live_table_names_the_backend_instance_and_exact_herdr_pane() -> None:
    coordinate = herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/run/user/1000/herdr/ops.sock",
            server_pid=4127,
            server_starttime="811092",
            pane_id="w3:p8",
        )
    )
    row = _supervisor_view.RowView(
        topic="backend-parity",
        repo="/work/livespec-overseer",
        tmux=coordinate,
        ctx=37,
        status="blocked:human",
        runtime="codex",
    )
    target = _supervisor_view.tmux_cell(row=row)
    table = _supervisor_table_layout.render_lines(
        rows=[("blocked:human", row.topic, target, "37%", "livespec-overseer")],
        columns=None,
    )

    assert table[0].split() == ["Status", "Topic", "Target", "Ctx%", "Repo"]
    assert target == (
        "herdr /run/user/1000/herdr/ops.sock · server 4127/811092 · " "pane w3:p8 (codex)"
    )


def test_the_live_exercise_plan_isolates_every_operator_resource() -> None:
    assert LIVE_EXERCISE.is_file()
    source = LIVE_EXERCISE.read_text(encoding="utf-8")

    scratch_creation = (
        'scratch_root="$(mktemp -d "${TMPDIR:-/tmp}/livespec-overseer-exercise.XXXXXX")"'
    )
    assert scratch_creation in source
    assert "trap cleanup EXIT HUP INT TERM" in source
    assert 'rm -rf -- "$scratch_root"' in source
    assert '--bind "$scratch_home" "$operator_home"' in source
    assert '--bind "$scratch_tmp" /tmp' in source
    assert '--bind "$scratch_runtime" "/run/user/$operator_uid"' in source
    assert '"repos": ["/tmp/livespec-overseer-exercise-repo"]' in source
    assert 'backend_instance="livespec-overseer-exercise-${backend}-' in source
    assert "-u TMUX_PANE" in source
    assert "-u HERDR_SOCKET_PATH" in source
    assert "HOME=" not in source


def test_runtime_isolation_check_is_distinct_from_plan_inspection() -> None:
    source = LIVE_EXERCISE.read_text(encoding="utf-8")
    documentation = LIVE_EXERCISE_DOC.read_text(encoding="utf-8")

    assert "--isolation-check" in source
    assert '"OVERSEER_EXERCISE_ISOLATION_CHECK=$isolation_check"' in source
    assert "COMPLETE isolation: native backend started and stopped inside namespace" in source
    assert "run --isolation-check" in documentation
    assert "does not prove runtime confinement" in documentation


def test_the_live_exercise_rejects_a_reused_evidence_directory(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    lifecycle = evidence / "lifecycle.jsonl"
    stale_record = '{"stage":"bootstrap","status":"passed"}\n'
    lifecycle.write_text(stale_record, encoding="utf-8")

    completed = subprocess.run(  # noqa: S603 -- fixed repo-owned script.
        [
            str(LIVE_EXERCISE),
            "run",
            "--plan-only",
            "--backend",
            "tmux",
            "--agent",
            "codex",
            "--topic",
            "stale-evidence",
            "--checkout",
            str(ROOT),
            "--evidence",
            str(evidence),
            "--",
            "/bin/true",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert "--evidence must name an empty directory" in completed.stderr
    assert lifecycle.read_text(encoding="utf-8") == stale_record


def test_lifecycle_evidence_never_calls_an_incomplete_or_failed_run_successful(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verifier = _load_evidence_verifier()
    evidence = tmp_path / "lifecycle.jsonl"

    assert verifier.main(argv=[str(evidence)]) == 1
    assert "INCOMPLETE lifecycle" in capsys.readouterr().err

    evidence.write_text("not-json\n", encoding="utf-8")
    assert verifier.main(argv=[str(evidence)]) == 1
    assert "FAILED lifecycle: malformed record at line 1" in capsys.readouterr().err

    evidence.write_text("[]\n", encoding="utf-8")
    assert verifier.main(argv=[str(evidence)]) == 1
    assert "FAILED lifecycle: record 1 is not an object" in capsys.readouterr().err

    stages = ["bootstrap", "adoption", "wrap-up", "declaration", "replacement"]
    records = [json.dumps({"stage": stage, "status": "passed"}) for stage in stages]
    records.append(
        json.dumps({"stage": "continuation", "status": "failed", "detail": "no fresh reply"})
    )
    evidence.write_text("\n".join(records) + "\n", encoding="utf-8")
    assert verifier.main(argv=[str(evidence)]) == 1
    failure = capsys.readouterr().err
    assert "FAILED lifecycle at continuation: no fresh reply" in failure
    assert "COMPLETE lifecycle" not in failure

    evidence.write_text("\n".join(records[:-2]) + "\n", encoding="utf-8")
    assert verifier.main(argv=[str(evidence)]) == 1
    missing = capsys.readouterr().err
    assert "INCOMPLETE lifecycle: missing stages: replacement, continuation" in missing

    complete = [
        json.dumps({"stage": stage, "status": "passed"}) for stage in [*stages, "continuation"]
    ]
    complete.append(json.dumps({"stage": "operator-note", "status": "passed"}))
    evidence.write_text("\n" + "\n".join(complete) + "\n", encoding="utf-8")
    assert verifier.main(argv=[str(evidence)]) == 0
    assert "COMPLETE lifecycle: all required stages passed" in capsys.readouterr().out


def test_lifecycle_evidence_rejects_a_failed_stage_followed_by_passed_duplicate(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verifier = _load_evidence_verifier()
    evidence = tmp_path / "lifecycle.jsonl"
    stages = ["bootstrap", "adoption", "wrap-up", "declaration", "replacement"]
    failed_then_passed = [
        *(json.dumps({"stage": stage, "status": "passed"}) for stage in stages),
        json.dumps({"stage": "continuation", "status": "failed", "detail": "first failure"}),
        json.dumps({"stage": "continuation", "status": "passed"}),
    ]

    evidence.write_text("\n".join(failed_then_passed) + "\n", encoding="utf-8")

    assert verifier.main(argv=[str(evidence)]) == 1
    duplicate = capsys.readouterr().err
    assert "FAILED lifecycle: duplicate required stage continuation at line 7" in duplicate
    assert "COMPLETE lifecycle" not in duplicate


def test_checked_in_evidence_verifier_runs_from_outside_the_checkout(tmp_path: Path) -> None:
    evidence = tmp_path / "missing-lifecycle.jsonl"
    child_env = {
        key: value
        for key, value in os.environ.items()
        if key != "COVERAGE_PROCESS_START" and not key.startswith("COV_CORE_")
    }

    completed = subprocess.run(  # noqa: S603 -- fixed interpreter and repo-owned script.
        [sys.executable, "-I", "-S", str(EVIDENCE_VERIFIER), str(evidence)],
        cwd=tmp_path,
        env=child_env,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == f"INCOMPLETE lifecycle: evidence file is missing: {evidence}\n"
