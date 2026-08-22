"""Consensus-disposition helpers for foreman-act human valves."""
# livespec-lloc-soft-band-owner: overseer-3h4s5w.3

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Final, Protocol, cast

import jsonio
from foreman_act_journal import journal_reconcile_command
from foreman_act_record import AppendJournal
from foreman_act_types import ACTION_IDS, BLOCKED_SESSION_ANSWER, HUMAN_VALVE, ActionId, ActResult
from foreman_consensus_actions import typed_action
from foreman_consensus_types import DecisionRule
from foreman_recorded_next_action import (
    RecordedNextAction,
    recorded_next_action_authorization,
)
from foreman_typed_ruling import ruling_kind_defined
from foreman_valve_policy import CONFIG_KEY, CONSENSUS, MAJORITY, UNANIMOUS

__all__: list[str] = [
    "ConsensusPanel",
    "act_journal_triage",
    "prepare_consensus_action",
]

_LOCAL_FLOORS: Final[frozenset[str]] = frozenset()
_FOREIGN_FLOORS: Final[frozenset[str]] = frozenset({"truly-unresolvable", "human-gated-by-design"})
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


class ConsensusPanel(Protocol):
    def __call__(
        self,
        *,
        request: dict[str, object],
        responses: dict[str, object],
        decision_rule: DecisionRule | None = None,
    ) -> dict[str, object]: ...


class Runner(Protocol):
    def __call__(self, *, argv: list[str]) -> int: ...


def _result(*, action_id: str | None, reason: str, outcome: str, mutated: bool) -> ActResult:
    return {
        "action_id": action_id,
        "mutated": mutated,
        "outcome": outcome,
        "reason": reason,
    }


def _refused(*, action_id: str | None, reason: str) -> ActResult:
    return _result(action_id=action_id, reason=reason, outcome="refused", mutated=False)


def _acted(*, action_id: str, reason: str) -> ActResult:
    return _result(action_id=action_id, reason=reason, outcome="acted", mutated=True)


def _failed(*, action_id: str, reason: str) -> ActResult:
    return _result(  # pragma: no cover
        action_id=action_id, reason=reason, outcome="failed", mutated=False
    )


def _known_action_id(*, value: object) -> ActionId | None:
    return value if isinstance(value, str) and value in ACTION_IDS else None


def _known_decision_rule(*, value: object) -> DecisionRule | None:
    return cast(DecisionRule, value) if value in {MAJORITY, UNANIMOUS} else None


def _panel_accepts_decision_rule(*, consensus_panel: ConsensusPanel) -> bool:
    parameters = inspect.signature(consensus_panel).parameters.values()
    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD or parameter.name == "decision_rule"
        for parameter in parameters
    )


def _panel_verdict(
    *,
    consensus_panel: ConsensusPanel,
    request: dict[str, object],
    responses: dict[str, object],
    decision_rule: DecisionRule | None,
) -> dict[str, object]:
    if _panel_accepts_decision_rule(consensus_panel=consensus_panel):
        return consensus_panel(
            request=request,
            responses=responses,
            decision_rule=decision_rule,
        )
    return consensus_panel(request=request, responses=responses)


def _valve_category(*, proposal: dict[str, object]) -> str | None:
    valve = jsonio.as_object(value=proposal.get("human_valve"))
    value = None if valve is None else valve.get("category")
    return value if isinstance(value, str) and value != "" else None


def _consensus_evidence(
    *, proposal: dict[str, object]
) -> tuple[dict[str, object], dict[str, object]] | None:
    evidence = jsonio.as_object(value=proposal.get("consensus"))
    if evidence is None:
        return None
    request = jsonio.as_object(value=evidence.get("request"))
    responses = jsonio.as_object(value=evidence.get("reviewer_responses"))
    if request is None or responses is None:  # pragma: no cover
        return None
    return request, responses


def _audit_record(
    *,
    proposal: dict[str, object],
    verdict: dict[str, object],
    disposition: dict[str, object],
    requested_action_id: ActionId,
    authorized_action_id: ActionId | None,
) -> dict[str, object]:
    return {
        "stage": "foreman-consensus-act",
        "action_id": requested_action_id,
        "governing_setting": f"{CONFIG_KEY}={CONSENSUS}",
        "decision_rule": verdict.get("decision_rule"),
        "full_autonomy": disposition.get("full_autonomy"),
        "repo": proposal.get("repo"),
        "topic": proposal.get("topic"),
        "panel_outcome": verdict.get("outcome"),
        "panel_reason": verdict.get("reason"),
        "panel_cache_key": verdict.get("cache_key"),
        "reviewers": verdict.get("reviewers"),
        "models": verdict.get("models"),
        "authorized_action_id": authorized_action_id,
        "verdict": verdict,
        "authorized_member_kind": "action",
    }


def _recorded_next_action_record(
    *, proposal: dict[str, object], recorded: RecordedNextAction
) -> dict[str, object]:
    return {
        "stage": "foreman-recorded-next-action",
        "action_id": BLOCKED_SESSION_ANSWER,
        "governing_setting": f"{CONFIG_KEY}={CONSENSUS}",
        "repo": proposal.get("repo"),
        "topic": proposal.get("topic"),
        "matched_text": recorded.matched_text,
        "source": recorded.source,
    }


