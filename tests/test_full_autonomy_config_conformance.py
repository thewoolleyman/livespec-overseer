"""Positive controls for the full-autonomy config conformance gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "check-full-autonomy-config-conformance.py"


def _load_check() -> ModuleType:
    assert _SCRIPT.is_file()
    spec = importlib.util.spec_from_file_location("full_autonomy_config_conformance", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_config(*, repo: Path, drift_acceptance_mode: str, full_autonomy: bool) -> None:
    repo.joinpath(".livespec.jsonc").write_text(
        f"""
{{
  "spec_governance": {{
    "propose_change_mode": "batch",
    "critique_mode": "batch",
    "in_flight_alignment": "default-align",
    "revise_decision_mode": "delegated",
    "ratification_review": "auto-spawn",
    "ratification_reviewer_model": "fable",
    "spec_pr_merge": "auto-on-green",
    "drift_acceptance_mode": "{drift_acceptance_mode}"
  }},
  "livespec-orchestrator-beads-fabro": {{
    "dispatcher": {{
      "acceptance_mode": "ai-only",
      "auto_approve_ready": true
    }}
  }},
  "livespec-overseer": {{
    "full_autonomy": {str(full_autonomy).lower()},
    "foreman_valve_disposition": "consensus"
  }}
}}
""".lstrip(),
        encoding="utf-8",
    )


def _write_all_wrong_false_config(*, repo: Path) -> None:
    repo.joinpath(".livespec.jsonc").write_text(
        """
{
  "spec_governance": {
    "propose_change_mode": "interactive",
    "critique_mode": "interactive",
    "in_flight_alignment": "prompt",
    "revise_decision_mode": "manual",
    "ratification_review": "manual-spawn",
    "ratification_reviewer_model": "",
    "spec_pr_merge": "manual",
    "drift_acceptance_mode": "human"
  },
  "livespec-orchestrator-beads-fabro": {
    "dispatcher": {
      "acceptance_mode": "human",
      "auto_approve_ready": false
    }
  },
  "livespec-overseer": {
    "full_autonomy": false,
    "foreman_valve_disposition": "report-only"
  }
}
""".lstrip(),
        encoding="utf-8",
    )


def _write_missing_drift_config(*, repo: Path) -> None:
    repo.joinpath(".livespec.jsonc").write_text(
        """
{
  "spec_governance": {
    "propose_change_mode": "batch",
    "critique_mode": "batch",
    "in_flight_alignment": "default-align",
    "revise_decision_mode": "delegated",
    "ratification_review": "auto-spawn",
    "ratification_reviewer_model": "fable",
    "spec_pr_merge": "auto-on-green"
  },
  "livespec-orchestrator-beads-fabro": {
    "dispatcher": {
      "acceptance_mode": "ai-only",
      "auto_approve_ready": true
    }
  },
  "livespec-overseer": {
    "full_autonomy": true
  }
}
""".lstrip(),
        encoding="utf-8",
    )


def _write_malformed_spec_governance_config(*, repo: Path) -> None:
    repo.joinpath(".livespec.jsonc").write_text(
        """
{
  "spec_governance": "wrong-shape",
  "livespec-orchestrator-beads-fabro": {
    "dispatcher": {
      "acceptance_mode": "ai-only",
      "auto_approve_ready": true
    }
  },
  "livespec-overseer": {
    "full_autonomy": true,
    "foreman_valve_disposition": "consensus"
  }
}
""".lstrip(),
        encoding="utf-8",
    )


def test_full_autonomy_true_fails_when_one_registered_lever_is_wrong(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_check()
    _write_config(repo=tmp_path, drift_acceptance_mode="human", full_autonomy=True)

    rc = module.main(argv=["--repo", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "spec_governance.drift_acceptance_mode" in captured.err
    assert '"human"' in captured.err
    assert '"consensus"' in captured.err


def test_full_autonomy_true_passes_when_registered_levers_are_at_max(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_check()
    _write_config(repo=tmp_path, drift_acceptance_mode="consensus", full_autonomy=True)

    rc = module.main(argv=["--repo", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out == ""
    assert captured.err == ""


def test_full_autonomy_true_names_absent_registered_lever(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_check()
    _write_missing_drift_config(repo=tmp_path)

    rc = module.main(argv=["--repo", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "spec_governance.drift_acceptance_mode is absent" in captured.err


def test_malformed_registered_section_fails_closed_to_absent_levers(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_check()
    _write_malformed_spec_governance_config(repo=tmp_path)

    rc = module.main(argv=["--repo", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 1
    assert "spec_governance.propose_change_mode is absent" in captured.err


def test_missing_config_passes_as_full_autonomy_absent(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_check()

    rc = module.main(argv=["--repo", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out == ""
    assert captured.err == ""


def test_full_autonomy_false_passes_without_reading_sibling_levers(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_check()
    _write_all_wrong_false_config(repo=tmp_path)

    rc = module.main(argv=["--repo", str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out == ""
    assert captured.err == ""
