"""Four measured ways the herdr boundary's bounded refusal was ESCAPED.

`SPECIFICATION/contracts.md` requires that "unsupported or malformed backend
responses MUST be bounded and fail closed, never treated as proof of an idle
pane, successful paste, or successful replacement", and
`SPECIFICATION/constraints.md` requires a selected backend to "fail closed
before the dependent action". A refusal that arrives as an uncaught exception is
not bounded, and a refusal that never arrives at all is not a refusal.

Each test here reproduces one escape measured against the imported transport and
identity baseline, where the module had the right INTENT and the wrong
PRECONDITION:

  - The absolute deadline was checked before the connect and inside the read
    loop, but NOT between them — so a deadline exhausted during peer
    identification still reached `sendall`, committing a request the caller was
    told was never sent.
  - `str.isdigit` admits non-ASCII decimal digits and imposes no length bound, so
    a target pid field reached `int()` and raised `ValueError` — for `'²'`
    (digit-ish, not a number) and for a 5000-digit field past CPython's
    integer-string conversion limit — while an Arabic-Indic numeral was accepted
    as a DIFFERENT pid than the one its bytes spell.
  - `json.loads` raises `RecursionError`, which is not a `ValueError`, so a
    2 KB deeply-nested reply — far inside the size bound — crashed the read
    instead of being refused.
  - A reply repeating a member name resolved last-wins, which
    `SPECIFICATION/scenarios.md` section "Duplicate JSON member names are never
    silently collapsed" forbids: no parser may choose either duplicate value.

Module imports are function-local behind an assertion on each expected module
path, matching the sibling herdr suites, so this file collects and reaches a real
assertion rather than dying at collection time.
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
MODULE_PATHS = {
    "herdr_identity": PACKAGE_DIR / "herdr_identity.py",
    "herdr_protocol": PACKAGE_DIR / "herdr_protocol.py",
    "herdr_transport": PACKAGE_DIR / "herdr_transport.py",
}

REQUEST_ID = "overseer-escape-1"
PROCESS_INFO_TYPE = "pane_process_info"


def _module(*, name: str) -> Any:
    path = MODULE_PATHS[name]
    assert path.is_file(), f"the herdr boundary needs {path.relative_to(PACKAGE_DIR.parent)}"
    return importlib.import_module(name)


@pytest.fixture(name="socket_dir")
def _socket_dir() -> Iterator[Path]:
    """A SHORT scratch directory, because an AF_UNIX address is capped near 108 bytes."""
    created = tempfile.mkdtemp(prefix="hrdr")
    yield Path(created)
    shutil.rmtree(created, ignore_errors=True)


def _serve(*, address: Path) -> list[bytes]:
    """Start a one-shot REAL AF_UNIX server; return the growing request record.

    The serving thread appends whatever crosses the socket, so a test can assert
    that NOTHING did. It answers with a usable reply precisely so that an
    accidental write would SUCCEED rather than fail for an unrelated reason.
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
                if buffered:
                    received.append(buffered)
                conn.sendall(_usable_reply())
            except OSError:
                return
        listener.close()

    threading.Thread(target=run, daemon=True).start()
    return received


def _usable_reply() -> bytes:
    payload = {
        "id": REQUEST_ID,
        "result": {"type": PROCESS_INFO_TYPE, "process_info": {"pane_id": "w1:p2"}},
    }
    return json.dumps(payload).encode("utf-8") + b"\n"


def _fake_clock(*, readings: list[float]) -> Callable[[], float]:
    """A monotonic seam that walks `readings`, then holds its last value."""
    remaining = list(readings)

    def read() -> float:
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    return read


def _encoded_target(*, pid_field: str) -> str:
    """A qualified coordinate whose ONLY defect is its server-pid field."""
    identity = _module(name="herdr_identity")
    fields = (
        b"/tmp/h.sock".hex(),
        pid_field,
        b"981".hex(),
        b"w1:p1".hex(),
    )
    return identity.HERDR_SCHEME + identity.FIELD_SEPARATOR.join(fields)


