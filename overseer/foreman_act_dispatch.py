"""Dispatch already-authorized foreman-act proposals to deterministic mechanics."""
# livespec-lloc-soft-band-owner: overseer-3h4s5w.6

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import tmuxio
from foreman_act_commands import command_for
from foreman_act_consensus import act_journal_triage
from foreman_act_dispatch_result import CommandResult, ReturncodeRunner, Runner, command_result
from foreman_act_filing import FileWorkItem, filing_request
from foreman_act_ledger import LedgerMutation, ledger_request
from foreman_act_record import AppendJournal
from foreman_act_revalidate import revalidate_identity, revalidate_start_identity, str_field
from foreman_act_types import (
    BLOCKED_SESSION_ANSWER,
    DISPATCH_JOURNAL_RECONCILE_MERGED,
    FOREMAN_EPIC_CREATE,
    PLAN_START,
    QUALIFYING_SESSION_RESUME,
    QUALIFYING_SESSION_START,
    SUPERVISOR_PAIR_START,
    WORK_ITEM_COMMENT,
    WORK_ITEM_FILE,
    WORK_ITEM_UPDATE,
    ActionId,
    ActResult,
)
from foreman_blocked_answer import act_blocked_session_answer
from foreman_start_intent import amend_start_intent, record_start_intent
from foreman_work_item_sessions import act_work_item_session, is_work_item_session_action

__all__: list[str] = ["CommandResult", "DispatchSeams", "Runner", "act_authorized"]

_START_ACTIONS: tuple[ActionId, ...] = (PLAN_START, QUALIFYING_SESSION_START, SUPERVISOR_PAIR_START)


@dataclass(frozen=True, kw_only=True)
class DispatchSeams:
    run: Runner
    file_work_item: FileWorkItem
    ledger_mutation: LedgerMutation
    append_journal: AppendJournal


def _result(*, action_id: str | None, outcome: str, reason: str, mutated: bool) -> ActResult:
    result: ActResult = {
        "action_id": action_id,
        "mutated": mutated,
        "outcome": outcome,
        "reason": reason,
    }
    return result


def _refused(*, action_id: str | None, reason: str) -> ActResult:
    return _result(action_id=action_id, outcome="refused", reason=reason, mutated=False)


def _acted(*, action_id: str, reason: str) -> ActResult:
    return _result(action_id=action_id, outcome="acted", reason=reason, mutated=True)


def _failed(*, action_id: str, reason: str) -> ActResult:
    return _result(action_id=action_id, outcome="failed", reason=reason, mutated=False)


def _bounded_reason(*, prefix: str, reason: str, limit: int = 180) -> str:
    if reason.startswith("Traceback (most recent call last):") and len(reason) > limit:
        return _bounded_traceback_reason(prefix=prefix, reason=reason, limit=limit)
    bounded = f"{prefix}:{reason}"
    if len(bounded) <= limit:
        return bounded
    return bounded[: limit - 3] + "..."


def _bounded_traceback_reason(*, prefix: str, reason: str, limit: int) -> str:
    header = f"{prefix}:Traceback (most recent call last):"
    separator = "\n..."
    available = limit - len(header) - len(separator)
    if available <= 0:  # pragma: no cover
        return header[: limit - 3] + "..."
    return f"{header}{separator}{reason[-available:]}"


def _supervisor_start_failure_reason(*, stderr: str) -> str | None:
    match = re.search(r"\breason=([A-Za-z0-9_.:-]+)", stderr)
    if match is None:
        return None
    return match.group(1)


def _revalidate_start_tmux_occupancy(
    *, action_id: ActionId, proposal: dict[str, object]
) -> str | None:
    if action_id not in _START_ACTIONS:
        return None
    session_name = str_field(payload=proposal, key="session_name")
    if session_name is None:  # pragma: no cover
        return "malformed_proposal"
    if tmuxio.TmuxIO().session_exists(session=session_name):  # pragma: no cover
        return "tmux_session_occupied"
    return None


def _act_filing(
    *,
    proposal: dict[str, object],
    action_id: ActionId,
    file_work_item: FileWorkItem,
    append_journal: AppendJournal,
) -> ActResult:
    request = filing_request(proposal=proposal)
    if request is None:
        return _refused(action_id=action_id, reason="malformed_filing")
    try:
        append_journal(
            repo=Path(str(proposal["repo"])),
            record={
                "stage": "foreman-act",
                "action_id": action_id,
                "outcome": "pending",
                "reason": "work_item_file_pending",
                "mutated": False,
            },
        )
    except OSError:
        return _refused(action_id=action_id, reason="journal_append_failed")
    try:
        filed = file_work_item(request=request)
    except (RuntimeError, ValueError) as exc:
        return _failed(
            action_id=action_id,
            reason=_bounded_reason(prefix="filing_subprocess_failed", reason=str(exc)),
        )
    item_id = filed[0]
    verdict = filed[1]
    root_suffix = ":".join(("", *filed[2:]))
    return _acted(action_id=action_id, reason=f"filed:{item_id}:{verdict}{root_suffix}")


def _is_ledger_mutation(*, action_id: ActionId) -> bool:
    return action_id in (FOREMAN_EPIC_CREATE, WORK_ITEM_COMMENT, WORK_ITEM_UPDATE)


