"""Deterministic Phase B foreman lifecycle actuator."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import jsonio
import streams
from _supervisor_snapshot import DEFAULT_STATUS_PATH
from foreman_act_commands import command_for
from foreman_act_filing import FileWorkItem, file_work_item, filing_request
from foreman_act_journal import journal_reconcile_command
from foreman_act_record import AppendJournal, append_journal
from foreman_act_revalidate import (
    revalidate_identity,
    revalidate_source,
    str_field,
    validate_proposal,
)
from foreman_act_types import (
    ACTION_IDS,
    BLOCKED_SESSION_ANSWER,
    DISPATCH_JOURNAL_RECONCILE_MERGED,
    HUMAN_VALVE,
    PROPOSAL_SCHEMA_VERSION,
    QUALIFYING_SESSION_RESUME,
    WORK_ITEM_FILE,
    WORK_ITEM_SESSION_ACTIONS,
    WORK_ITEM_SESSION_FINISH,
    WORK_ITEM_SESSION_RESUME,
    WORK_ITEM_SESSION_START,
    ActionId,
    ActResult,
)
from foreman_gather_collect import compose_document
from foreman_work_item_sessions import act_work_item_session, is_work_item_session_action

__all__: list[str] = [
    "ACTION_IDS",
    "BLOCKED_SESSION_ANSWER",
    "DISPATCH_JOURNAL_RECONCILE_MERGED",
    "HUMAN_VALVE",
    "PROPOSAL_SCHEMA_VERSION",
    "QUALIFYING_SESSION_RESUME",
    "WORK_ITEM_FILE",
    "WORK_ITEM_SESSION_ACTIONS",
    "WORK_ITEM_SESSION_FINISH",
    "WORK_ITEM_SESSION_RESUME",
    "WORK_ITEM_SESSION_START",
    "ActResult",
    "ActionId",
    "act",
    "main",
    "run_command",
]


class Gatherer(Protocol):
    def __call__(
        self, *, repo: str | Path, snapshot_path: str | Path = DEFAULT_STATUS_PATH
    ) -> dict[str, object]: ...


class Runner(Protocol):
    def __call__(self, *, argv: list[str]) -> int: ...


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
    bounded = f"{prefix}:{reason}"
    if len(bounded) <= limit:
        return bounded
    return bounded[: limit - 3] + "..."


def _journal_record(*, result: ActResult) -> dict[str, object]:
    return {
        "stage": "foreman-act",
        "action_id": result["action_id"],
        "outcome": result["outcome"],
        "reason": result["reason"],
        "mutated": result["mutated"],
    }


def act(
    *,
    proposal: dict[str, object],
    run: Runner,
    gather: Gatherer = compose_document,
    file_work_item: FileWorkItem = file_work_item,
    append_journal: AppendJournal = append_journal,
    snapshot_path: str | Path = DEFAULT_STATUS_PATH,
) -> ActResult:
    action_id, refusal = validate_proposal(proposal=proposal)
    if refusal is not None:
        result = _refused(action_id=action_id, reason=refusal)
    elif action_id is None or action_id not in ACTION_IDS:  # pragma: no cover
        result = _refused(action_id=action_id, reason="unknown_action")
    else:
        repo = str_field(payload=proposal, key="repo")
        if repo is None:  # pragma: no cover
            result = _refused(action_id=action_id, reason="malformed_proposal")
        else:
            result = _act_validated(
                action_id=action_id,
                proposal=proposal,
                repo=repo,
                document=gather(repo=repo, snapshot_path=snapshot_path),
                run=run,
                file_work_item=file_work_item,
            )
    repo_path = str_field(payload=proposal, key="repo")
    if repo_path is not None:  # pragma: no branch
        append_journal(repo=Path(repo_path), record=_journal_record(result=result))
    return result


def _act_validated(
    *,
    action_id: ActionId,
    proposal: dict[str, object],
    repo: str,
    document: dict[str, object],
    run: Runner,
    file_work_item: FileWorkItem,
) -> ActResult:
    refusal = revalidate_source(document=document)
    if refusal is not None:
        result = _refused(action_id=action_id, reason=refusal)
    elif is_work_item_session_action(action_id=action_id):
        result = act_work_item_session(
            action_id=action_id, proposal=proposal, document=document, run=run
        )
    elif (
        identity_refusal := revalidate_identity(proposal=proposal, document=document)
    ) is not None:
        result = _refused(action_id=action_id, reason=identity_refusal)
    elif action_id == WORK_ITEM_FILE:
        result = _act_filing(proposal=proposal, action_id=action_id, file_work_item=file_work_item)
    elif action_id == DISPATCH_JOURNAL_RECONCILE_MERGED:
        result = _act_journal_triage(
            action_id=action_id, proposal=proposal, document=document, repo=repo, run=run
        )
    else:
        result = _act_command(action_id=action_id, proposal=proposal, run=run)
    return result


def _act_filing(
    *, proposal: dict[str, object], action_id: ActionId, file_work_item: FileWorkItem
) -> ActResult:
    request = filing_request(proposal=proposal)
    if request is None:
        return _refused(action_id=action_id, reason="malformed_filing")
    try:
        item_id, verdict = file_work_item(request=request)
    except RuntimeError as exc:
        return _failed(
            action_id=action_id,
            reason=_bounded_reason(prefix="filing_subprocess_failed", reason=str(exc)),
        )
    return _acted(action_id=action_id, reason=f"filed:{item_id}:{verdict}")


def _act_journal_triage(
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


def _act_command(*, action_id: ActionId, proposal: dict[str, object], run: Runner) -> ActResult:
    command = command_for(action_id=action_id, proposal=proposal)
    if command is None:  # pragma: no cover
        result = _refused(action_id=action_id, reason="classifier_mismatch")
    else:
        code = run(argv=command)
        result = (
            _acted(
                action_id=action_id,
                reason="resumed" if action_id == QUALIFYING_SESSION_RESUME else "started",
            )
            if code == 0
            else _failed(action_id=action_id, reason=f"command_exit_{code}")
        )
    return result


def run_command(*, argv: list[str]) -> int:
    completed = subprocess.run(argv, check=False)  # noqa: S603  # pragma: no cover
    return int(completed.returncode)  # pragma: no cover


def _load_proposal(*, path: Path) -> dict[str, object] | None:
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    return parsed


def main(*, argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="foreman-act")
    _ = parser.add_argument("--proposal", required=True)
    _ = parser.add_argument("--snapshot-path", default=str(DEFAULT_STATUS_PATH))
    args = parser.parse_args(argv)
    proposal = _load_proposal(path=Path(args.proposal))
    result = (
        _refused(action_id=None, reason="malformed_proposal")  # pragma: no cover
        if proposal is None
        else act(
            proposal=proposal,
            run=run_command,
            gather=compose_document,
            snapshot_path=args.snapshot_path,
        )
    )
    streams.write_stdout(text=json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
