"""Journal-record helpers for foreman consensus actions."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import jsonio
from foreman_act_record import AppendJournal
from foreman_act_types import BLOCKED_SESSION_ANSWER, ActionId, ActResult
from foreman_recorded_next_action import (
    RecordedNextAction,
    recorded_next_action_authorization,
)
from foreman_valve_policy import CONFIG_KEY, CONSENSUS

__all__: list[str] = [
    "consensus_audit_record",
    "maintainer_decision_action_record",
    "maintainer_decision_audit_record",
    "prepare_maintainer_decision",
    "prepare_recorded_next_action",
]


def _refused(*, action_id: str | None, reason: str) -> ActResult:
    return {
        "action_id": action_id,
        "mutated": False,
        "outcome": "refused",
        "reason": reason,
    }


def consensus_audit_record(
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
        "authority": "panel",
    }


def maintainer_decision_audit_record(
    *,
    proposal: dict[str, object],
    maintainer_decision: dict[str, str],
    requested_action_id: ActionId,
    authorized_action_id: ActionId,
) -> dict[str, object]:
    return {
        "stage": "foreman-maintainer-decision",
        "action_id": requested_action_id,
        "governing_setting": f"{CONFIG_KEY}={CONSENSUS}",
        "repo": proposal.get("repo"),
        "topic": proposal.get("topic"),
        "authorized_action_id": authorized_action_id,
        "authorized_member_kind": "action",
        "authority": "maintainer",
        "maintainer_decision": maintainer_decision,
    }


def maintainer_decision_action_record(
    *,
    proposal: dict[str, object],
    authorized_action_id: ActionId,
) -> dict[str, object]:
    return {
        "stage": "blocked-session-answer",
        "action_id": authorized_action_id,
        "repo": proposal.get("repo"),
        "topic": proposal.get("topic"),
        "authorized_action_id": authorized_action_id,
        "authority": "maintainer",
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


def prepare_recorded_next_action(
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


def _maintainer_decision(
    *, action_id: ActionId, proposal: dict[str, object]
) -> tuple[dict[str, str] | None, ActResult | None]:
    if action_id != BLOCKED_SESSION_ANSWER:
        return None, None
    answer = jsonio.as_object(value=proposal.get("blocked_session_answer"))
    value = None if answer is None else answer.get("maintainer_decision")
    if value is None:
        return None, None
    decision = jsonio.as_object(value=value)
    fields = {
        "decided_by": None if decision is None else decision.get("decided_by"),
        "decided_at": None if decision is None else decision.get("decided_at"),
        "surface": None if decision is None else decision.get("surface"),
    }
    if not all(isinstance(field, str) and field != "" for field in fields.values()):
        return None, _refused(action_id=action_id, reason="maintainer_decision_malformed")
    return cast(dict[str, str], fields), None


def prepare_maintainer_decision(
    *, action_id: ActionId, proposal: dict[str, object], append_journal: AppendJournal
) -> tuple[ActionId | None, ActResult | None] | None:
    decision, refusal = _maintainer_decision(action_id=action_id, proposal=proposal)
    if refusal is not None:
        return None, refusal
    if decision is None:
        return None
    try:
        append_journal(
            repo=Path(str(proposal["repo"])),
            record=maintainer_decision_audit_record(
                proposal=proposal,
                maintainer_decision=decision,
                requested_action_id=action_id,
                authorized_action_id=action_id,
            ),
        )
        append_journal(
            repo=Path(str(proposal["repo"])),
            record=maintainer_decision_action_record(
                proposal=proposal,
                authorized_action_id=action_id,
            ),
        )
    except OSError:  # pragma: no cover
        return None, _refused(action_id=action_id, reason="journal_append_failed")
    return action_id, None
