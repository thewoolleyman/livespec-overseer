"""Consensus-disposition helpers for foreman-act human valves."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import jsonio
from foreman_act_journal import journal_reconcile_command
from foreman_act_record import AppendJournal
from foreman_act_types import ACTION_IDS, HUMAN_VALVE, ActionId, ActResult
from foreman_valve_policy import CONFIG_KEY, CONSENSUS

__all__: list[str] = [
    "ConsensusPanel",
    "act_journal_triage",
    "prepare_consensus_action",
]

_HARD_FLOORS = frozenset({"truly-unresolvable", "human-gated-by-design"})


class ConsensusPanel(Protocol):
    def __call__(
        self, *, request: dict[str, object], responses: dict[str, object]
    ) -> dict[str, object]: ...


class Runner(Protocol):
    def __call__(self, *, argv: list[str]) -> int: ...


def _refused(*, action_id: str | None, reason: str) -> ActResult:
    return {
        "action_id": action_id,
        "mutated": False,
        "outcome": "refused",
        "reason": reason,
    }


def _acted(*, action_id: str, reason: str) -> ActResult:
    return {
        "action_id": action_id,
        "mutated": True,
        "outcome": "acted",
        "reason": reason,
    }


def _failed(*, action_id: str, reason: str) -> ActResult:
    return {  # pragma: no cover
        "action_id": action_id,
        "mutated": False,
        "outcome": "failed",
        "reason": reason,
    }


def _known_action_id(*, value: object) -> ActionId | None:
    return value if isinstance(value, str) and value in ACTION_IDS else None


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
    requested_action_id: ActionId,
    authorized_action_id: ActionId,
) -> dict[str, object]:
    return {
        "stage": "foreman-consensus-act",
        "action_id": requested_action_id,
        "governing_setting": f"{CONFIG_KEY}={CONSENSUS}",
        "repo": proposal.get("repo"),
        "topic": proposal.get("topic"),
        "panel_outcome": verdict.get("outcome"),
        "panel_reason": verdict.get("reason"),
        "panel_cache_key": verdict.get("cache_key"),
        "reviewers": verdict.get("reviewers"),
        "models": verdict.get("models"),
        "authorized_action_id": authorized_action_id,
        "verdict": verdict,
    }


def _authorized_panel_action(*, verdict: dict[str, object]) -> tuple[ActionId | None, str | None]:
    if verdict.get("outcome") != "unanimous":
        reason = verdict.get("reason")  # pragma: no cover
        suffix = (  # pragma: no cover
            reason if isinstance(reason, str) and reason != "" else "not_unanimous"
        )
        return None, f"consensus_not_unanimous:{suffix}"  # pragma: no cover
    action = jsonio.as_object(value=verdict.get("action"))
    action_id = None if action is None else _known_action_id(value=action.get("action_id"))
    if action_id is None:  # pragma: no cover
        return None, "consensus_action_not_enumerated"
    if action_id == HUMAN_VALVE:  # pragma: no cover
        return None, "consensus_action_not_enumerated"
    return action_id, None


def prepare_consensus_action(
    *,
    action_id: ActionId,
    proposal: dict[str, object],
    disposition: dict[str, object],
    consensus_panel: ConsensusPanel,
    append_journal: AppendJournal,
) -> tuple[ActionId | None, ActResult | None]:
    if disposition.get("effective") != CONSENSUS:
        reason = "human_action_report_only"
        if disposition.get("recognized") is False:  # pragma: no cover
            reason = "unrecognized_foreman_valve_disposition"
        return None, _refused(action_id=action_id, reason=reason)
    category = _valve_category(proposal=proposal)
    if category in _HARD_FLOORS:
        return None, _refused(action_id=action_id, reason=f"hard_floor:{category}")
    evidence = _consensus_evidence(proposal=proposal)
    if evidence is None:
        return None, _refused(action_id=action_id, reason="consensus_evidence_unavailable")
    request, responses = evidence
    verdict = consensus_panel(request=request, responses=responses)
    authorized_action_id, refusal = _authorized_panel_action(verdict=verdict)
    if refusal is not None or authorized_action_id is None:  # pragma: no cover
        return None, _refused(action_id=action_id, reason=refusal or "consensus_unavailable")
    try:
        append_journal(
            repo=Path(str(proposal["repo"])),
            record=_audit_record(
                proposal=proposal,
                verdict=verdict,
                requested_action_id=action_id,
                authorized_action_id=authorized_action_id,
            ),
        )
    except OSError:
        return None, _refused(action_id=action_id, reason="journal_append_failed")
    return authorized_action_id, None


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