def test_a_deadline_exhausted_during_peer_identification_writes_nothing(*, socket_dir: Path):
    """The window between the connect guard and the read guard must not admit a write.

    Peer identification does real work — connect, `SO_PEERCRED`, a `/proc` read —
    so the deadline can expire inside it. The clock is injected to place the
    expiry exactly there: reading one opens the deadline, reading two passes the
    pre-connect guard, reading three is the first observation AFTER the peer is
    known. A request committed at that point is the worst possible outcome,
    because the caller is told `request_sent=False` about a request the server
    received and may already have acted on.
    """
    protocol = _module(name="herdr_protocol")
    transport_module = _module(name="herdr_transport")
    address = socket_dir / "h.sock"
    received = _serve(address=address)
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None, "this process must have a readable /proc start time"

    outcome = transport_module.HerdrTransport(
        socket_path=str(address),
        expected_peer=transport_module.PeerIdentity(
            pid=os.getpid(), uid=os.getuid(), starttime=starttime
        ),
        timeout_seconds=0.5,
        monotonic=_fake_clock(readings=[0.0, 0.0, 100.0]),
    ).request(
        request_id=REQUEST_ID,
        method=protocol.METHOD_PANE_PROCESS_INFO,
        params={"pane_id": "w1:p2"},
        expect=protocol.ReplyExpectation(
            result_type=PROCESS_INFO_TYPE, required_fields=("process_info",)
        ),
    )

    assert outcome.ok is False
    assert outcome.timed_out is True
    assert outcome.request_sent is False, (
        "a deadline exhausted during peer identification must refuse BEFORE the "
        "write, so the caller's `request_sent` claim stays true"
    )
    # The peer WAS identified, so the refusal names a known generation rather
    # than an anonymous socket — the connect itself was inside the deadline.
    assert outcome.peer is not None
    time.sleep(0.2)
    assert received == [], "nothing may cross the socket after the deadline expires"


def test_a_target_pid_that_is_not_a_plain_ascii_integer_is_refused_not_raised():
    """A server-pid field is ASCII decimal within a pid's length, or the target is refused.

    All three cases are decided by one predicate, and the FIRST is the quiet one:
    an Arabic-Indic numeral satisfies `str.isdigit`, so it was accepted and
    silently resolved to a pid whose decimal spelling is not the field's bytes —
    two different durable coordinates aliasing one generation, which is exactly
    what qualification exists to prevent. The other two escaped as `ValueError`.
    """
    identity = _module(name="herdr_identity")
    cases = {
        "a non-ASCII decimal numeral": "١٢٣",
        "a digit-ish character that is not a number": "²",
        "a numeral past the integer-string conversion limit": "9" * 5000,
    }

    for defect, pid_field in cases.items():
        decoding = identity.decode_target(value=_encoded_target(pid_field=pid_field))
        assert decoding.backend == "", f"a server pid that is {defect} was accepted"
        assert decoding.herdr is None, f"a server pid that is {defect} yielded a target"
        assert decoding.error != "", f"a server pid that is {defect} was refused silently"


def test_a_small_deeply_nested_reply_is_refused_rather_than_overflowing():
    """Nesting is bounded SEPARATELY from size, because the two are unrelated.

    A thousand opening brackets is about two kilobytes — a two-hundredth of the
    reply size bound — so the size guard never sees it, and `json.loads` raises
    `RecursionError`, which is not a `ValueError` and so escaped the parse's
    refusal. A peer that sends this is not speaking the protocol; that is the
    fail-closed case.
    """
    protocol = _module(name="herdr_protocol")
    depth = 1000
    raw = b'{"id":"' + REQUEST_ID.encode("utf-8") + b'","result":' + b"[" * depth + b"]" * depth
    raw += b"}"
    assert len(raw) < protocol.MAX_REPLY_BYTES, "this payload must be well inside the size bound"

    reading = protocol.read_reply(
        raw=raw, request_id=REQUEST_ID, expect=protocol.ReplyExpectation()
    )

    assert reading.ok is False
    assert reading.result == {}
    assert reading.error != ""


def test_a_repeated_member_name_in_a_reply_is_refused_rather_than_collapsed():
    """No parser may choose either duplicate value, at either envelope level.

    `SPECIFICATION/scenarios.md` section "Duplicate JSON member names are never
    silently collapsed" states the rule; the measured behaviour was last-wins, so
    a peer could present a usable `result` whose required field carried a value
    the caller never saw the alternative to.
    """
    protocol = _module(name="herdr_protocol")
    expect = protocol.ReplyExpectation(
        result_type=PROCESS_INFO_TYPE, required_fields=("process_info",)
    )
    good = f'{{"type":"{PROCESS_INFO_TYPE}","process_info":{{"shell_pid":1}}}}'
    cases = {
        "a repeated result member": (
            f'{{"id":"{REQUEST_ID}","result":{{"type":"{PROCESS_INFO_TYPE}",'
            '"process_info":{"shell_pid":1},"process_info":{"shell_pid":2}}}'
        ),
        "a repeated envelope member": f'{{"id":"{REQUEST_ID}","result":{good},"result":{good}}}',
        "a repeated member nested inside the result": (
            f'{{"id":"{REQUEST_ID}","result":{{"type":"{PROCESS_INFO_TYPE}",'
            '"process_info":{"shell_pid":1,"shell_pid":2}}}'
        ),
    }

    for defect, text in cases.items():
        reading = protocol.read_reply(
            raw=text.encode("utf-8"), request_id=REQUEST_ID, expect=expect
        )
        assert reading.ok is False, f"a reply carrying {defect} was accepted"
        assert reading.result == {}, f"a reply carrying {defect} yielded a result"
        assert reading.error != "", f"a reply carrying {defect} was refused silently"
