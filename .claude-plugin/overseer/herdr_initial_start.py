"""Exact Herdr workspace creation and initial retained-shell launch."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import partial
from typing import Protocol, cast

import _herdr_layout_proofs
import _herdr_shell_identity
import bootstrap_journal
import herdr_identity
import herdr_initial_creation
import herdr_protocol
import herdr_transport
import herdr_write_calls
import terminal_ownership
import tmuxio_env

__all__: list[str] = [
    "HerdrInitialStart",
    "InitialMutation",
    "ShellIdentity",
]

ShellIdentity = _herdr_shell_identity.ShellIdentity


class NativeRequests(Protocol):
    def request(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        method: str,
        params: Mapping[str, object],
        expect: herdr_protocol.ReplyExpectation,
    ) -> herdr_transport.RpcOutcome: ...


@dataclass(frozen=True, kw_only=True)
class InitialMutation:
    ok: bool
    target: str
    error: str
    effect_unknown: bool


def _scope_claim(
    *, target: herdr_identity.HerdrPaneTarget, pane_id: str
) -> terminal_ownership.OwnershipClaim:
    return terminal_ownership.OwnershipClaim(
        backend=herdr_identity.HERDR_BACKEND,
        socket_path=target.socket_path,
        server_pid=target.server_pid,
        server_starttime=target.server_starttime,
        pane_id=pane_id,
        pane_process_pid=0,
        distance=0,
    )


@dataclass(kw_only=True)
class HerdrInitialStart:
    """One no-replay native start surface bound to durable exact-instance intents."""

    writer: NativeRequests
    journal: bootstrap_journal.MutationJournal = field(
        default_factory=bootstrap_journal.BootstrapMutationJournal
    )
    shell_evidence_of: _herdr_shell_identity.ShellEvidence = (
        _herdr_shell_identity.proc_shell_identity
    )
    login_shells: frozenset[str] = field(default_factory=_herdr_shell_identity.system_login_shells)
    shell_aliases: frozenset[tuple[str, str]] = field(
        default_factory=_herdr_shell_identity.system_shell_aliases
    )

    def _target(self, *, value: str) -> herdr_identity.HerdrPaneTarget:
        return cast(
            herdr_identity.HerdrPaneTarget,
            herdr_identity.decode_herdr_target(value=value),
        )

    def _creation_claim(
        self, *, target: herdr_identity.HerdrPaneTarget, repo: str, topic: str
    ) -> terminal_ownership.OwnershipClaim:
        return herdr_initial_creation.creation_claim(target=target, repo=repo, topic=topic)

    def _launch_claim(
        self, *, target: herdr_identity.HerdrPaneTarget, repo: str
    ) -> terminal_ownership.OwnershipClaim:
        return _scope_claim(target=target, pane_id=f"initial-launch:{repo}::{target.pane_id}")

    def pending_initial_start(self, *, repo: str, topic: str, session: str) -> str:
        target = self._target(value=session)
        creation = self.journal.pending_error(
            claim=self._creation_claim(target=target, repo=repo, topic=topic)
        )
        launch = self.journal.pending_error(claim=self._launch_claim(target=target, repo=repo))
        pending = creation or launch
        return f"target={session}: {pending}" if pending else ""

    def create_initial_pane(
        self, *, source: str, name: str, cwd: str
    ) -> herdr_initial_creation.InitialCreation:
        return herdr_initial_creation.create_initial_pane(
            writer=self.writer,
            journal=self.journal,
            source=source,
            name=name,
            cwd=cwd,
        )

    def created_initial_pane_persisted(self, *, repo: str, topic: str, session: str) -> None:
        target = self._target(value=session)
        self.journal.resolve(claim=self._creation_claim(target=target, repo=repo, topic=topic))

    @staticmethod
    def _send_launch(
        *,
        writer: NativeRequests,
        target: herdr_identity.HerdrPaneTarget,
        command: str,
    ) -> herdr_transport.RpcOutcome:
        return writer.request(
            target=target,
            method=herdr_write_calls.PASTE_METHOD,
            params=herdr_write_calls.launch_params(pane_id=target.pane_id, command=command),
            expect=herdr_write_calls.EXPECT_OK,
        )

    def launch_initial_agent(
        self,
        *,
        session: str,
        cwd: str,
        command: str,
        env: object,
        expected_process: str,
    ) -> InitialMutation:
        del expected_process
        target = self._target(value=session)
        claim = self._launch_claim(target=target, repo=cwd)
        self.journal.prepare(claim=claim)
        proof = _herdr_shell_identity.ShellProof(
            evidence_of=self.shell_evidence_of,
            login_shells=self.login_shells,
            shell_aliases=self.shell_aliases,
        )
        first = _herdr_layout_proofs.retained_shell(
            requester=self.writer,
            target=target,
            created=target.pane_id,
            expected=None,
            proof=proof,
        )
        second = _herdr_layout_proofs.retained_shell(
            requester=self.writer,
            target=target,
            created=target.pane_id,
            expected=first.identity,
            proof=proof,
        )
        authorized = (first.identity is not None) & (second.identity == first.identity)
        rendered = tmuxio_env.with_env_delta(
            command=command,
            env=cast(Mapping[str, str | None] | None, env),
        )
        requests = itertools.compress((rendered,), (authorized,))
        outcomes = tuple(
            self._send_launch(writer=self.writer, target=target, command=request)
            for request in requests
        )
        refusal = herdr_transport.RpcOutcome(
            ok=False,
            result={},
            error=first.error or second.error,
            peer=None,
            timed_out=False,
            request_sent=False,
        )
        outcome = (*outcomes, refusal)[0]
        keep = outcome.ok | outcome.effect_unknown
        action: Callable[..., None] = {
            True: partial(self.journal.retain, pane_id=session),
            False: self.journal.resolve,
        }[keep]
        action(claim=claim)
        return InitialMutation(
            ok=outcome.ok,
            target=session,
            error=outcome.error,
            effect_unknown=outcome.effect_unknown,
        )

    def finish_initial_agent(self, *, repo: str, session: str, unresolved: bool) -> None:
        target = self._target(value=session)
        claim = self._launch_claim(target=target, repo=repo)
        action: Callable[..., None] = {
            True: partial(self.journal.retain, pane_id=session),
            False: self.journal.resolve,
        }[unresolved]
        action(claim=claim)

    def preserve_initial_pane(self, *, session: str) -> bool:
        del session
        return False

    cleanup_initial_pane = preserve_initial_pane