def _act_ledger_mutation(
    *,
    proposal: dict[str, object],
    action_id: ActionId,
    ledger_mutation: LedgerMutation,
    append_journal: AppendJournal,
    run: Runner,
) -> ActResult:
    refusal, request = ledger_request(proposal=proposal, action_id=action_id)
    if refusal is not None or request is None:
        return _refused(action_id=action_id, reason=refusal or "malformed_ledger_mutation")
    try:
        append_journal(
            repo=Path(str(request["repo"])),
            record={
                "stage": "foreman-act",
                "action_id": action_id,
                "outcome": "pending",
                "reason": "ledger_mutation_pending",
                "mutated": False,
            },
        )
    except OSError:  # pragma: no cover
        return _refused(action_id=action_id, reason="journal_append_failed")
    try:
        item_id, verdict = ledger_mutation(request=request, run=run)
    except RuntimeError as exc:  # pragma: no cover
        return _failed(
            action_id=action_id,
            reason=_bounded_reason(prefix="ledger_subprocess_failed", reason=str(exc)),
        )
    return _acted(action_id=action_id, reason=f"ledger_updated:{item_id}:{verdict}")


def _act_command(*, action_id: ActionId, proposal: dict[str, object], run: Runner) -> ActResult:
    command = command_for(action_id=action_id, proposal=proposal)
    if command is None:  # pragma: no cover
        result = _refused(action_id=action_id, reason="classifier_mismatch")
    else:
        result = command_result(raw=run(argv=command))
        code = result.returncode
        failed_reason = (
            _supervisor_start_failure_reason(stderr=result.stderr)
            if action_id in _START_ACTIONS
            else None
        )
        result = (
            _acted(
                action_id=action_id,
                reason="resumed" if action_id == QUALIFYING_SESSION_RESUME else "started",
            )
            if code == 0
            else _failed(action_id=action_id, reason=failed_reason or f"command_exit_{code}")
        )
    return result


def _act_start_command(
    *, action_id: ActionId, proposal: dict[str, object], repo: str, run: Runner
) -> ActResult:
    """Record the start-intent BEFORE the spawn, spawn, then reconcile the record.

    The ordering is the obligation, not an implementation detail: a surface that
    does not survive its own spawn writes nothing afterwards, so the record has
    to precede the act it describes. An intent that cannot be persisted refuses
    the spawn rather than proceeding unrecorded.

    Reaching the amendment at all proves the surface SURVIVED, which is what
    makes the two failure cases distinguishable: a spawn that failed and resolved
    carries its error, and one that never returned leaves the record as it was.
    """
    if action_id not in _START_ACTIONS:
        return _act_command(action_id=action_id, proposal=proposal, run=run)
    target = str(proposal.get("topic", ""))
    if not record_start_intent(
        repo=Path(repo), action_id=action_id, target=target, proposal=proposal
    ):
        return _refused(action_id=action_id, reason="start_intent_write_failed")
    result = _act_command(action_id=action_id, proposal=proposal, run=run)
    error = None if result["outcome"] == "acted" else str(result["reason"])
    amend_start_intent(repo=Path(repo), action_id=action_id, target=target, error=error)
    return result


def act_authorized(
    *,
    action_id: ActionId,
    proposal: dict[str, object],
    document: dict[str, object],
    repo: str,
    seams: DispatchSeams,
) -> ActResult:
    if is_work_item_session_action(action_id=action_id):
        returncode_runner = ReturncodeRunner(run=seams.run)
        result = act_work_item_session(
            action_id=action_id,
            proposal=proposal,
            document=document,
            run=returncode_runner,
        )
    elif (
        identity_refusal := revalidate_start_identity(proposal=proposal, document=document)
        if action_id in _START_ACTIONS
        else revalidate_identity(proposal=proposal, document=document)
    ) is not None:
        result = _refused(action_id=action_id, reason=identity_refusal)
    elif (
        start_refusal := _revalidate_start_tmux_occupancy(action_id=action_id, proposal=proposal)
    ) is not None:
        result = _refused(action_id=action_id, reason=start_refusal)
    elif action_id == BLOCKED_SESSION_ANSWER:
        result = act_blocked_session_answer(
            proposal=proposal,
            document=document,
            repo=repo,
            append_journal=seams.append_journal,
        )
    elif action_id == WORK_ITEM_FILE:
        result = _act_filing(
            proposal=proposal,
            action_id=action_id,
            file_work_item=seams.file_work_item,
            append_journal=seams.append_journal,
        )
    elif _is_ledger_mutation(action_id=action_id):
        result = _act_ledger_mutation(
            proposal=proposal,
            action_id=action_id,
            ledger_mutation=seams.ledger_mutation,
            append_journal=seams.append_journal,
            run=seams.run,
        )
    elif action_id == DISPATCH_JOURNAL_RECONCILE_MERGED:  # pragma: no cover
        returncode_runner = ReturncodeRunner(run=seams.run)
        result = act_journal_triage(
            action_id=action_id,
            proposal=proposal,
            document=document,
            repo=repo,
            run=returncode_runner,
        )
    else:
        result = _act_start_command(
            action_id=action_id, proposal=proposal, repo=repo, run=seams.run
        )
    return result
