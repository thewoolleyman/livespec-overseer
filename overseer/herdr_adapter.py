"""herdr_adapter.py — the native herdr OBSERVATION surface, addressed exactly.

The daemon's three questions about a terminal — which panes exist, what does this
one show, and what is actually running in it — answered over the herdr socket
API. :mod:`herdr_calls` shapes each call and reads each reply (pure);
:mod:`herdr_transport` owns the socket and the deadline; this module is the thin
layer that turns a BACKEND-QUALIFIED coordinate into the right bounded request
and the reply into a value a caller can act on.

**Opt-in by explicit construction, and unused by production defaults.** Nothing
in the supervision loop reaches this module yet: backend selection, mapping-store
rewrites and `overseer-start` activation are a separate slice, deliberately, so
an incomplete backend is never silently activated. Constructing a
:class:`HerdrAdapter` is the only way to reach it.

**Every operation is addressed by a target, never by a bare pane id.**
`SPECIFICATION/contracts.md` requires a backend operation to identify the actual
backend instance and target, and `SPECIFICATION/constraints.md` requires instance
identity to include the live server generation. So the expected peer is built
from the TARGET — its socket path, server pid and server start time — plus this
process's own uid. Two consequences are the point of the design rather than side
effects: a target for one server cannot read a pane on another even when both
servers use the same pane id, and a coordinate whose generation has been replaced
reads NOTHING rather than silently adopting whichever server now answers.

**Identification is the read-only enumeration, not a probe of its own.** The
transport reports the generation it validated on every outcome, so asking "which
server is listening?" is just enumerating panes and keeping the peer. That is
deliberate: a dedicated probe would be one more method to get wrong, and a
MUTATING probe would make discovery itself an effect.

**A reply must describe the pane that was ASKED about, not merely answer the
request.** The transport matches a reply's id to the request's, which proves the
reply answers THIS REQUEST; it says nothing about which pane the reply is about.
So the two pane-scoped observations additionally require the payload to echo the
target's pane id, and refuse when it names another pane or names none at all.
Independent review found the gap by presenting a correctly-addressed reply whose
payload said `w1:p999`: the capture returned `ok=True` with that pane's text.

The ownership check runs AFTER the payload is parsed, not before, and the order
is deliberate: a payload that cannot be read at all is diagnosed as UNREADABLE
rather than as foreign, which is the more accurate of the two and keeps the two
failures distinguishable to an operator. Parsing is pure, so nothing is acted on
in between.

**Nothing here mutates a pane.** Input and layout are separate surfaces; an
observation that cannot be read is a refusal naming why, never an empty success
that would read as an idle pane.
"""

from __future__ import annotations

import itertools
import os
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Protocol

import claude_sessions
import herdr_calls
import herdr_identity
import herdr_protocol
import herdr_transport
from _seams import PidToOptionalStr

__all__: list[str] = [
    "REQUEST_ID_PREFIX",
    "ForegroundObserver",
    "ForegroundReading",
    "HerdrAdapter",
    "InstanceIdentification",
    "OwnershipObserver",
    "PaneCapture",
    "PaneListing",
]

REQUEST_ID_PREFIX = "overseer-herdr"


def _default_request_ids() -> Iterator[str]:
    """Distinct request ids, which is what makes a mismatched reply detectable.

    The transport refuses a reply whose id is not the one it sent; that guard is
    worth nothing if every request carries the same id. A process-wide counter is
    enough because the id only has to be unique against replies THIS process is
    waiting for, and each request owns its own connection.
    """
    return (f"{REQUEST_ID_PREFIX}-{index}" for index in itertools.count(1))


@dataclass(frozen=True, kw_only=True)
class InstanceIdentification:
    """Which live server generation is listening on a socket, or why that is unknown."""

    ok: bool
    peer: herdr_transport.PeerIdentity | None
    error: str


@dataclass(frozen=True, kw_only=True)
class PaneListing:
    """Every pane the addressed server holds, or a named refusal and no panes."""

    ok: bool
    panes: tuple[herdr_calls.PaneRow, ...]
    error: str


@dataclass(frozen=True, kw_only=True)
class PaneCapture:
    """One pane's visible content, or a named refusal and no text.

    An unreadable capture carries `text == ""` AND `ok is False`. The pairing is
    load-bearing: an empty pane and an unreadable pane produce the same string,
    and `SPECIFICATION/contracts.md` forbids reading the second as the first.
    """

    ok: bool
    text: str
    error: str


@dataclass(frozen=True, kw_only=True)
class ForegroundReading:
    """What is running in one pane, or a named refusal and no process."""

    ok: bool
    process: herdr_calls.ForegroundProcess | None
    error: str


class ForegroundObserver(Protocol):
    """The exact-pane process observation required by public bootstrap."""

    def foreground(self, *, target: herdr_identity.HerdrPaneTarget) -> ForegroundReading: ...


class OwnershipObserver(Protocol):
    """The complete read-only Herdr surface required for ownership discovery."""

    def identify(self, *, socket_path: str) -> InstanceIdentification: ...

    def list_panes(self, *, target: herdr_identity.HerdrPaneTarget) -> PaneListing: ...

    def foreground(self, *, target: herdr_identity.HerdrPaneTarget) -> ForegroundReading: ...


def _unreadable(*, kind: str) -> str:
    return f"herdr {kind} reply carried an unreadable payload"


def _foreign_pane(*, kind: str, echoed: str, pane_id: str) -> str:
    return (
        f"herdr {kind} reply describes pane {echoed!r}, not the requested {pane_id!r}; "
        "a matching request id proves the reply answers this REQUEST, not this PANE"
    )


