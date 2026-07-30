"""Verification-discipline rules must discriminate, not merely exist.

The generated supervisor handoff contract now emits two commands for two
separate rules:

* filed work-item status is a timestamped claim, so re-measure from the ledger;
* a pipeline reports the last command's exit status, so preserve the verdict
  command's status before filtering output.

These fixtures demonstrate each rule RED with the bad substitution. They are
small shell/data rigs rather than prose assertions because the acceptance bar is
that the emitted commands can fail for the defect they prevent.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

__all__: list[str] = []


def _run_shell(*, script: str) -> subprocess.CompletedProcess[str]:
    """Run a literal shell fixture.

    S603 is suppressed narrowly: every script is an in-module literal fixture,
    not user input, and the point of these tests is shell pipeline semantics.
    """
    return subprocess.run(  # noqa: S603
        ["sh", "-c", script],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def _status_without_remeasurement(*, filed_claim: str) -> str:
    return filed_claim


def _status_with_remeasurement(*, ledger_json: Path) -> str:
    return str(json.loads(ledger_json.read_text(encoding="utf-8"))["status"])


def test_a_failing_verdict_command_reports_success_when_laundered_through_a_pipe() -> None:
    """RED demonstration: substitute the piped form and the failure is hidden."""
    piped = _run_shell(script="false | head -1")
    preserved = _run_shell(
        script="false; verdict_rc=$?; printf '%s\n' ignored | head -1; exit $verdict_rc"
    )
    assert piped.returncode == 0
    assert preserved.returncode != 0


def test_a_stale_filed_claim_is_carried_forward_without_ledger_remeasurement(
    *, tmp_path: Path
) -> None:
    """RED demonstration: remove re-measurement and stale prose stays current."""
    ledger = tmp_path / "item.json"
    ledger.write_text(json.dumps({"id": "overseer-nxaho7", "status": "closed"}), encoding="utf-8")
    filed_claim = "pending"
    assert _status_without_remeasurement(filed_claim=filed_claim) == "pending"
    assert _status_with_remeasurement(ledger_json=ledger) == "closed"
