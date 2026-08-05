"""Deterministic Phase B foreman lifecycle actuator."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import foreman_act_dispatch
import jsonio
import streams
import tmuxio
from _supervisor_snapshot import DEFAULT_STATUS_PATH
from foreman_act_consensus import (
    ConsensusPanel,
    prepare_consensus_action,
)
from foreman_act_dispatch import Runner
from foreman_act_filing import FileWorkItem, file_work_item
from foreman_act_record import AppendJournal, append_journal
from foreman_act_revalidate import (
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
from foreman_consensus import consensus
from foreman_gather_collect import compose_document
from foreman_valve_policy import effective_valve_disposition

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
    consensus_panel: ConsensusPanel = consensus,
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
                document=gather(repo=repo, snapshot_path=DEFAULT_STATUS_PATH),
                run=run,
                file_work_item=file_work_item,
                consensus_seams=(append_journal, consensus_panel),
            )
    repo_path = str_field(payload=proposal, key="repo")
    if repo_path is not None and result["reason"] != "journal_append_failed":  # pragma: no branch
        append_journal(repo=Path(repo_path), record=_journal_record(result=result))
    return result


def _act_validated(
    *,
    action_id: ActionId,
    proposal: dict[str, object],
    document: dict[str, object],
    run: Runner,
    file_work_item: FileWorkItem,
    consensus_seams: tuple[AppendJournal, ConsensusPanel],
) -> ActResult:
    repo = str_field(payload=proposal, key="repo") or ""
    append_journal, consensus_panel = consensus_seams
    refusal = revalidate_source(document=document)
    if refusal is not None:
        result = _refused(action_id=action_id, reason=refusal)
    elif action_id in (BLOCKED_SESSION_ANSWER, HUMAN_VALVE):
        authorized, valve_refusal = prepare_consensus_action(
            proposal=proposal,
            disposition=effective_valve_disposition(repo=Path(repo)),
            consensus_panel=consensus_panel,
            append_journal=append_journal,
        )
        if valve_refusal is not None or authorized is None:
            result = valve_refusal or _refused(action_id=action_id, reason="consensus_unavailable")
        else:
            foreman_act_dispatch.tmuxio = tmuxio
            result = foreman_act_dispatch.act_authorized(
                action_id=authorized,
                proposal=proposal,
                document=document,
                repo=repo,
                run=run,
                file_work_item=file_work_item,
            )
    else:
        foreman_act_dispatch.tmuxio = tmuxio
        result = foreman_act_dispatch.act_authorized(
            action_id=action_id,
            proposal=proposal,
            document=document,
            repo=repo,
            run=run,
            file_work_item=file_work_item,
        )
    return result


def run_command(*, argv: list[str]) -> int:
    completed = subprocess.run(  # noqa: S603  # pragma: no cover
        argv, check=False, stdout=subprocess.DEVNULL
    )
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

    def cli_gather(
        *, repo: str | Path, snapshot_path: str | Path = DEFAULT_STATUS_PATH
    ) -> dict[str, object]:
        _ = snapshot_path
        return compose_document(repo=repo, snapshot_path=args.snapshot_path)

    result = (
        _refused(action_id=None, reason="malformed_proposal")  # pragma: no cover
        if proposal is None
        else act(proposal=proposal, run=run_command, gather=cli_gather)
    )
    streams.write_stdout(text=json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
