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

import claude_sessions
import herdr_identity
import herdr_protocol
import herdr_transport
import herdr_write_calls
from _seams import PidToOptionalStr

__all__: list[str] = [
    "DEFAULT_TOP_RATIO",
    "HerdrWriter",
    "LayoutOutcome",
    "WriteOutcome",
]

# The share of the column the new TOP pane takes by default, matching
# `overseer-start`'s tmux-side `_DAEMON_PANE_HEIGHT_PERCENT` intent: the daemon
# pane carries the table plus the NEEDS YOU block, the supervised pane is a
# prompt. Callers that want a different split pass `ratio`.
DEFAULT_TOP_RATIO = 0.66


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
class LayoutOutcome:
    """A layout mutation's result, naming the pane it created when it got that far.

    `pane_id` is reported even on a FAILED outcome whenever the split itself
    succeeded, because a partially-applied layout is exactly the state a caller
    has to re-observe: the pane exists, and the step that failed afterwards did
    not un-create it. An empty `pane_id` means no pane was made.
    """

    ok: bool
    pane_id: str
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
        ratio: float = DEFAULT_TOP_RATIO,
    ) -> LayoutOutcome:
        """Run `command` in a new retained-shell pane placed ABOVE `target`.

        Three bounded mutations in sequence — split downward, swap the two
        positions, launch into the new pane's own shell — because herdr splits
        only right and down, so "above" has no single call. `target` keeps its
        pane id, its shell and its focus throughout; the swap moves rectangles,
        not identities.

        **No step is retried, and a failure after the split still names the new
        pane.** Each stage is its own write boundary, so a stage that was sent
        and went unanswered leaves `effect_unknown` set and the layout in a
        state only re-observation can resolve. Repeating a swap that may have
        landed would undo it, and repeating a launch would run the command
        twice; `SPECIFICATION/contracts.md` forbids resubmitting past that
        boundary and this method does not.
        """
        split = self._request(
            target=target,
            method=herdr_write_calls.SPLIT_METHOD,
            params=herdr_write_calls.split_down_params(
                pane_id=target.pane_id, cwd=cwd, ratio=ratio
            ),
            expect=herdr_write_calls.EXPECT_PANE_INFO,
        )
        if not split.ok:
            return LayoutOutcome(
                ok=False, pane_id="", error=split.error, effect_unknown=split.effect_unknown
            )
        created = herdr_write_calls.new_pane_id(result=split.result)
        if created is None:
            # The split was ACKNOWLEDGED, so a pane probably exists; it simply
            # cannot be addressed. That is an uncertain mutation, not a refusal.
            return LayoutOutcome(
                ok=False,
                pane_id="",
                error="herdr split reply does not name the pane it created",
                effect_unknown=True,
            )
        swap = self._request(
            target=target,
            method=herdr_write_calls.SWAP_METHOD,
            params=herdr_write_calls.swap_params(
                source_pane_id=target.pane_id, target_pane_id=created
            ),
            expect=herdr_write_calls.EXPECT_PANE_SWAP,
        )
        if not swap.ok:
            return LayoutOutcome(
                ok=False, pane_id=created, error=swap.error, effect_unknown=swap.effect_unknown
            )
        refusal = herdr_write_calls.swap_refusal(
            result=swap.result, source_pane_id=target.pane_id, target_pane_id=created
        )
        if refusal:
            # A REFUSAL, not an uncertainty: herdr answered, and its answer was
            # that it did not move anything. The pane exists where the split
            # left it — below the target — so launching into it now would put
            # the command somewhere nobody is looking.
            return LayoutOutcome(ok=False, pane_id=created, error=refusal, effect_unknown=False)
        launch = self._request(
            target=target,
            method=herdr_write_calls.PASTE_METHOD,
            params=herdr_write_calls.launch_params(pane_id=created, command=command),
            expect=herdr_write_calls.EXPECT_OK,
        )
        if not launch.ok:
            return LayoutOutcome(
                ok=False, pane_id=created, error=launch.error, effect_unknown=launch.effect_unknown
            )
        return LayoutOutcome(ok=True, pane_id=created, error="", effect_unknown=False)

    def _write(
        self, *, target: herdr_identity.HerdrPaneTarget, params: Mapping[str, object]
    ) -> WriteOutcome:
        """One bounded input mutation, reduced to the three facts a caller needs."""
        outcome = self._request(
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

    def _request(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        method: str,
        params: Mapping[str, object],
        expect: herdr_protocol.ReplyExpectation,
    ) -> herdr_transport.RpcOutcome:
        """One bounded mutation against the generation `target` names, or why not.

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
