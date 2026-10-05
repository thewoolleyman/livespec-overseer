"""herdr_transport.py — the ONE module that opens a herdr socket.

The counterpart of :mod:`tmuxio` for the herdr backend, and held to the same
shape: every other herdr module (:mod:`herdr_identity`, :mod:`herdr_protocol`) is
pure, so this is the single I/O boundary and the adapter above it can be driven
against a scripted peer.

Stdlib-only, Linux-only. `socket` is the only network-capable module imported
anywhere in the supervision loop besides the OTLP emitter, and
`overseer/test_package_constraints.py` pins that fact: the address family here is
AF_UNIX, which has no network reach at all, so importing `socket` does not give
the daemon a way to make a model call. Keep it that way — an AF_INET socket in
this module would make that guard's allowance false.

Guarantees, each required by `SPECIFICATION/contracts.md` or
`SPECIFICATION/constraints.md`:

  - **ONE absolute deadline per request.** `timeout_seconds` is measured from the
    moment `request` is entered and governs connect, write and every read. A
    per-operation timeout would let a peer that answers slowly but steadily hold
    the supervision loop indefinitely, which is the one failure a fail-soft
    posture cannot address because it never crashes.
  - **The peer generation is validated BEFORE every write.** Each request opens
    its own connection and validates `SO_PEERCRED` plus the peer's `/proc` start
    time before a single byte is sent, so the "revalidate before effects"
    requirement needs no separate re-check step: there is no window between the
    validation and the write in which the server could be replaced.
  - **Bounded reply framing.** One newline-terminated reply, read in chunks and
    refused once the accumulation passes `max_reply_bytes`. EOF before the
    delimiter is a TRUNCATION, never an empty success.
  - **Fail-closed, and SPECIFIC about uncertainty.** Every failure returns an
    `RpcOutcome` naming it; nothing raises for an expected failure.

**`request_sent` and `timed_out` are the load-bearing pair, not diagnostics.**
`SPECIFICATION/contracts.md` distinguishes a herdr failure "proven to precede any
termination attempt", which preserves the round's authorization and may be
retried, from one after that boundary, which must NOT be submitted again. A
caller can only make that distinction if the transport reports whether the
request reached the server. So `request_sent=False` means the operation
provably did not happen; `request_sent=True` with `timed_out=True` means its fate
is UNKNOWN — re-observe, never blindly retry.
"""

from __future__ import annotations

import socket
import struct
import time
from collections.abc import Callable, Mapping
from contextlib import closing
from dataclasses import dataclass
from typing import Any

import claude_sessions
import herdr_protocol
from _seams import PidToOptionalStr

__all__: list[str] = [
    "DEFAULT_TIMEOUT_SECONDS",
    "PEERCRED_FORMAT",
    "HerdrTransport",
    "PeerIdentity",
    "RpcOutcome",
]

# `struct` layout of Linux's `struct ucred` as returned by
# `getsockopt(SOL_SOCKET, SO_PEERCRED, 12)`: pid, uid, gid. Measured in the
# research probe, where the decoded pid "exactly matched isolated
# `herdr ... server` ancestor".
PEERCRED_FORMAT = "3i"

# Wall-clock ceiling on ONE request. Like `tmuxio`'s own timeout this is a
# liveness floor rather than a latency budget: a herdr round trip is local IPC
# that normally returns in milliseconds, so exceeding this means the server is
# not answering.
DEFAULT_TIMEOUT_SECONDS = 5.0

_RECV_CHUNK_BYTES = 65536
_DEADLINE_ERROR = "herdr request deadline expired before a complete reply arrived"


@dataclass(frozen=True, kw_only=True)
class PeerIdentity:
    """A herdr server's live generation, as proven across its own socket.

    `pid` plus `starttime` is the non-reusable pair: the pid alone is reused after
    a restart, and the research measurement is that a restart may reuse the
    socket path and the pane ids too.
    """

    pid: int
    uid: int
    starttime: str


