"""Evaluate a proposed foreman escalation, and raise it only where the floor allows.

Ratified by v035 in `SPECIFICATION/spec.md`, in its relay and escalation floors:
where an escalation's proposed remedy names a component that is not part of this
deployment, AND a remedy the DELEGATION FLOOR enumerates addresses the same
condition and is available to the foreman, the foreman MUST refuse to raise that
escalation, naming both the absent component and the enumerated remedy that was
available — so the refusal is actionable rather than merely obstructive.

The refusal is MECHANICAL on purpose. A sweep of this repository found the
motivating incident's escalation vocabulary in no prose, package or spec file
here, which means the seat that raised it composed the wording at run time. No
wording change can prevent the next one, so only a refusal the foreman itself
performs closes the gap.

BOTH LEGS OF THE CONJUNCTION ARE RESOLVED HERE rather than declared by the
caller, because the seat that raises such an escalation is precisely the seat
that believed the absent component existed; a mechanism that asked it would be
answered wrongly for the same reason the escalation was wrong. A component is
part of this deployment when the package ships a file for it — a module or an
executable entry point — and the remedy is read from the tick's own roster
document, whose per-plan remedy the DELEGATION FLOOR enumeration already bounds.
There is no whitelist of component names in this tree, and none may be added:
the inventory is measured from what ships.

WHERE NO ENUMERATED REMEDY ADDRESSES THE CONDITION THE ESCALATION IS RAISED, and
every unresolvable input fails toward raising rather than toward silence. An
escalation naming no plan, a plan the roster does not carry, a roster that
cannot be read, and a row carrying no remedy all leave the escalation standing.
This rule governs a remedy the foreman COULD have taken and did not; it is never
licence to suppress a genuine report that required infrastructure is missing,
and an implementation that failed closed here would make the foreman the arbiter
of what exists.

Raising writes the one marker path the daemon reads, so a refusal is observable
as that marker's absence: nothing reaches the mechanical attention surface, and
the foreman is left with the enumerated remedy the refusal named.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import jsonio
import streams
from _supervisor_foreman_escalation import escalation_path
from foreman_act_types import ACTION_IDS, ActionId
from foreman_runtime_identity import canonical_session_name
from foreman_runtime_state import atomic_json, read_json_object

__all__: list[str] = [
    "PACKAGE_DIR",
    "RAISED",
    "REFUSED",
    "EscalationVerdict",
    "ProposedEscalation",
    "component_slug",
    "deployment_component_names",
    "evaluate_escalation",
    "main",
]

RAISED: Final[str] = "raised"
REFUSED: Final[str] = "refused"
PACKAGE_DIR: Final[Path] = Path(__file__).resolve().parent
_ROW_PLAN_KEY: Final[str] = "plan"
_ROW_REMEDY_KEY: Final[str] = "unrouted_plan_remedy"
_NON_SLUG_RUN: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, kw_only=True)
class ProposedEscalation:
    """What a seat proposes to raise: its text, the component its remedy names, its condition."""

    component: str
    plan: str | None
    reason: str


@dataclass(frozen=True, kw_only=True)
class EscalationVerdict:
    """Whether the escalation is raised, and the two facts that decided it."""

    absent_component: str | None
    available_remedy: ActionId | None
    plan: str | None
    reason: str
    verdict: str

    def document(self) -> dict[str, object]:
        return {
            "absent_component": self.absent_component,
            "available_remedy": self.available_remedy,
            "plan": self.plan,
            "reason": self.reason,
            "verdict": self.verdict,
        }


def component_slug(*, component: str) -> str:
    """Normalize a component named in prose to the form the shipped inventory carries."""
    return _NON_SLUG_RUN.sub("-", component.lower()).strip("-")


def deployment_component_names() -> frozenset[str]:
    """The components this deployment HAS, measured from the files the package ships."""
    return frozenset(
        component_slug(component=child.stem) for child in PACKAGE_DIR.iterdir() if child.is_file()
    )


def _available_enumerated_remedy(*, roster: dict[str, object], plan: str | None) -> ActionId | None:
    """The DELEGATION-FLOOR-enumerated remedy the tick already identified for that plan."""
    rows = jsonio.as_list(value=roster.get("rows"))
    if plan is None or rows is None:
        return None
    for raw in rows:
        row = jsonio.as_object(value=raw)
        if row is None or row.get(_ROW_PLAN_KEY) != plan:
            continue
        remedy = row.get(_ROW_REMEDY_KEY)
        if isinstance(remedy, str) and remedy in ACTION_IDS:
            return remedy
    return None


def _refusal_reason(*, escalation: ProposedEscalation, remedy: ActionId) -> str:
    """Name BOTH facts, because a refusal that names neither cannot be acted on."""
    return (
        f"refused to raise this escalation: its proposed remedy names "
        f"'{escalation.component}', which is not part of this deployment, while the "
        f"enumerated remedy '{remedy}' addresses the same condition for plan "
        f"'{escalation.plan}' and was available to the foreman"
    )


def evaluate_escalation(
    *,
    escalation: ProposedEscalation,
    roster: dict[str, object],
    components: frozenset[str],
) -> EscalationVerdict:
    """Refuse only on the full conjunction; every other reading raises the escalation."""
    remedy = _available_enumerated_remedy(roster=roster, plan=escalation.plan)
    present = component_slug(component=escalation.component) in components
    absent_component = None if present else escalation.component
    if absent_component is not None and remedy is not None:
        return EscalationVerdict(
            absent_component=absent_component,
            available_remedy=remedy,
            plan=escalation.plan,
            reason=_refusal_reason(escalation=escalation, remedy=remedy),
            verdict=REFUSED,
        )
    # Raised, and the absent component is still REPORTED where there was one, so
    # the record shows the escalation was not refused on account of it.
    return EscalationVerdict(
        absent_component=absent_component,
        available_remedy=remedy,
        plan=escalation.plan,
        reason=escalation.reason,
        verdict=RAISED,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foreman-escalate")
    _ = parser.add_argument("--repo", default=str(Path.cwd()))
    _ = parser.add_argument("--component", required=True)
    _ = parser.add_argument("--reason", required=True)
    _ = parser.add_argument("--plan", default=None)
    _ = parser.add_argument("--roster", default=None)
    return parser


def main(*, argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo = Path(args.repo).resolve()
    roster = {} if args.roster is None else read_json_object(path=Path(args.roster))
    verdict = evaluate_escalation(
        escalation=ProposedEscalation(component=args.component, plan=args.plan, reason=args.reason),
        roster=roster,
        components=deployment_component_names(),
    )
    path = escalation_path(repo=str(repo), topic=canonical_session_name(repo=repo))
    if verdict.verdict == RAISED:
        atomic_json(path=path, payload={"reason": verdict.reason})
    document = verdict.document()
    document["escalation_path"] = str(path)
    streams.write_stdout(text=json.dumps(document, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
