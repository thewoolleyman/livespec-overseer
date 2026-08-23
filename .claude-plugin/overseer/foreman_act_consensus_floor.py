"""Hard-floor pre-evidence gates for foreman consensus actions."""

from __future__ import annotations

from typing import Final

import jsonio
from foreman_act_types import BLOCKED_SESSION_ANSWER, ActionId, ActResult
from foreman_valve_policy import CONSENSUS

__all__: list[str] = [
    "FOREIGN_FLOORS",
    "FOREIGN_FLOOR_RELAXATION_RATIFIED",
    "LOCAL_FLOORS",
    "pre_evidence_refusal",
]

LOCAL_FLOORS: Final[frozenset[str]] = frozenset()
FOREIGN_FLOORS: Final[frozenset[str]] = frozenset({"truly-unresolvable", "human-gated-by-design"})
FOREIGN_FLOOR_RELAXATION_RATIFIED: Final[bool] = False
"""Foreign floor relaxation is unratified.

Tracked by bd-ib-8jv8 for livespec-orchestrator-beads-fabro
SPECIFICATION/contracts.md section "Every needs-human escalation still reaches
a human", and livespec-38bk for livespec SPECIFICATION/spec.md section "Full
autonomy and the decision rule". Flipping this requires citing ratified
versions in both owning repos.

Owning orchestrator section: "Every needs-human escalation still reaches a human".
Owning livespec section: SPECIFICATION/spec.md section "Full autonomy and the decision rule".
"""


def _result(*, action_id: str | None, reason: str, outcome: str, mutated: bool) -> ActResult:
    return {
        "action_id": action_id,
        "mutated": mutated,
        "outcome": outcome,
        "reason": reason,
    }


def _refused(*, action_id: str | None, reason: str) -> ActResult:
    return _result(action_id=action_id, reason=reason, outcome="refused", mutated=False)


def _valve_category(*, proposal: dict[str, object]) -> str | None:
    valve = jsonio.as_object(value=proposal.get("human_valve"))
    value = None if valve is None else valve.get("category")
    return value if isinstance(value, str) and value != "" else None


def _blocked_answer_category(*, action_id: ActionId, proposal: dict[str, object]) -> str | None:
    if action_id != BLOCKED_SESSION_ANSWER:
        return None
    answer = jsonio.as_object(value=proposal.get("blocked_session_answer"))
    value = None if answer is None else answer.get("category")
    return value if isinstance(value, str) and value != "" else None


def _hard_floor_category(*, action_id: ActionId, proposal: dict[str, object]) -> str | None:
    return _valve_category(proposal=proposal) or _blocked_answer_category(
        action_id=action_id, proposal=proposal
    )


def pre_evidence_refusal(
    *,
    action_id: ActionId,
    proposal: dict[str, object],
    disposition: dict[str, object],
    local_floors: frozenset[str] = LOCAL_FLOORS,
    foreign_floors: frozenset[str] = FOREIGN_FLOORS,
    foreign_floor_relaxation_ratified: bool = FOREIGN_FLOOR_RELAXATION_RATIFIED,
) -> ActResult | None:
    """The gates that bind however the act is later authorized.

    Both the disposition and the hard floors are evaluated BEFORE any
    authorization path is considered, so no carve-out can reach past them.
    """
    if disposition.get("effective") != CONSENSUS:
        reason = "human_action_report_only"
        if disposition.get("recognized") is False:  # pragma: no cover
            reason = "unrecognized_foreman_valve_disposition"
        return _refused(action_id=action_id, reason=reason)
    category = _hard_floor_category(action_id=action_id, proposal=proposal)
    if category in foreign_floors and not foreign_floor_relaxation_ratified:
        return _refused(action_id=action_id, reason=f"hard_floor:{category}")
    if category in local_floors and disposition.get("full_autonomy") is not True:
        return _refused(action_id=action_id, reason=f"hard_floor:{category}")
    return None