def _prepare_recorded_next_action(
    *, action_id: ActionId, proposal: dict[str, object], append_journal: AppendJournal
) -> tuple[ActionId | None, ActResult | None] | None:
    """Authorize a picker answer that restates the plan's recorded next action.

    Returns None when the carve-out was not claimed or does not match, leaving
    the consensus path to decide. The carve-out stands in for panel EVIDENCE
    only; the disposition gate and the hard floors have already been applied by
    the caller and are not reached through here.
    """
    if action_id != BLOCKED_SESSION_ANSWER:
        return None
    recorded, refusal = recorded_next_action_authorization(proposal=proposal)
    if refusal is not None:
        return None, _refused(action_id=action_id, reason=refusal)
    if recorded is None:
        return None
    try:
        append_journal(
            repo=Path(str(proposal["repo"])),
            record=_recorded_next_action_record(proposal=proposal, recorded=recorded),
        )
    except OSError:  # pragma: no cover
        return None, _refused(action_id=action_id, reason="journal_append_failed")
    return action_id, None


def _authorized_panel_member(
    *, verdict: dict[str, object], effective_decision_rule: object
) -> tuple[ActionId | None, str | None]:
    if verdict.get("outcome") not in {"majority", "unanimous"}:
        reason = verdict.get("reason")  # pragma: no cover
        suffix = (  # pragma: no cover
            reason if isinstance(reason, str) and reason != "" else "not_unanimous"
        )
        return None, f"consensus_not_unanimous:{suffix}"  # pragma: no cover
    if verdict.get("outcome") == "majority" and (
        verdict.get("decision_rule") != MAJORITY or effective_decision_rule != MAJORITY
    ):
        return None, "consensus_majority_requires_majority_rule"
    action = typed_action(action=verdict.get("action"))
    if action is not None and action.get("member_kind") == "typed_ruling":
        ruling = jsonio.as_object(value=action.get("ruling"))
        kind = None if ruling is None else ruling.get("kind")
        if not isinstance(kind, str) or not ruling_kind_defined(kind=kind):
            return None, "consensus_ruling_not_enumerated"
        return None, "consensus_ruling_not_supported"
    action_id = None if action is None else _known_action_id(value=action.get("action_id"))
    if action_id is None or action_id == HUMAN_VALVE:  # pragma: no cover
        return None, "consensus_action_not_enumerated"
    return action_id, None


def _pre_evidence_refusal(
    *, action_id: ActionId, proposal: dict[str, object], disposition: dict[str, object]
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
    category = _valve_category(proposal=proposal)
    if category in _FOREIGN_FLOORS and not FOREIGN_FLOOR_RELAXATION_RATIFIED:
        return _refused(action_id=action_id, reason=f"hard_floor:{category}")
    if category in _LOCAL_FLOORS and disposition.get("full_autonomy") is not True:
        return _refused(action_id=action_id, reason=f"hard_floor:{category}")
    return None


def prepare_consensus_action(
    *,
    action_id: ActionId,
    proposal: dict[str, object],
    disposition: dict[str, object],
    consensus_panel: ConsensusPanel,
    append_journal: AppendJournal,
) -> tuple[ActionId | None, ActResult | None]:
    pre_evidence = _pre_evidence_refusal(
        action_id=action_id, proposal=proposal, disposition=disposition
    )
    if pre_evidence is not None:
        return None, pre_evidence
    carve_out = _prepare_recorded_next_action(
        action_id=action_id, proposal=proposal, append_journal=append_journal
    )
    if carve_out is not None:
        return carve_out
    evidence = _consensus_evidence(proposal=proposal)
    if evidence is None:
        return None, _refused(action_id=action_id, reason="consensus_evidence_unavailable")
    request, responses = evidence
    decision_rule = _known_decision_rule(value=disposition.get("decision_rule"))
    verdict = _panel_verdict(
        consensus_panel=consensus_panel,
        request=request,
        responses=responses,
        decision_rule=decision_rule,
    )
    authorized_member, refusal = _authorized_panel_member(
        verdict=verdict, effective_decision_rule=decision_rule
    )
    if refusal is not None or authorized_member is None:  # pragma: no cover
        refused_action_id = (
            HUMAN_VALVE if refusal == "consensus_ruling_not_enumerated" else action_id
        )
        return None, _refused(
            action_id=refused_action_id, reason=refusal or "consensus_unavailable"
        )
    authorized_action_id = authorized_member
    try:
        append_journal(
            repo=Path(str(proposal["repo"])),
            record=_audit_record(
                proposal=proposal,
                verdict=verdict,
                disposition=disposition,
                requested_action_id=action_id,
                authorized_action_id=authorized_action_id,
            ),
        )
    except OSError:
        return None, _refused(action_id=action_id, reason="journal_append_failed")
    return authorized_member, None


def act_journal_triage(
    *,
    action_id: ActionId,
    proposal: dict[str, object],
    document: dict[str, object],
    repo: str,
    run: Runner,
) -> ActResult:
    refusal, command = journal_reconcile_command(proposal=proposal, document=document, repo=repo)
    if refusal is not None or command is None:
        return _refused(action_id=action_id, reason=refusal or "unsupported_transition")
    code = run(argv=command)
    if code != 0:  # pragma: no cover
        return _failed(action_id=action_id, reason=f"command_exit_{code}")
    return _acted(action_id=action_id, reason="reconciled_merged_dispatch")