@dataclass(frozen=True, kw_only=True)
class RpcOutcome:
    """One request's result, or a named fail-closed refusal.

    See the module docstring for why `request_sent` and `timed_out` are part of
    the contract rather than logging detail.
    """

    ok: bool
    result: dict[str, object]
    error: str
    peer: PeerIdentity | None
    timed_out: bool
    request_sent: bool

    @property
    def effect_unknown(self) -> bool:
        """Whether a MUTATION this outcome describes may have taken effect anyway.

        The single place the write-boundary rule is decided, so no call site
        recomputes it. `SPECIFICATION/contracts.md` lets a herdr failure "proven
        to precede any termination attempt" be retried and forbids resubmitting
        one after that boundary, so the question is whether the request reached
        the server and went unanswered — `request_sent and not ok` — and nothing
        else.

        **It is deliberately NOT `timed_out`.** A timeout is one way a committed
        request goes unanswered; a truncated reply, a reply past the size bound,
        an unparseable reply, a reply carrying another request's id, an error
        envelope and a reply missing a required field are the others, and every
        one of them follows a `sendall` that already handed the server the
        mutation. Deriving replayability from `timed_out` would mark five of
        those six safe to repeat.

        It is derived rather than stored for the same reason: a stored flag can
        be set wrong at one of the eight construction sites, and this invariant
        is not the kind that should depend on remembering.
        """
        return self.request_sent and not self.ok


def _refused(
    *,
    error: str,
    peer: PeerIdentity | None = None,
    timed_out: bool = False,
    request_sent: bool = False,
) -> RpcOutcome:
    return RpcOutcome(
        ok=False,
        result={},
        error=error,
        peer=peer,
        timed_out=timed_out,
        request_sent=request_sent,
    )


def _peer_refusal(*, observed: PeerIdentity, expected: PeerIdentity | None) -> str:
    """Why `observed` may not be spoken to, or `""` when it may.

    `expected is None` is the DISCOVERY case: the caller does not yet know which
    generation is listening and is asking to be told. It is not a relaxation —
    the generation it learns is returned on the outcome, and pinning it on the
    next request is what makes every later call exact.
    """
    if expected is None or observed == expected:
        return ""
    return (
        f"herdr server generation mismatch: socket is served by "
        f"{observed} but this track is bound to {expected}"
    )


