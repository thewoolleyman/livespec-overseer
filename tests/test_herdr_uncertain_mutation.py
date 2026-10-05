"""An attempted herdr write whose effect cannot be verified stays UNCERTAIN.

`SPECIFICATION/contracts.md` separates a herdr failure "proven to precede any
termination attempt", which preserves the round's authorization and may be
retried, from one after that boundary, which "MUST NOT be submitted again"; and
`SPECIFICATION/constraints.md` says that an "attempted launch with an unknown
outcome MUST NOT be submitted again". A caller can only honour that if the
transport tells it which side of the write boundary the failure fell on.

`timed_out` is NOT that signal and must not be mistaken for it. A timeout is one
way a reply fails to arrive; a truncated reply, a reply past the size bound, an
unparseable reply, a reply answering someone else's request, an error envelope
and a reply missing the field that was required are all the OTHER ways, and every
one of them follows a `sendall` that already committed the request. The server
may have performed the mutation in each case. So the question "may I do this
again?" is answered by `request_sent` and `ok` TOGETHER, never by `timed_out` —
which is the distinction this file pins, because reading it off `timed_out` would
mark six of these seven committed writes as safe to replay.

The transport is driven over a REAL local AF_UNIX server, and each case asserts
how many requests actually crossed the socket, because "is never automatically
retried" is a claim about what was WRITTEN and cannot be checked any other way.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import claude_sessions
import pytest

__all__: list[str] = []

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "overseer"
PROTOCOL_PATH = PACKAGE_DIR / "herdr_protocol.py"
TRANSPORT_PATH = PACKAGE_DIR / "herdr_transport.py"

REQUEST_ID = "overseer-mutate-1"
PANE_SWAP_RESULT: dict[str, object] = {"type": "pane_swap", "swap": {"changed": True}}


def _modules() -> tuple[Any, Any]:
    for path in (PROTOCOL_PATH, TRANSPORT_PATH):
        assert path.is_file(), f"the herdr boundary needs {path.relative_to(PACKAGE_DIR.parent)}"
    return (
        importlib.import_module("herdr_protocol"),
        importlib.import_module("herdr_transport"),
    )


@pytest.fixture(name="socket_dir")
def _socket_dir() -> Iterator[Path]:
    """A SHORT scratch directory, because an AF_UNIX address is capped near 108 bytes."""
    created = tempfile.mkdtemp(prefix="hrdr")
    yield Path(created)
    shutil.rmtree(created, ignore_errors=True)


def _serve(*, address: Path, respond: Callable[[Any], None]) -> list[bytes]:
    """Start a REAL AF_UNIX server that accepts REPEATEDLY; return the request record.

    Accepting more than one connection is the point: `HerdrTransport` opens a
    fresh connection per request, so a one-shot listener would make "exactly one
    request crossed the socket" true by construction rather than by the
    transport's own restraint.
    """
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(address))
    listener.listen(4)
    received: list[bytes] = []

    def run() -> None:
        listener.settimeout(3.0)
        while True:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            with conn:
                conn.settimeout(3.0)
                buffered = b""
                try:
                    while not buffered.endswith(b"\n"):
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        buffered += chunk
                    if buffered:
                        received.append(buffered)
                    respond(conn)
                except OSError:
                    return

    threading.Thread(target=run, daemon=True).start()
    return received


def _replies(*, body: bytes, newline: bool = True, pause: float = 0.0) -> Callable[[Any], None]:
    payload = body + (b"\n" if newline else b"")

    def respond(conn: Any) -> None:
        time.sleep(pause)
        conn.sendall(payload)

    return respond


def _swap_body(*, result: dict[str, object] | None = None, request_id: str = REQUEST_ID) -> bytes:
    payload = PANE_SWAP_RESULT if result is None else result
    return json.dumps({"id": request_id, "result": payload}).encode("utf-8")


def _live_peer(*, transport_module: Any) -> Any:
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None, "this process must have a readable /proc start time"
    return transport_module.PeerIdentity(pid=os.getpid(), uid=os.getuid(), starttime=starttime)


def _swap(*, transport: Any, protocol: Any) -> Any:
    """One MUTATION — a pane swap, the measured layout write this slice performs."""
    return transport.request(
        request_id=REQUEST_ID,
        method=protocol.METHOD_PANE_SWAP,
        params={"source_pane_id": "w1:p1", "target_pane_id": "w1:p2"},
        expect=protocol.ReplyExpectation(result_type="pane_swap", required_fields=("swap",)),
    )


def _transport(*, transport_module: Any, address: Path, **overrides: Any) -> Any:
    fields: dict[str, Any] = {
        "socket_path": str(address),
        "expected_peer": _live_peer(transport_module=transport_module),
        "timeout_seconds": 5.0,
    }
    fields.update(overrides)
    return transport_module.HerdrTransport(**fields)


def test_every_unverified_reply_after_an_attempted_write_is_unknown_effect(*, socket_dir: Path):
    """Seven ways a committed write goes unanswered, and only ONE of them times out.

    Each case writes the swap request and then fails to produce a usable answer.
    The mutation may have happened in every one — the server had the request —
    so every one is `effect_unknown`. Reading that off `timed_out` instead would
    call six of the seven safe to replay.

    Each case carries its own transport overrides rather than sharing one set,
    because two of the seven are produced by a transport BOUND rather than by the
    reply's content: the timeout needs a short deadline against a slow peer, and
    the size bound needs a small ceiling against an endless one.
    """
    protocol, transport_module = _modules()
    # Asserted rather than left to an `AttributeError`, so the Red names the
    # missing contract member instead of tripping over it — the same reason the
    # sibling suites assert on a module path before importing it.
    assert hasattr(transport_module.RpcOutcome, "effect_unknown"), (
        "`RpcOutcome` must carry `effect_unknown`: `request_sent` and `ok` "
        "together decide whether a mutation may be submitted again, and no "
        "caller should have to recompute that pairing"
    )
    good = json.dumps(PANE_SWAP_RESULT)
    cases: dict[str, tuple[Callable[[Any], None], dict[str, Any]]] = {
        "no reply at all before the deadline": (
            _replies(body=_swap_body(), pause=3.0),
            {"timeout_seconds": 0.4},
        ),
        "a reply truncated before its delimiter": (
            _replies(body=_swap_body(), newline=False),
            {},
        ),
        "a reply past the bounded size with no delimiter": (
            _replies(body=b"x" * 4096, newline=False),
            {"max_reply_bytes": 512},
        ),
        "an unparseable reply": (_replies(body=b'{"id":'), {}),
        "a reply answering another request": (
            _replies(body=f'{{"id":"someone-else","result":{good}}}'.encode()),
            {},
        ),
        "an error envelope": (
            _replies(
                body=json.dumps({"id": REQUEST_ID, "error": {"message": "no such pane"}}).encode(
                    "utf-8"
                )
            ),
            {},
        ),
        "a reply missing the required field": (
            _replies(body=_swap_body(result={"type": "pane_swap"})),
            {},
        ),
    }

    for index, (defect, (respond, overrides)) in enumerate(cases.items()):
        address = socket_dir / f"u{index}.sock"
        received = _serve(address=address, respond=respond)
        outcome = _swap(
            transport=_transport(transport_module=transport_module, address=address, **overrides),
            protocol=protocol,
        )

        assert outcome.ok is False, f"{defect} was accepted"
        assert outcome.request_sent is True, f"{defect} lost the fact that the write happened"
        assert outcome.effect_unknown is True, (
            f"{defect} left the mutation's effect KNOWN; a committed write with no "
            "usable answer is uncertain regardless of whether it timed out"
        )
        assert outcome.timed_out is ("deadline" in defect), (
            f"{defect} disagrees with its own timeout classification, so this case "
            "no longer demonstrates that `timed_out` is the wrong discriminator"
        )
        time.sleep(0.1)
        assert len(received) == 1, (
            f"{defect} produced {len(received)} requests; an uncertain mutation is "
            "re-observed by the caller, never retried inside the transport"
        )

    assert (
        len([defect for defect in cases if "deadline" in defect]) == 1
    ), "exactly one of these seven cases is a timeout, by construction"


def test_a_failure_proven_to_precede_the_write_leaves_the_effect_known(*, socket_dir: Path):
    """The other side of the boundary: nothing was written, so nothing can have happened.

    These are the cases `SPECIFICATION/contracts.md` lets a caller retry, and
    they are retryable precisely because `effect_unknown` is false. An absent
    socket needs no server; a mismatched generation and an exhausted deadline are
    driven against a real one, so the refusal is proven to be the transport's
    restraint rather than an unreachable peer.
    """
    protocol, transport_module = _modules()
    live = _live_peer(transport_module=transport_module)
    foreign = transport_module.PeerIdentity(
        pid=live.pid, uid=live.uid, starttime=f"{live.starttime}9"
    )

    absent = _swap(
        transport=_transport(transport_module=transport_module, address=socket_dir / "gone.sock"),
        protocol=protocol,
    )
    address = socket_dir / "live.sock"
    received = _serve(address=address, respond=_replies(body=_swap_body()))
    mismatched = _swap(
        transport=_transport(
            transport_module=transport_module, address=address, expected_peer=foreign
        ),
        protocol=protocol,
    )
    expired = _swap(
        transport=_transport(
            transport_module=transport_module,
            address=address,
            timeout_seconds=0.5,
            monotonic=_fake_clock(readings=[0.0, 100.0]),
        ),
        protocol=protocol,
    )

    for defect, outcome in (
        ("an absent socket", absent),
        ("a foreign server generation", mismatched),
        ("an already-expired deadline", expired),
    ):
        assert outcome.ok is False, f"{defect} was accepted"
        assert outcome.request_sent is False, f"{defect} is proven to precede the write"
        assert outcome.effect_unknown is False, (
            f"{defect} was marked uncertain; a failure proven to precede the write "
            "preserves the round's authorization and may be retried"
        )
    time.sleep(0.1)
    assert received == [], "no request may cross the socket in any of these three cases"


def test_a_usable_reply_leaves_no_uncertainty(*, socket_dir: Path):
    """The mutation is verified, so its effect is known — the pair's positive case."""
    protocol, transport_module = _modules()
    address = socket_dir / "ok.sock"
    _ = _serve(address=address, respond=_replies(body=_swap_body()))

    outcome = _swap(
        transport=_transport(transport_module=transport_module, address=address),
        protocol=protocol,
    )

    assert outcome.ok is True
    assert outcome.request_sent is True
    assert outcome.effect_unknown is False
    assert outcome.result["swap"] == {"changed": True}


def _fake_clock(*, readings: list[float]) -> Callable[[], float]:
    """A monotonic seam that walks `readings`, then holds its last value."""
    remaining = list(readings)

    def read() -> float:
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    return read
