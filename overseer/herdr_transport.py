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
