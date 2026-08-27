"""Integration coverage for the escalation-refusal floor and for its boundary.

Pins two ratified scenarios in `SPECIFICATION/scenarios.md`: an escalation
proposing repair of an absent component is refused with the available remedy
named, and a genuine report of missing infrastructure is still raised.

Both halves are required, and the second is not a nicety. A refusal without its
boundary would let the foreman suppress a true report that required
infrastructure is missing — which the ratified clause forbids in terms, because
the rule governs a remedy the foreman could have taken and did not, and is never
licence to become the arbiter of what exists.

A third test carries the other half of the clause's CONJUNCTION: an escalation
naming a component this deployment DOES ship is raised even where an enumerated
remedy is available. Without it an implementation that refuses every escalation
whenever some remedy exists passes both ratified scenarios while refusing
escalations the floor never reaches.

The evaluation drives the shipped escalation surface end to end, against a
roster the shipped roster CLI composed on a real tick, because the refusal has
to read the SAME enumerated remedy the tick identified. A test that handed the
evaluator a remedy of its own would pin nothing about that agreement.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import foreman_act_types
import foreman_plan_roster
import pytest

__all__: list[str] = []

OVERSEER_DIR = Path(__file__).resolve().parents[2] / "overseer"
MODULE_PATH = OVERSEER_DIR / "foreman_escalate.py"
CONFIG_KEY = "unrouted_plan_bound"
# The motivating incident, verbatim in shape: a seat seeing a plan unactioned
# past its bound escalated a repair of a resident drain process, which this
# session-driven deployment does not have, while `plan_start` — the act the
# DELEGATION FLOOR enumerates for a plan with no session — sat available.
ABSENT_COMPONENT = "Dispatcher drain loop"
INCIDENT_REASON = "start or repair the Dispatcher drain loop so the plan's ready work moves"
# The deferral this plan recorded at baseline: the full-cycle probe primitive
# genuinely does not exist here, and no enumerated remedy addresses its absence.
MISSING_INFRASTRUCTURE = "full-cycle-probe"
MISSING_INFRASTRUCTURE_REASON = (
    "the full-cycle-probe primitive is not released, so the loop-is-live claim "
    "cannot be gated on a passing probe"
)
# A component this deployment really does ship, used as the control that the
# refusal turns on the component being ABSENT rather than on a remedy existing.
PRESENT_COMPONENT = "overseerd"
PLAN = "alpha"


def escalate_module() -> ModuleType:
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_escalate")


def write_repo(*, repo: Path) -> None:
    (repo / "plan" / PLAN).mkdir(parents=True)
    (repo / ".livespec.jsonc").write_text(
        json.dumps({"livespec-overseer": {CONFIG_KEY: 1}}), encoding="utf-8"
    )
    (repo / "attention.json").write_text(
        json.dumps({"schema_version": 1, "items": [{"id": "item-alpha", "tmux": PLAN}]}),
        encoding="utf-8",
    )


def roster_with_available_remedy(
    *, repo: Path, capsys: pytest.CaptureFixture[str]
) -> tuple[Path, str]:
    """Tick the shipped roster CLI and return its document plus the remedy it identified."""
    argv = [
        "--repo",
        str(repo),
        "--snapshot-path",
        str(repo / "absent-snapshot.json"),
        "--tick-identity",
        "daemon-1:1",
        "--tmux-session",
        "",
    ]
    assert foreman_plan_roster.main(argv=argv) == 0
    emitted = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    roster = json.loads(emitted[-1])
    rows = [row for row in roster["rows"] if row["plan"] == PLAN]
    assert len(rows) == 1
    assert rows[0]["unrouted_plan_condition"] == "holds"
    remedy = rows[0]["unrouted_plan_remedy"]
    assert remedy in foreman_act_types.ACTION_IDS
    path = repo / "roster.json"
    path.write_text(json.dumps(roster, sort_keys=True), encoding="utf-8")
    return path, remedy


def evaluate(
    *,
    module: ModuleType,
    capsys: pytest.CaptureFixture[str],
    repo: Path,
    component: str,
    reason: str,
    condition: tuple[str, Path] | None = None,
) -> dict[str, object]:
    """Drive the shipped surface; `condition` names the plan and the roster that determined it."""
    argv = ["--repo", str(repo), "--component", component, "--reason", reason]
    if condition is not None:
        plan, roster = condition
        argv += ["--plan", plan, "--roster", str(roster)]
    assert module.main(argv=argv) == 0
    emitted = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    verdict = json.loads(emitted[-1])
    assert isinstance(verdict, dict)
    return verdict


def test_an_escalation_proposing_repair_of_an_absent_component_is_refused(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert MODULE_PATH.is_file()
    module = escalate_module()
    repo = tmp_path / "repo"
    write_repo(repo=repo)
    roster, remedy = roster_with_available_remedy(repo=repo, capsys=capsys)

    verdict = evaluate(
        module=module,
        capsys=capsys,
        repo=repo,
        component=ABSENT_COMPONENT,
        reason=INCIDENT_REASON,
        condition=(PLAN, roster),
    )

    assert verdict["verdict"] == module.REFUSED
    assert verdict["absent_component"] == ABSENT_COMPONENT
    # The remedy named is the one THE TICK identified, not one this test chose.
    assert verdict["available_remedy"] == remedy
    # Actionable rather than merely obstructive: the refusal names BOTH.
    assert ABSENT_COMPONENT in str(verdict["reason"])
    assert str(remedy) in str(verdict["reason"])
    # Refused rather than raised: the daemon reads exactly one marker path, and
    # a refusal leaves it unwritten, so nothing reaches the attention surface.
    assert not Path(str(verdict["escalation_path"])).exists()


def test_a_genuine_report_of_missing_infrastructure_is_still_raised(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert MODULE_PATH.is_file()
    module = escalate_module()
    repo = tmp_path / "repo"
    write_repo(repo=repo)
    roster, remedy = roster_with_available_remedy(repo=repo, capsys=capsys)

    raised = evaluate(
        module=module,
        capsys=capsys,
        repo=repo,
        component=MISSING_INFRASTRUCTURE,
        reason=MISSING_INFRASTRUCTURE_REASON,
    )

    assert raised["verdict"] == module.RAISED
    # It is NOT refused on account of the named component being absent: the
    # component IS absent, and the verdict records that it is, and it is raised
    # anyway, because no enumerated remedy addresses this condition.
    assert raised["absent_component"] == MISSING_INFRASTRUCTURE
    assert raised["available_remedy"] is None
    marker = Path(str(raised["escalation_path"]))
    written = marker.read_text(encoding="utf-8")
    # Raised means the marker the daemon reads carries the escalation's OWN
    # text, unaltered — the report reaches the attention surface as written.
    assert json.loads(written)["reason"] == MISSING_INFRASTRUCTURE_REASON

    # THE DISCRIMINATING CONTROL. The same absent component and the same
    # escalation text, evaluated against a condition an enumerated remedy DOES
    # address, is refused. So the raise above is caused by the absence of a
    # remedy and by nothing about the component, which is the only reading under
    # which the boundary bounds anything.
    refused = evaluate(
        module=module,
        capsys=capsys,
        repo=repo,
        component=MISSING_INFRASTRUCTURE,
        reason=MISSING_INFRASTRUCTURE_REASON,
        condition=(PLAN, roster),
    )
    assert refused["verdict"] == module.REFUSED
    assert refused["available_remedy"] == remedy
    # A refusal writes nothing at all: the marker is BYTE-UNCHANGED from what
    # the raise put there, so a refusal is proven to write nothing rather than
    # merely to report nothing.
    assert marker.read_text(encoding="utf-8") == written


def test_an_escalation_naming_a_component_this_deployment_ships_is_raised(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert MODULE_PATH.is_file()
    module = escalate_module()
    repo = tmp_path / "repo"
    write_repo(repo=repo)
    roster, remedy = roster_with_available_remedy(repo=repo, capsys=capsys)

    verdict = evaluate(
        module=module,
        capsys=capsys,
        repo=repo,
        component=PRESENT_COMPONENT,
        reason=f"{PRESENT_COMPONENT} is wedged and the plan cannot move",
        condition=(PLAN, roster),
    )

    # The floor is a CONJUNCTION. An available remedy alone does not reach it,
    # so an escalation about machinery this deployment really has stands even
    # where the foreman could have acted instead.
    assert verdict["verdict"] == module.RAISED
    assert verdict["absent_component"] is None
    assert verdict["available_remedy"] == remedy
    assert Path(str(verdict["escalation_path"])).is_file()
    assert PRESENT_COMPONENT in module.deployment_component_names()
    assert module.component_slug(component=ABSENT_COMPONENT) not in (
        module.deployment_component_names()
    )


def test_an_unresolvable_remedy_fails_toward_raising_the_escalation() -> None:
    assert MODULE_PATH.is_file()
    module = escalate_module()
    components = module.deployment_component_names()
    escalation = module.ProposedEscalation(
        component=ABSENT_COMPONENT, plan=PLAN, reason=INCIDENT_REASON
    )
    unresolvable: tuple[dict[str, object], ...] = (
        {},
        {"rows": "not-a-list"},
        {"rows": ["not-an-object"]},
        {"rows": [{"plan": "other-plan", "unrouted_plan_remedy": "plan_start"}]},
        {"rows": [{"plan": PLAN, "unrouted_plan_remedy": None}]},
        {"rows": [{"plan": PLAN, "unrouted_plan_remedy": "not-an-enumerated-act"}]},
    )
    for roster in unresolvable:
        verdict = module.evaluate_escalation(
            escalation=escalation, roster=roster, components=components
        )
        assert verdict.verdict == module.RAISED
        assert verdict.available_remedy is None
        assert verdict.reason == INCIDENT_REASON

    # The control: the identical escalation against a roster that DOES carry an
    # enumerated remedy for the same plan is refused, so each raise above is the
    # unavailability of a remedy rather than a refusal path that never fires.
    resolved = module.evaluate_escalation(
        escalation=escalation,
        roster={"rows": [{"plan": PLAN, "unrouted_plan_remedy": foreman_act_types.PLAN_START}]},
        components=components,
    )
    assert resolved.verdict == module.REFUSED
    assert resolved.available_remedy == foreman_act_types.PLAN_START
    assert resolved.absent_component == ABSENT_COMPONENT


def test_an_escalation_naming_no_plan_resolves_no_enumerated_remedy() -> None:
    assert MODULE_PATH.is_file()
    module = escalate_module()
    verdict = module.evaluate_escalation(
        escalation=module.ProposedEscalation(
            component=ABSENT_COMPONENT, plan=None, reason=INCIDENT_REASON
        ),
        roster={"rows": [{"plan": PLAN, "unrouted_plan_remedy": foreman_act_types.PLAN_START}]},
        components=module.deployment_component_names(),
    )
    assert verdict.verdict == module.RAISED
    assert verdict.available_remedy is None
    assert verdict.document()["plan"] is None
