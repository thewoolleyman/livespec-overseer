"""Published drain instructions preserve receipt-bound incident routing.

These integration checks read the three shipped bindings and their shared
operator artifact. They pin the instruction contract, not live incident
execution; released-tooling incident drills remain the owning plan's proof.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / ".claude-plugin"
PROSE = PLUGIN / "prose" / "drain-backlog.md"
START = "### Receipt-bound incident selection comes first"
END = "### Normal factory preconditions"

# EXPEDITED_INCIDENT_RESPONSE flag: overseer-czsqpx


def _incident_instructions(body: str) -> str:
    assert START in body, "incident selection must precede factory preconditions"
    assert END in body, "ordinary work must retain its normal preconditions"
    assert body.index(START) < body.index(END)
    return body.split(START, 1)[1].split(END, 1)[0]


@pytest.mark.parametrize(
    "binding",
    [
        "skills/drain-backlog/SKILL.md",
        ".codex-plugin/skills/drain-backlog/SKILL.md",
        ".pi-plugin/skills/livespec-overseer-drain-backlog/SKILL.md",
    ],
)
def test_each_harness_reads_receipt_selection_before_factory_preconditions(binding: str) -> None:
    assert "prose/drain-backlog.md" in (PLUGIN / binding).read_text()
    instructions = _incident_instructions(PROSE.read_text())
    assert (
        "before factory admission, credential probing or a green-master precondition"
        in instructions
    )
    assert "active implementation orchestrator's supported incident reader" in instructions
    assert "item, attempt, phase, repository and current operation identity" in instructions


@pytest.mark.parametrize(
    ("observation", "required_route"),
    [
        ("Current authorized repair", "sanctioned local incident worktree, commit and push"),
        ("Current recorded emergency revert", "sanctioned recorded inverse"),
        ("Normal repayment or ordinary work", "normal factory route"),
        ("Stale attempt or lost ownership", "no incident side effect"),
        ("Unavailable or unsupported incident reader", "precise missing capability"),
    ],
)
def test_canonical_observations_have_explicit_routes(observation: str, required_route: str) -> None:
    instructions = _incident_instructions(PROSE.read_text())
    rows = [line for line in instructions.splitlines() if line.startswith(f"| {observation} |")]
    assert len(rows) == 1
    assert required_route in rows[0]


def test_a_label_or_ambient_flag_cannot_authorize_recovery() -> None:
    instructions = _incident_instructions(PROSE.read_text())
    assert (
        "An ambient flag, retained marker or factory-exempt label is never authorization"
        in instructions
    )
    assert (
        "revalidate canonical phase, generation and ownership immediately before each side effect"
        in instructions
    )
    assert "never an unrestricted audit allow-label" in PROSE.read_text()
    assert "do not invent an incident command, receipt or second lifecycle store" in instructions


def test_repair_records_focused_evidence_without_broad_bypasses() -> None:
    instructions = _incident_instructions(PROSE.read_text())
    assert "For a repair, record changed or directly related tests" in instructions
    for obligation in (
        "changed or directly related tests",
        "coverage scoped to touched product files",
        "one manual incident reproduction",
        "deferred verification and specification work",
        "--no-verify",
        "LEFTHOOK disabling",
        "primary-checkout mutation",
        "unsafe host mutation",
        "independently verified supervising mechanism",
    ):
        assert obligation in instructions
    assert (
        "Do not launch the normal full aggregate or probe the factory to authorize this route"
        in instructions
    )


def test_normal_master_success_retains_same_item_repayment_and_closure_debt() -> None:
    instructions = _incident_instructions(PROSE.read_text())
    assert "canonical observer records normal-master success" in instructions
    assert "new unexpedited factory run on the SAME incident item" in instructions
    assert "no incident execution flag set" in instructions
    assert "original cumulative change scope" in instructions
    assert "final normal factory, PR and master proof plus repaid debt" in instructions
    assert (
        "ready-only restart, independent recovery and plan proof/archive interlocks" in instructions
    )


def test_deferred_proof_defects_and_deployed_regressions_have_distinct_routes() -> None:
    instructions = _incident_instructions(PROSE.read_text())
    assert "follow-up-only proof defect is fixed in that follow-up" in instructions
    assert "without reverting otherwise healthy master solely for that finding" in instructions
    assert (
        "canonically attributed deployed or other-PR regression returns to incident recovery"
        in instructions
    )
    assert "current generation fence" in instructions


def test_ordinary_failed_run_policy_is_not_an_incident_authorization() -> None:
    body = PROSE.read_text()
    assert "ordinary failed factory run" in body
    assert "does not itself authorize the incident route" in body
    assert "factory-exempt:expedited-incident" in body
    assert "same incident item" in body.split("The `/loop` prompt", 1)[1]


def test_missing_or_late_incident_selection_is_detected() -> None:
    body = PROSE.read_text()
    with pytest.raises(AssertionError, match="incident selection"):
        _incident_instructions(body.replace(START, "### Removed selection"))
    with pytest.raises(AssertionError):
        _incident_instructions(f"{END}\n{START}\n")