@dataclass(frozen=True, kw_only=True)
class HerdrAdapter:
    """The observation surface for herdr panes, one bounded request per call.

    `starttime_of` and `monotonic` are passed through to the transport so a test
    can drive an unreadable generation or an expired deadline deterministically.
    `expected_uid` is injectable only so the "a socket served by another user is
    not this track's backend" guard can be asserted; the daemon always takes its
    own uid. `request_ids` is injectable so a test can assert the exact bytes on
    the wire.
    """

    timeout_seconds: float = herdr_transport.DEFAULT_TIMEOUT_SECONDS
    max_reply_bytes: int = herdr_protocol.MAX_REPLY_BYTES
    expected_uid: int = field(default_factory=os.getuid)
    request_ids: Iterator[str] = field(default_factory=_default_request_ids)
    starttime_of: PidToOptionalStr = claude_sessions.proc_starttime
    monotonic: Callable[[], float] = time.monotonic

    def identify(self, *, socket_path: str) -> InstanceIdentification:
        """Learn which server generation is listening, mutating nothing.

        `expected_peer=None` is the transport's DISCOVERY case — the caller does
        not yet know the generation and is asking to be told. Pinning what it
        returns on every later call is what makes those calls exact.
        """
        outcome = self._transport(socket_path=socket_path, peer=None).request(
            request_id=next(self.request_ids),
            method=herdr_protocol.METHOD_PANE_LIST,
            params=herdr_calls.list_params(),
            expect=herdr_calls.EXPECT_LIST,
        )
        return InstanceIdentification(ok=outcome.ok, peer=outcome.peer, error=outcome.error)

    def list_panes(self, *, target: herdr_identity.HerdrPaneTarget) -> PaneListing:
        """Enumerate the panes of the server `target` names — and only that server."""
        result, error = self._result_of(
            target=target,
            method=herdr_protocol.METHOD_PANE_LIST,
            params=herdr_calls.list_params(),
            expect=herdr_calls.EXPECT_LIST,
        )
        if error:
            return PaneListing(ok=False, panes=(), error=error)
        panes = herdr_calls.pane_rows(result=result)
        if panes is None:
            return PaneListing(ok=False, panes=(), error=_unreadable(kind="pane listing"))
        return PaneListing(ok=True, panes=panes, error="")

    def capture_pane(
        self, *, target: herdr_identity.HerdrPaneTarget, retain_ansi: bool = True
    ) -> PaneCapture:
        """Capture `target`'s VISIBLE content, retaining styling by default."""
        result, error = self._result_of(
            target=target,
            method=herdr_protocol.METHOD_PANE_READ,
            params=herdr_calls.read_params(pane_id=target.pane_id, retain_ansi=retain_ansi),
            expect=herdr_calls.EXPECT_READ,
        )
        if error:
            return PaneCapture(ok=False, text="", error=error)
        read = herdr_calls.pane_read(result=result)
        if read is None:
            return PaneCapture(ok=False, text="", error=_unreadable(kind="pane capture"))
        if read.pane_id != target.pane_id:
            return PaneCapture(
                ok=False,
                text="",
                error=_foreign_pane(
                    kind="pane capture", echoed=read.pane_id, pane_id=target.pane_id
                ),
            )
        return PaneCapture(ok=True, text=read.text, error="")

    def foreground(self, *, target: herdr_identity.HerdrPaneTarget) -> ForegroundReading:
        """Read what is actually running in `target`, not the shell hosting it."""
        result, error = self._result_of(
            target=target,
            method=herdr_protocol.METHOD_PANE_PROCESS_INFO,
            params=herdr_calls.process_info_params(pane_id=target.pane_id),
            expect=herdr_calls.EXPECT_PROCESS_INFO,
        )
        if error:
            return ForegroundReading(ok=False, process=None, error=error)
        process = herdr_calls.foreground_process(result=result)
        if process is None:
            return ForegroundReading(ok=False, process=None, error=_unreadable(kind="process info"))
        if process.pane_id != target.pane_id:
            return ForegroundReading(
                ok=False,
                process=None,
                error=_foreign_pane(
                    kind="process info", echoed=process.pane_id, pane_id=target.pane_id
                ),
            )
        return ForegroundReading(ok=True, process=process, error="")

    def _transport(
        self, *, socket_path: str, peer: herdr_transport.PeerIdentity | None
    ) -> herdr_transport.HerdrTransport:
        return herdr_transport.HerdrTransport(
            socket_path=socket_path,
            expected_peer=peer,
            timeout_seconds=self.timeout_seconds,
            max_reply_bytes=self.max_reply_bytes,
            starttime_of=self.starttime_of,
            monotonic=self.monotonic,
        )

    def _result_of(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        method: str,
        params: Mapping[str, object],
        expect: herdr_protocol.ReplyExpectation,
    ) -> tuple[dict[str, object], str]:
        """One bounded request to the generation `target` names, or why not.

        The expected peer is derived from the target rather than remembered from
        an earlier identification, so a stale coordinate cannot be rescued by a
        cached generation — which is the whole point of carrying the generation
        in the coordinate.
        """
        outcome = self._transport(
            socket_path=target.socket_path,
            peer=herdr_transport.PeerIdentity(
                pid=target.server_pid,
                uid=self.expected_uid,
                starttime=target.server_starttime,
            ),
        ).request(request_id=next(self.request_ids), method=method, params=params, expect=expect)
        if not outcome.ok:
            return {}, outcome.error
        return outcome.result, ""
