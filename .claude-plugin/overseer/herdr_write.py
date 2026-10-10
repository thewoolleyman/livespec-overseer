"""herdr_write.py — the native herdr WRITE surface, addressed exactly.

The daemon's two acts on a terminal it supervises — deliver a payload, then
submit it — performed over the herdr socket API. :mod:`herdr_write_calls` shapes
each call and names each reply (pure); :mod:`herdr_transport` owns the socket,
the deadline and the peer validation; this module is the thin layer that turns a
BACKEND-QUALIFIED coordinate into the right bounded request.

**Opt-in by explicit construction, and unused by production defaults.** Nothing
in the supervision loop reaches this module: backend selection, mapping-store
rewrites and `overseer-start` activation are a separate slice, deliberately, so
an incomplete backend is never silently activated. Constructing a
:class:`HerdrWriter` is the only way to reach it.

**Delivery and SUBMISSION are separate operations, and that separation is the
whole design.** `SPECIFICATION/constraints.md` requires the two supported
backends to preserve the same supervision guarantees, and the tmux backend's
guarantee is that a multi-line payload arrives as one atomic paste which the
daemon then OBSERVES before sending Enter. An atomic paste-and-submit call
exists in herdr (`keys: ["Enter"]` alongside the text) and is deliberately NOT
offered here: it would collapse the observe step, and the observe step is what
keeps the daemon from submitting a payload that landed wrong.

**A write is a MUTATION, so its failure mode is uncertainty rather than simple
refusal.** Every outcome therefore carries `effect_unknown`, taken from the
transport's single write-boundary rule rather than recomputed here: a request
that reached the server and went unanswered MAY have taken effect, and
`SPECIFICATION/contracts.md` forbids resubmitting past that boundary. Nothing in
this module retries, and no caller should read an uncertain outcome as a licence
to repeat the call — re-OBSERVE the pane instead.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Protocol

import _herdr_shell_identity
import claude_sessions
import herdr_identity
import herdr_layout
import herdr_protocol
import herdr_transport
import herdr_write_calls
from _seams import PidToOptionalStr

__all__: list[str] = [
    "DEFAULT_TOP_RATIO",
    "BootstrapWriter",
    "HerdrWriter",
    "LayoutOutcome",
    "WriteOutcome",
]

# Re-exported so a caller holding a writer needs only this module, exactly as
# `registry` and `supervisor` re-export their own collaborators here.
DEFAULT_TOP_RATIO = herdr_layout.DEFAULT_TOP_RATIO
LayoutOutcome = herdr_layout.LayoutOutcome


class BootstrapWriter(Protocol):
    """The exact-generation Herdr mutation surface public bootstrap requires."""

    def request(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        method: str,
        params: Mapping[str, object],
        expect: herdr_protocol.ReplyExpectation,
    ) -> herdr_transport.RpcOutcome: ...

    def split_window_top(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        cwd: str,
        command: str,
        ratio: float = herdr_layout.DEFAULT_TOP_RATIO,
    ) -> herdr_layout.LayoutOutcome: ...


def _default_request_ids() -> Iterator[str]:
    return (f"overseer-w-{index}" for index in range(1, 1 << 62))


@dataclass(frozen=True, kw_only=True)
class WriteOutcome:
    """One mutation's result, or a named fail-closed refusal.

    `effect_unknown` distinguishes the two failures a caller must treat
    differently: a write REFUSED before the request crossed the socket changed
    nothing and is safe to reconsider, while a write whose request was sent and
    went unanswered may already have landed. Only the first is replayable, and
    neither is retried here.
    """

    ok: bool
    error: str
    effect_unknown: bool


@dataclass(frozen=True, kw_only=True)
class HerdrWriter:
    """The write surface for herdr panes, one bounded request per call.

    The injectable fields mirror :class:`herdr_adapter.HerdrAdapter`'s and exist
    for the same reasons: `starttime_of` and `monotonic` let a test drive an
    unreadable generation or an expired deadline deterministically,
    `expected_uid` lets the "another user's socket is not this track's backend"
    guard be asserted, and `request_ids` lets a test assert the exact bytes on
    the wire. The daemon always takes its own uid.
    """

    timeout_seconds: float = herdr_transport.DEFAULT_TIMEOUT_SECONDS
    max_reply_bytes: int = herdr_protocol.MAX_REPLY_BYTES
    expected_uid: int = field(default_factory=os.getuid)
    request_ids: Iterator[str] = field(default_factory=_default_request_ids)
    starttime_of: PidToOptionalStr = claude_sessions.proc_starttime
    monotonic: Callable[[], float] = time.monotonic
    # The retained-shell proof's kernel half. Injectable for the same reason
    # `starttime_of` is: a deterministic test must be able to drive an
    # exec-replaced root, an unreadable `/proc`, and a host whose registered
    # login shells differ from this one's, none of which can be staged against
    # real host state. The daemon takes the real readers.
    shell_evidence_of: _herdr_shell_identity.ShellEvidence = (
        _herdr_shell_identity.proc_shell_identity
    )
    login_shells: frozenset[str] = field(default_factory=_herdr_shell_identity.system_login_shells)
    # The names this host registers its login shells UNDER, which is what lets a
    # pane reporting `sh` be recognised as the `/usr/bin/dash` the kernel shows.
    # Injectable alongside `login_shells` so a test can drive a host that
    # registers a name for a different binary, or registers nothing at all.
    shell_aliases: frozenset[tuple[str, str]] = field(
        default_factory=_herdr_shell_identity.system_shell_aliases
    )

    def bracketed_paste(self, *, target: herdr_identity.HerdrPaneTarget, text: str) -> WriteOutcome:
        """Deliver `text` to `target` as ONE bracketed paste, submitting nothing.

        The payload is left sitting in the pane unexecuted on purpose; see the
        module docstring for why submission is a separate call.
        """
        return self._write(
            target=target,
            params=herdr_write_calls.paste_params(pane_id=target.pane_id, text=text),
        )

    def send_enter(self, *, target: herdr_identity.HerdrPaneTarget) -> WriteOutcome:
        """Submit whatever `target` currently holds, delivering no new text."""
        return self._write(
            target=target,
            params=herdr_write_calls.enter_params(pane_id=target.pane_id),
        )

    def split_window_top(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        cwd: str,
        command: str,
        ratio: float = herdr_layout.DEFAULT_TOP_RATIO,
    ) -> herdr_layout.LayoutOutcome:
        """Run `command` in a new retained-shell pane placed ABOVE `target`.

        The sequence and every proof it requires before writing live in
        :mod:`herdr_layout`; this writer supplies the bounded, peer-validated
        request path it runs on.
        """
        return herdr_layout.place_above(
            requester=self,
            target=target,
            cwd=cwd,
            command=command,
            proof=_herdr_shell_identity.ShellProof(
                evidence_of=self.shell_evidence_of,
                login_shells=self.login_shells,
                shell_aliases=self.shell_aliases,
            ),
            ratio=ratio,
        )

    def _write(
        self, *, target: herdr_identity.HerdrPaneTarget, params: Mapping[str, object]
    ) -> WriteOutcome:
        """One bounded input mutation, reduced to the three facts a caller needs."""
        outcome = self.request(
            target=target,
            method=herdr_write_calls.PASTE_METHOD,
            params=params,
            expect=herdr_write_calls.EXPECT_OK,
        )
        return WriteOutcome(
            ok=outcome.ok,
            error=outcome.error,
            effect_unknown=outcome.effect_unknown,
        )

    def request(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        method: str,
        params: Mapping[str, object],
        expect: herdr_protocol.ReplyExpectation,
    ) -> herdr_transport.RpcOutcome:
        """One bounded mutation against the generation `target` names, or why not.

        PUBLIC because :mod:`herdr_layout` runs its whole sequence on it through
        :class:`herdr_layout.BoundedRequests`; a cross-module private call would
        be rejected by pyright-strict and by this repo's own checks, and the
        honest alternative to a private reach is a named interface.

        The expected peer is derived from the TARGET on every call rather than
        remembered from an earlier identification, so a coordinate whose server
        generation has been replaced writes NOTHING rather than reaching
        whichever server now answers on that path. In a multi-step layout
        change that revalidation happens again before EVERY step, so a server
        replaced midway cannot receive the remainder of the sequence.
        """
        return herdr_transport.HerdrTransport(
            socket_path=target.socket_path,
            expected_peer=herdr_transport.PeerIdentity(
                pid=target.server_pid,
                uid=self.expected_uid,
                starttime=target.server_starttime,
            ),
            timeout_seconds=self.timeout_seconds,
            max_reply_bytes=self.max_reply_bytes,
            starttime_of=self.starttime_of,
            monotonic=self.monotonic,
        ).request(request_id=next(self.request_ids), method=method, params=params, expect=expect)
