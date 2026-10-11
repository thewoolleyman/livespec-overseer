"""Exact-instance Herdr workspace creation for deliberate initial start."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Protocol, cast

import bootstrap_journal
import herdr_identity
import herdr_protocol
import herdr_transport
import jsonio
import terminal_ownership

__all__: list[str] = [
    "InitialCreation",
    "create_initial_pane",
    "creation_claim",
]

_WORKSPACE_CREATE = "workspace.create"
_PANE_LIST = "pane.list"
_EXPECT_WORKSPACE = herdr_protocol.ReplyExpectation(
    result_type="workspace_created", required_fields=("root_pane",)
)
_EXPECT_PANES = herdr_protocol.ReplyExpectation(result_type="pane_list", required_fields=("panes",))


class _CreationRequests(Protocol):
    def request(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        method: str,
        params: Mapping[str, object],
        expect: herdr_protocol.ReplyExpectation,
    ) -> herdr_transport.RpcOutcome: ...


@dataclass(frozen=True, kw_only=True)
class InitialCreation:
    ok: bool
    target: str
    error: str
    effect_unknown: bool


def creation_claim(
    *, target: herdr_identity.HerdrPaneTarget, repo: str, topic: str
) -> terminal_ownership.OwnershipClaim:
    """Journal scope for one repo/topic creation on one server generation."""
    return terminal_ownership.OwnershipClaim(
        backend=herdr_identity.HERDR_BACKEND,
        socket_path=target.socket_path,
        server_pid=target.server_pid,
        server_starttime=target.server_starttime,
        pane_id=f"initial-create:{repo}::{topic}",
        pane_process_pid=0,
        distance=0,
    )


def _coordinate(*, target: herdr_identity.HerdrPaneTarget, pane_id: str) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=target.socket_path,
            server_pid=target.server_pid,
            server_starttime=target.server_starttime,
            pane_id=pane_id,
        )
    )


def _pane_identifier(*, row: object) -> str:
    value = (jsonio.as_object(value=row) or {}).get("pane_id")
    return value if isinstance(value, str) else ""


def _pane_ids(
    *, writer: _CreationRequests, target: herdr_identity.HerdrPaneTarget
) -> frozenset[str]:
    outcome = writer.request(
        target=target,
        method=_PANE_LIST,
        params={},
        expect=_EXPECT_PANES,
    )
    rows = jsonio.as_list(value=outcome.result.get("panes")) or []
    return frozenset(filter(None, (_pane_identifier(row=row) for row in rows)))


def create_initial_pane(
    *,
    writer: _CreationRequests,
    journal: bootstrap_journal.MutationJournal,
    source: str,
    name: str,
    cwd: str,
) -> InitialCreation:
    """Create once, retaining the real new coordinate across uncertain replies."""
    target = cast(
        herdr_identity.HerdrPaneTarget,
        herdr_identity.decode_herdr_target(value=source),
    )
    claim = creation_claim(target=target, repo=cwd, topic=name)
    before = _pane_ids(writer=writer, target=target)
    journal.prepare(claim=claim)
    outcome = writer.request(
        target=target,
        method=_WORKSPACE_CREATE,
        params={"cwd": cwd, "env": {}, "focus": False, "label": name},
        expect=_EXPECT_WORKSPACE,
    )
    after = _pane_ids(writer=writer, target=target)
    delta = after - before
    observed = {1: next(iter(delta), "")}.get(len(delta), "")
    root = jsonio.as_object(value=outcome.result.get("root_pane")) or {}
    acknowledged = root.get("pane_id") if isinstance(root.get("pane_id"), str) else ""
    created = cast(str, observed or acknowledged or target.pane_id)
    coordinate = _coordinate(target=target, pane_id=created)
    ok = outcome.ok & bool(observed) & (acknowledged == observed)
    uncertain = outcome.effect_unknown | (outcome.request_sent & (not ok))
    action: Callable[..., None] = {
        True: partial(journal.retain, pane_id=coordinate),
        False: journal.resolve,
    }[ok | uncertain]
    action(claim=claim)
    return InitialCreation(
        ok=ok,
        target=coordinate,
        error=outcome.error or "workspace.create did not return one freshly enumerated root pane",
        effect_unknown=uncertain,
    )