@dataclass(frozen=True, kw_only=True)
class HerdrTransport:
    """One herdr socket instance, addressed exactly and spoken to under a deadline.

    `starttime_of` and `monotonic` are injected so the beside-tests can drive an
    unreadable generation and an already-expired deadline deterministically; the
    daemon always takes the defaults. `max_reply_bytes` is injectable for the same
    reason — a test must be able to cross the bound without moving a megabyte.
    """

    socket_path: str
    expected_peer: PeerIdentity | None = None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_reply_bytes: int = herdr_protocol.MAX_REPLY_BYTES
    starttime_of: PidToOptionalStr = claude_sessions.proc_starttime
    monotonic: Callable[[], float] = time.monotonic

    def request(
        self,
        *,
        request_id: str,
        method: str,
        params: Mapping[str, object],
        expect: herdr_protocol.ReplyExpectation,
    ) -> RpcOutcome:
        """One request/reply exchange on its own connection, bounded and validated."""
        deadline = self.monotonic() + self.timeout_seconds
        payload = herdr_protocol.encode_request(request_id=request_id, method=method, params=params)
        # Constructing an AF_UNIX socket allocates a descriptor and performs no
        # I/O. An fd-exhaustion failure here is a host fault for the daemon's
        # boundary to own, not an expected herdr outcome, so it is not converted
        # into a refusal that would read as "herdr said no".
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        with closing(sock):
            return self._exchange(
                sock=sock,
                payload=payload,
                deadline=deadline,
                request_id=request_id,
                expect=expect,
            )

    def _remaining(self, *, deadline: float) -> float:
        return deadline - self.monotonic()

    def _identify(self, *, sock: Any, deadline: float) -> tuple[PeerIdentity | None, str]:
        """Connect and read the peer's generation, or say why neither happened."""
        remaining = self._remaining(deadline=deadline)
        if remaining <= 0.0:
            return None, _DEADLINE_ERROR
        sock.settimeout(remaining)
        try:
            sock.connect(self.socket_path)
            raw = sock.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize(PEERCRED_FORMAT)
            )
        except OSError as exc:
            return None, f"herdr socket {self.socket_path!r} is unreachable: {exc}"
        pid, uid, _gid = struct.unpack(PEERCRED_FORMAT, raw)
        starttime = self.starttime_of(pid=pid)
        if starttime is None:
            return None, (
                f"herdr server generation is unreadable: no /proc start time for " f"peer pid {pid}"
            )
        return PeerIdentity(pid=pid, uid=uid, starttime=starttime), ""

    def _exchange(
        self,
        *,
        sock: Any,
        payload: bytes,
        deadline: float,
        request_id: str,
        expect: herdr_protocol.ReplyExpectation,
    ) -> RpcOutcome:
        peer, identify_error = self._identify(sock=sock, deadline=deadline)
        if peer is None:
            return _refused(error=identify_error, timed_out=identify_error == _DEADLINE_ERROR)
        refusal = _peer_refusal(observed=peer, expected=self.expected_peer)
        if refusal:
            return _refused(error=refusal, peer=peer)
        # THE WINDOW BETWEEN THE TWO OTHER DEADLINE GUARDS. Identification is not
        # free — it connects, reads `SO_PEERCRED` and reads `/proc` — so the
        # deadline can expire inside it, and guarding only before the connect and
        # inside the read loop left the write itself unguarded. A request
        # committed here is the one failure worse than a timeout: the caller is
        # told `request_sent=False` about a request the server has, and may act
        # on, so a mutation that DID happen is reported as provably not having
        # happened. The peer rides along on the refusal because it WAS
        # identified; only the write is abandoned.
        remaining = self._remaining(deadline=deadline)
        if remaining <= 0.0:
            return _refused(error=_DEADLINE_ERROR, peer=peer, timed_out=True)
        # AND THE WINDOW MUST BE THE RIGHT SIZE, not merely open — a distinct
        # defect from the one above, and the one that made the single absolute
        # deadline ADVISORY. `_identify` set the socket's timeout from the budget
        # remaining BEFORE the connect, so `sendall` inherited that value and was
        # allowed to block for the whole original budget after identification had
        # already spent most of it: measured at 3.609s against a 2.0s deadline
        # when identification took 1.6s. Re-arming here costs no extra clock
        # reading, because it reuses the one the guard above just took — which is
        # also why every injected-clock test in the sibling suites is unaffected.
        sock.settimeout(remaining)
        raw, read_error, timed_out = self._send_and_read(
            sock=sock, payload=payload, deadline=deadline
        )
        if read_error:
            return _refused(error=read_error, peer=peer, timed_out=timed_out, request_sent=True)
        reading = herdr_protocol.read_reply(raw=raw, request_id=request_id, expect=expect)
        return RpcOutcome(
            ok=reading.ok,
            result=reading.result,
            error=reading.error,
            peer=peer,
            timed_out=False,
            request_sent=True,
        )

    def _send_and_read(
        self, *, sock: Any, payload: bytes, deadline: float
    ) -> tuple[bytes, str, bool]:
        """Write the request, then read ONE bounded newline-delimited reply.

        The write and the read share one `except OSError`, and that is deliberate
        rather than lazy: both report the same thing to the caller — the request
        was committed to the socket and no usable reply came back — and a
        connection reset seen on the write is exactly as uncertain as one seen on
        the read. `TimeoutError` (what `socket` raises on a timeout since 3.10,
        and itself an `OSError`) is the one case distinguished, because a deadline
        is what makes an outcome UNCERTAIN rather than failed.
        """
        buffered = bytearray()
        try:
            sock.sendall(payload)
            while True:
                remaining = self._remaining(deadline=deadline)
                if remaining <= 0.0:
                    return b"", _DEADLINE_ERROR, True
                sock.settimeout(remaining)
                chunk = sock.recv(_RECV_CHUNK_BYTES)
                if not chunk:
                    return b"", "herdr reply was truncated before its delimiter", False
                buffered.extend(chunk)
                if len(buffered) > self.max_reply_bytes:
                    return (
                        b"",
                        (
                            f"herdr reply passed the bounded size of "
                            f"{self.max_reply_bytes} bytes with no delimiter"
                        ),
                        False,
                    )
                delimiter = buffered.find(b"\n")
                if delimiter >= 0:
                    return bytes(buffered[:delimiter]), "", False
        except OSError as exc:
            timed_out = isinstance(exc, TimeoutError)
            return b"", (_DEADLINE_ERROR if timed_out else f"herdr socket failed: {exc}"), timed_out
