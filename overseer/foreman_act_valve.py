"""Human-valve consensus branch for validated foreman-act proposals."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import foreman_act_dispatch
import tmuxio
from foreman_act_consensus import ConsensusPanel, prepare_consensus_action
from foreman_act_dispatch import DispatchSeams
from foreman_act_record import AppendJournal
from foreman_act_types import ActionId, ActResult
from foreman_typed_ruling import act_typed_ruling
from foreman_valve_policy import effective_valve_disposition

__all__: list[str] = ["act_with_human_valve"]


def act_with_human_valve(
    *,
    action_id: ActionId,
    proposal: dict[str, object],
    document: dict[str, object],
    repo: str,
    seams: DispatchSeams,
    consensus_seams: tuple[AppendJournal, ConsensusPanel],
) -> ActResult:
    append_journal, consensus_panel = consensus_seams
    authorized, valve_refusal = prepare_consensus_action(
        action_id=action_id,
        proposal=proposal,
        disposition=effective_valve_disposition(repo=Path(repo)),
        consensus_panel=consensus_panel,
        append_journal=append_journal,
    )
    if valve_refusal is not None:
        return valve_refusal
    if isinstance(authorized, dict):
        return act_typed_ruling(ruling=authorized, proposal=proposal, document=document, repo=repo)
    authorized_action_id = cast(ActionId, authorized)
    foreman_act_dispatch.tmuxio = tmuxio
    return foreman_act_dispatch.act_authorized(
        action_id=authorized_action_id,
        proposal=proposal,
        document=document,
        repo=repo,
        seams=seams,
    )
