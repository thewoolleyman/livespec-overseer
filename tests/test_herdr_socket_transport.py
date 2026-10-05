"""The bounded, peer-validated herdr socket transport, over a REAL AF_UNIX server.

`SPECIFICATION/contracts.md` requires that a backend operation "identify the
actual backend instance and target", and that "unsupported or malformed backend
responses MUST be bounded and fail closed, never treated as proof of an idle
pane, successful paste, or successful replacement".
`SPECIFICATION/constraints.md` adds that instance identity "MUST include the live
server generation, proven by its process identity and start time or an
equivalent non-reusable identity; a socket path alone is insufficient".

`plan/herdr-overseer/research/002-herdr-api-evidence.md` measured the protocol
this drives: newline-delimited JSON over AF_UNIX/SOCK_STREAM, one request object
`{"id", "method", "params"}` per connection, one newline-terminated reply
wrapping `result` or `error`, and Linux `SO_PEERCRED` decoded as `3i` yielding the
server's pid/uid/gid — whose pid "exactly matched isolated `herdr ... server`
ancestor".

**Every framing, peer-credential and timeout assertion here runs against a real
local AF_UNIX socket**, because a dictionary of canned replies cannot exercise the
things most likely to be wrong: that a reply split across seven writes is
reassembled, that EOF before the newline is not read as a valid empty reply, that
`SO_PEERCRED` returns what we think it returns, and that nothing is written when
the peer generation does not match. The one exception is noted on its own test.
The server here is this very test process, so the peer pid, uid and `/proc` start
time it validates against are genuine process evidence rather than fixtures.

Module imports are function-local behind an assertion on each expected module
path, so this file collects and reaches a real assertion at Red rather than dying
as a `ModuleNotFoundError` at collection time.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import struct
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

REQUEST_ID = "overseer-1"
# The measured `pane.process_info` reply shape, trimmed to the fields under test.
PROCESS_INFO_TYPE = "pane_process_info"
PROCESS_INFO_RESULT: dict[str, object] = {
    "type": PROCESS_INFO_TYPE,
    "process_info": {"pane_id": "w1:p2", "shell_pid": 1015684},
}


def _modules() -> tuple[Any, Any]:
    for path in (PROTOCOL_PATH, TRANSPORT_PATH):
        assert path.is_file(), (
            f"the bounded herdr socket transport needs "
            f"{path.relative_to(PACKAGE_DIR.parent)}; pure envelope handling and the "
            "socket boundary stay in separate modules per this repo's rules"
        )
    return (
        importlib.import_module("herdr_protocol"),
        importlib.import_module("herdr_transport"),
    )


@pytest.fixture(name="socket_dir")
def _socket_dir() -> Iterator[Path]:
    """A SHORT scratch directory for AF_UNIX addresses.

    An AF_UNIX path is capped near 108 bytes, and pytest's `tmp_path` is derived
    from the test NAME — which in this file would spend most of that budget. A
    short `mkdtemp` keeps every address comfortably inside the cap.
    """
    created = tempfile.mkdtemp(prefix="hrdr")
    yield Path(created)
    shutil.rmtree(created, ignore_errors=True)


def _serve(*, address: Path, respond: Callable[[Any], None]) -> list[bytes]:
    """Start a one-shot REAL AF_UNIX server; return the growing request record.

    The returned list is appended to by the serving thread, so a test can assert
    on what actually crossed the socket — including that NOTHING did.
    """
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(address))
    listener.listen(1)
    received: list[bytes] = []

    def run() -> None:
        listener.settimeout(5.0)
        try:
            conn, _ = listener.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(5.0)
            buffered = b""
            try:
                while not buffered.endswith(b"\n"):
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buffered += chunk
            except OSError:
                buffered = b""
            if buffered:
                received.append(buffered)
            respond(conn)
        listener.close()

    threading.Thread(target=run, daemon=True).start()
    return received


def _replies(
    *, body: bytes, newline: bool = True, chunks: int = 1, pause: float = 0.0
) -> Callable[[Any], None]:
    payload = body + (b"\n" if newline else b"")
    width = max(1, -(-len(payload) // chunks))

    def respond(conn: Any) -> None:
        time.sleep(pause)
        for start in range(0, len(payload), width):
            conn.sendall(payload[start : start + width])
            if chunks > 1:
                time.sleep(0.005)

    return respond


def _result_body(*, result: dict[str, object] | None = None, request_id: str = REQUEST_ID) -> bytes:
    payload = PROCESS_INFO_RESULT if result is None else result
    return json.dumps({"id": request_id, "result": payload}).encode("utf-8")


def _live_peer(*, transport_module: Any) -> Any:
    """This very process, as peer identity — real pid, uid and /proc start time."""
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None, "this process must have a readable /proc start time"
    return transport_module.PeerIdentity(pid=os.getpid(), uid=os.getuid(), starttime=starttime)


def _expect(*, protocol: Any) -> Any:
    return protocol.ReplyExpectation(
        result_type=PROCESS_INFO_TYPE, required_fields=("process_info",)
    )


def _ask(*, transport: Any, protocol: Any, request_id: str = REQUEST_ID) -> Any:
    return transport.request(
        request_id=request_id,
        method=protocol.METHOD_PANE_PROCESS_INFO,
        params={"pane_id": "w1:p2"},
        expect=_expect(protocol=protocol),
    )


def _transport(*, transport_module: Any, address: Path, **overrides: Any) -> Any:
    fields: dict[str, Any] = {
        "socket_path": str(address),
        "expected_peer": _live_peer(transport_module=transport_module),
        "timeout_seconds": 5.0,
    }
    fields.update(overrides)
    return transport_module.HerdrTransport(**fields)


def _fake_clock(*, readings: list[float]) -> Callable[[], float]:
    """A monotonic seam that walks `readings`, then holds its last value.

    The absolute-deadline guards cannot be driven by real time without making the
    test a race. Injecting the clock makes "the deadline had already passed"
    deterministic, which is the only way to assert the guard rather than hope for
    it.
    """
    remaining = list(readings)

    def read() -> float:
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    return read


def test_the_request_crosses_the_socket_as_one_newline_delimited_json_object(*, socket_dir: Path):
    protocol, transport_module = _modules()
    address = socket_dir / "h.sock"
    received = _serve(address=address, respond=_replies(body=_result_body()))

    outcome = _ask(
        transport=_transport(transport_module=transport_module, address=address),
        protocol=protocol,
    )

    assert outcome.ok, outcome.error
    assert outcome.result == PROCESS_INFO_RESULT
    assert outcome.request_sent is True
    assert outcome.timed_out is False
    assert received, "the server recorded no request at all"
    wire = received[0]
    assert wire.endswith(b"\n")
    assert wire.count(b"\n") == 1, "exactly one newline-delimited request per connection"
    assert json.loads(wire.decode("utf-8")) == {
        "id": REQUEST_ID,
        "method": "pane.process_info",
        "params": {"pane_id": "w1:p2"},
    }


def test_a_reply_split_across_many_writes_is_reassembled(*, socket_dir: Path):
    protocol, transport_module = _modules()
    address = socket_dir / "h.sock"
    _ = _serve(address=address, respond=_replies(body=_result_body(), chunks=7))

    outcome = _ask(
        transport=_transport(transport_module=transport_module, address=address),
        protocol=protocol,
    )

    assert outcome.ok, outcome.error
    assert outcome.result == PROCESS_INFO_RESULT


def test_the_live_peer_generation_is_what_an_unpinned_transport_adopts(*, socket_dir: Path):
    protocol, transport_module = _modules()
    address = socket_dir / "h.sock"
    _ = _serve(address=address, respond=_replies(body=_result_body()))

    outcome = _ask(
        transport=_transport(
            transport_module=transport_module, address=address, expected_peer=None
        ),
        protocol=protocol,
    )

    assert outcome.ok, outcome.error
    # SO_PEERCRED reports the SERVER's credentials, and this process IS the server.
    assert outcome.peer == _live_peer(transport_module=transport_module)
    assert outcome.peer.starttime == claude_sessions.proc_starttime(pid=os.getpid())


def test_a_mismatched_peer_generation_writes_nothing_at_all(*, socket_dir: Path):
    protocol, transport_module = _modules()
    address = socket_dir / "h.sock"
    received = _serve(address=address, respond=_replies(body=_result_body()))
    live = _live_peer(transport_module=transport_module)
    # Same socket, same pid, DIFFERENT start time: the restart-reused-pid case a
    # pid-only identity cannot see.
    stale = transport_module.PeerIdentity(
        pid=live.pid, uid=live.uid, starttime=f"{live.starttime}9"
    )

    outcome = _ask(
        transport=_transport(
            transport_module=transport_module, address=address, expected_peer=stale
        ),
        protocol=protocol,
    )

    assert outcome.ok is False
    assert "generation" in outcome.error
    assert outcome.request_sent is False, "a refused peer must not be written to"
    assert received == [], f"bytes reached a server whose generation was refused: {received!r}"


def test_a_mismatched_peer_uid_is_refused(*, socket_dir: Path):
    protocol, transport_module = _modules()
    address = socket_dir / "h.sock"
    _ = _serve(address=address, respond=_replies(body=_result_body()))
    live = _live_peer(transport_module=transport_module)
    other = transport_module.PeerIdentity(pid=live.pid, uid=live.uid + 1, starttime=live.starttime)

    outcome = _ask(
        transport=_transport(
            transport_module=transport_module, address=address, expected_peer=other
        ),
        protocol=protocol,
    )

    assert outcome.ok is False
    assert outcome.request_sent is False


def test_an_unreadable_peer_generation_fails_closed(*, socket_dir: Path):
    protocol, transport_module = _modules()
    address = socket_dir / "h.sock"
    _ = _serve(address=address, respond=_replies(body=_result_body()))

    outcome = _ask(
        transport=_transport(
            transport_module=transport_module,
            address=address,
            expected_peer=None,
            starttime_of=lambda *, pid: None,
        ),
        protocol=protocol,
    )

    assert outcome.ok is False
    assert outcome.peer is None
    assert outcome.request_sent is False
    assert "unreadable" in outcome.error


def test_an_absent_socket_fails_closed_without_a_peer(*, socket_dir: Path):
    protocol, transport_module = _modules()

    outcome = _ask(
        transport=_transport(
            transport_module=transport_module,
            address=socket_dir / "nobody-is-listening.sock",
        ),
        protocol=protocol,
    )

    assert outcome.ok is False
    assert outcome.peer is None
    assert outcome.request_sent is False
    assert outcome.timed_out is False


def test_a_reply_that_never_arrives_is_bounded_and_marked_uncertain(*, socket_dir: Path):
    protocol, transport_module = _modules()
    address = socket_dir / "h.sock"
    _ = _serve(address=address, respond=_replies(body=_result_body(), pause=3.0))

    outcome = _ask(
        transport=_transport(
            transport_module=transport_module, address=address, timeout_seconds=0.4
        ),
        protocol=protocol,
    )

    assert outcome.ok is False
    # The request DID cross the socket, so the server may well have acted on it.
    # That pairing — sent, but no reply — is what makes a MUTATION uncertain, and
    # the caller needs both facts to know it must re-observe rather than retry.
    assert outcome.request_sent is True
    assert outcome.timed_out is True


def test_an_already_expired_deadline_stops_before_connecting(*, socket_dir: Path):
    protocol, transport_module = _modules()
    address = socket_dir / "h.sock"
    received = _serve(address=address, respond=_replies(body=_result_body()))

    outcome = _ask(
        transport=_transport(
            transport_module=transport_module,
            address=address,
            timeout_seconds=0.5,
            monotonic=_fake_clock(readings=[0.0, 100.0]),
        ),
        protocol=protocol,
    )

    assert outcome.ok is False
    assert outcome.request_sent is False
    assert outcome.timed_out is True
    assert received == []


def test_a_deadline_that_expires_before_the_reply_read_stops_there(*, socket_dir: Path):
    protocol, transport_module = _modules()
    address = socket_dir / "h.sock"
    _ = _serve(address=address, respond=_replies(body=_result_body(), pause=3.0))

    outcome = _ask(
        transport=_transport(
            transport_module=transport_module,
            address=address,
            timeout_seconds=0.5,
            # Reading three is the pre-WRITE guard (the sibling
            # `test_herdr_bounded_refusal_escapes` suite pins that boundary);
            # reading four is the first read-loop observation, which is the
            # boundary this test is about.
            monotonic=_fake_clock(readings=[0.0, 0.0, 0.0, 100.0]),
        ),
        protocol=protocol,
    )

    assert outcome.ok is False
    assert outcome.request_sent is True
    assert outcome.timed_out is True


def test_a_truncated_reply_missing_its_newline_is_never_read_as_a_result(*, socket_dir: Path):
    protocol, transport_module = _modules()
    address = socket_dir / "h.sock"
    _ = _serve(address=address, respond=_replies(body=_result_body(), newline=False))

    outcome = _ask(
        transport=_transport(transport_module=transport_module, address=address),
        protocol=protocol,
    )

    assert outcome.ok is False
    assert outcome.result == {}
    assert outcome.timed_out is False
    assert "truncated" in outcome.error


def test_a_reply_past_the_bounded_size_is_refused_rather_than_accumulated(*, socket_dir: Path):
    protocol, transport_module = _modules()
    address = socket_dir / "h.sock"
    # No newline anywhere, so a transport without a size bound would read until the
    # peer closed — which is the unbounded-accumulation failure being refused here.
    _ = _serve(address=address, respond=_replies(body=b"x" * 4096, newline=False))

    outcome = _ask(
        transport=_transport(
            transport_module=transport_module, address=address, max_reply_bytes=512
        ),
        protocol=protocol,
    )

    assert outcome.ok is False
    assert outcome.result == {}
    assert "bounded" in outcome.error
    # The shipped default is the protocol module's own bound, not a test value.
    assert (
        transport_module.HerdrTransport(socket_path="/unused").max_reply_bytes
        == protocol.MAX_REPLY_BYTES
    )


def test_every_unusable_reply_envelope_fails_closed_naming_its_defect(*, socket_dir: Path):
    protocol, transport_module = _modules()
    good = json.dumps(PROCESS_INFO_RESULT)
    cases: dict[str, bytes] = {
        "not valid UTF-8": b"\xff\xfe\x00",
        "not well-formed JSON": b'{"id":',
        "well-formed JSON that is not an object": b"[1, 2, 3]",
        "an error envelope": json.dumps(
            {"id": REQUEST_ID, "error": {"message": "no such pane"}}
        ).encode("utf-8"),
        "no id at all": f'{{"result": {good}}}'.encode(),
        "another request's id": f'{{"id": "someone-else", "result": {good}}}'.encode(),
        "no result": json.dumps({"id": REQUEST_ID}).encode("utf-8"),
        "a result that is not an object": json.dumps({"id": REQUEST_ID, "result": 5}).encode(
            "utf-8"
        ),
        "another result type": _result_body(result={"type": "pane_read", "process_info": {}}),
        "a missing required field": _result_body(result={"type": PROCESS_INFO_TYPE}),
    }

    for defect, body in cases.items():
        address = socket_dir / f"c{len(defect)}{abs(hash(defect)) % 10000}.sock"
        _ = _serve(address=address, respond=_replies(body=body))
        outcome = _ask(
            transport=_transport(transport_module=transport_module, address=address),
            protocol=protocol,
        )
        assert outcome.ok is False, f"a reply carrying {defect} was accepted"
        assert outcome.result == {}, f"a reply carrying {defect} yielded a result"
        assert outcome.error != "", f"a reply carrying {defect} was refused without a reason"
        # A bad reply is NOT an uncertain mutation: the server answered, so the
        # caller knows the operation's fate even though the answer was unusable.
        assert outcome.timed_out is False, f"a reply carrying {defect} was marked uncertain"


def test_the_peercred_layout_this_transport_decodes_is_the_measured_one():
    """The ONE assertion here that does not go through a socket.

    `struct.calcsize("3i")` is 12 on this platform, which is the byte count the
    research measurement records passing to `getsockopt(SOL_SOCKET, SO_PEERCRED,
    12)`. Pinning it keeps a silent layout change from turning peer validation
    into a decode of the wrong three integers — which would compare real
    credentials against garbage and could pass by coincidence.
    """
    _, transport_module = _modules()

    assert struct.calcsize(transport_module.PEERCRED_FORMAT) == 12
    assert len(struct.unpack(transport_module.PEERCRED_FORMAT, struct.pack("3i", 1, 2, 3))) == 3
