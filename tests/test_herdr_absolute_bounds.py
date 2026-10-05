"""The herdr boundary's two residual UNBOUNDED paths, each measured before this file.

`SPECIFICATION/contracts.md` requires a herdr backend response to be "bounded and
fail closed", and `SPECIFICATION/constraints.md` requires the supervision loop to
degrade rather than stall. The transport already carries ONE absolute deadline per
request and the parser already carries a reply SIZE and NESTING bound — and two
paths escape all of them, both found by independent read-only review of the
accepted work and both reproduced here against that accepted tree.

**1. The write carried a STALE timeout, so the absolute deadline was advisory.**
`socket.settimeout` is set once inside peer identification, BEFORE the connect,
from the budget remaining at that moment. Identification then does real work —
connect, `SO_PEERCRED`, a `/proc` read — and `sendall` inherits that original
value instead of what is actually left. Measured against the accepted tree with a
2.0s budget and identification consuming 1.6s: a blocked write returned at
**3.609s**, 1.8x its own deadline. The pre-write expiry guard does not cover this,
because the budget was not yet exhausted when the write began; what is wrong is
the SIZE of the window the write is then given. The remedy is to reset the
socket's timeout to the residual budget immediately before the attempted write,
and the uncertainty flags MUST survive it: the bytes were committed, so the
mutation's effect stays unknown.

**2. The nesting bound was enforced by a QUADRATIC scan, so a tiny frame burned
the CPU for minutes.** The bound itself was correct; its implementation blanked
string literals with an unanchored `re.sub`, and on an unterminated string of
escaped quotes the engine restarts and backtracks at every quote. Measured on the
accepted tree: 2 028 bytes 0.0163s, 4 028 bytes 0.0638s, 8 028 bytes 0.2514s —
quadrupling per doubling, so the 64 KB frame below takes about sixteen seconds and
a frame still inside the 1 MiB size bound takes hours. No socket deadline can
interrupt it: it is CPU work inside the daemon's own tick. The remedy is a
guaranteed-linear scan.

**The malformed frame is parsed in a CHILD PROCESS under a watchdog**, so the
suite neither hangs nor spends a core for minutes when this regresses. The child
`os._exit`s to skip `atexit`, which keeps the forked process from flushing a
coverage data file and racing the parent's.

The third test is a NON-REGRESSION guard rather than newly-driven behaviour: the
accepted tree already reads escapes correctly, and it is pinned here because the
remedy for defect 2 REPLACES the scanner that gets it right. It is stated plainly
rather than presented as Red-driven evidence.
"""

from __future__ import annotations

import importlib
import json
import multiprocessing
import os
import shutil
import socket
import tempfile
import threading
import time
from collections.abc import Iterator
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

import claude_sessions
import pytest

__all__: list[str] = []

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "overseer"
PROTOCOL_PATH = PACKAGE_DIR / "herdr_protocol.py"
TRANSPORT_PATH = PACKAGE_DIR / "herdr_transport.py"

REQUEST_ID = "overseer-bounds-1"

# The write-bound case, in whole seconds so the two outcomes cannot be confused.
# Accepted tree: ~3.6s (identification's 1.6s plus the write's inherited 2.0s).
# Remedied tree: ~2.0s (identification's 1.6s plus the residual 0.4s).
WRITE_BUDGET_SECONDS = 2.0
IDENTIFY_COST_SECONDS = 1.6
# Halfway between the two, so neither verdict depends on a tight margin.
WRITE_BOUND_SECONDS = 2.8
# Far past this host's AF_UNIX send buffer (`net.core.wmem_default` is 212 992),
# against a peer that accepts and never reads, so `sendall` genuinely blocks.
BLOCKING_PAYLOAD_BYTES = 8 * 1024 * 1024

# 32 000 escaped-quote pairs — a 64 KB frame, a sixteenth of the reply SIZE bound,
# which the measured quadratic scan needs about sixteen seconds for.
MALFORMED_PAIRS = 32_000
PARSE_WATCHDOG_SECONDS = 3.0


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


def _accept_and_never_read(*, address: Path) -> list[Any]:
    """A REAL AF_UNIX peer that accepts the connection and never reads a byte.

    That is what makes the write block rather than fail: the connection is
    genuinely established, `SO_PEERCRED` is genuine, and the send buffer simply
    fills. The accepted connection is held in the returned list so it is not
    garbage-collected mid-test, which would close it and turn the blocked write
    into an immediate reset.
    """
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(address))
    listener.listen(1)
    held: list[Any] = []

    def run() -> None:
        listener.settimeout(10.0)
        try:
            conn, _ = listener.accept()
        except OSError:
            return
        held.append(conn)
        time.sleep(10.0)
        conn.close()
        listener.close()

    threading.Thread(target=run, daemon=True).start()
    return held


def _malformed_frame() -> bytes:
    """A reply whose string literal never terminates, built only of escaped quotes.

    Well inside both the SIZE bound and the NESTING bound, so neither of the two
    existing guards is what must stop it.
    """
    return (
        b'{"id":"'
        + REQUEST_ID.encode("utf-8")
        + b'","result":{"text":"'
        + (b'\\"' * MALFORMED_PAIRS)
    )


def _read_reply_in_child(*, pipe: Connection, raw: bytes, request_id: str) -> None:
    """Parse `raw` in a forked child and report the outcome, then leave abruptly.

    `os._exit` skips `atexit`, so this forked child never flushes a coverage data
    file — the race the repo's no-subprocess-spawn rule exists to prevent. It is
    reached only on the success path; a child that is still scanning when the
    watchdog expires is killed by the parent instead.
    """
    protocol = importlib.import_module("herdr_protocol")
    started = time.monotonic()
    reading = protocol.read_reply(
        raw=raw, request_id=request_id, expect=protocol.ReplyExpectation()
    )
    pipe.send((reading.ok, reading.error, time.monotonic() - started))
    pipe.close()
    os._exit(0)


def test_the_write_is_bounded_by_the_residual_deadline_not_the_original_one(*, socket_dir: Path):
    """A slow identification must shrink the write's window, not leave it at full size.

    Real time and the real `socket` timeout throughout: this is a claim about the
    bound the kernel actually enforces on the write, so an injected clock would
    assert the arithmetic while leaving the socket on its stale value — exactly
    the defect. Identification is slowed by the one injected seam that does real
    work inside it, the `/proc` start-time read.
    """
    protocol, transport_module = _modules()
    address = socket_dir / "h.sock"
    held = _accept_and_never_read(address=address)
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None, "this process must have a readable /proc start time"

    def slow_starttime(*, pid: int) -> str | None:
        time.sleep(IDENTIFY_COST_SECONDS)
        return claude_sessions.proc_starttime(pid=pid)

    transport = transport_module.HerdrTransport(
        socket_path=str(address),
        expected_peer=transport_module.PeerIdentity(
            pid=os.getpid(), uid=os.getuid(), starttime=starttime
        ),
        timeout_seconds=WRITE_BUDGET_SECONDS,
        starttime_of=slow_starttime,
    )
    started = time.monotonic()
    outcome = transport.request(
        request_id=REQUEST_ID,
        method=protocol.METHOD_PANE_SEND_INPUT,
        params={"pane_id": "w1:p1", "text": "x" * BLOCKING_PAYLOAD_BYTES, "keys": []},
        expect=protocol.ReplyExpectation(),
    )
    elapsed = time.monotonic() - started

    assert outcome.ok is False
    assert outcome.timed_out is True
    assert elapsed < WRITE_BOUND_SECONDS, (
        f"the request took {elapsed:.3f}s against a {WRITE_BUDGET_SECONDS}s absolute "
        f"deadline, {IDENTIFY_COST_SECONDS}s of which went to peer identification: "
        "the write inherited the timeout set before the connect instead of the "
        "budget actually remaining, so the deadline is advisory"
    )
    # The bytes WERE committed, so narrowing the window must not narrow the
    # uncertainty: this is still a mutation whose effect is unknown.
    assert outcome.request_sent is True
    assert outcome.effect_unknown is True
    assert outcome.peer is not None
    # Also what keeps the accepted connection referenced for the test's life: were
    # it collected, the blocked write would become an immediate reset and this
    # would stop being a timeout measurement at all.
    assert len(held) == 1, "the peer must have accepted exactly one connection"


def test_a_malformed_frame_is_refused_in_bounded_time_rather_than_quadratically():
    """A 64 KB frame inside both existing bounds must not cost the daemon a tick.

    Run in a forked child under a watchdog because the regression is CPU-bound
    inside the parse: nothing the transport, the deadline or the size bound can
    reach. A still-running child IS the failure, and killing it is what keeps the
    cost of that failure bounded for the rest of the suite.
    """
    _ = _modules()
    frame = _malformed_frame()
    assert len(frame) < (1 << 20), "this frame must sit well inside the reply size bound"

    context = multiprocessing.get_context("fork")
    parent_end, child_end = context.Pipe(duplex=False)
    child = context.Process(
        target=_read_reply_in_child,
        kwargs={"pipe": child_end, "raw": frame, "request_id": REQUEST_ID},
    )
    child.start()
    child.join(timeout=PARSE_WATCHDOG_SECONDS)
    still_scanning = child.is_alive()
    if still_scanning:
        child.kill()
        child.join(timeout=10.0)

    assert not still_scanning, (
        f"a {len(frame)}-byte malformed frame was still being parsed after "
        f"{PARSE_WATCHDOG_SECONDS}s; the nesting bound is enforced by a scan that "
        "rescans on backtracking, so a frame inside every existing bound costs "
        "minutes of CPU that no deadline can interrupt"
    )
    assert parent_end.poll(), "the child must report its reading"
    ok, error, parse_seconds = parent_end.recv()
    assert ok is False, "an unterminated string is not a usable reply"
    assert error != "", "the refusal must name its defect"
    assert parse_seconds < PARSE_WATCHDOG_SECONDS


def test_the_nesting_bound_reads_escapes_so_a_bracket_in_a_string_is_not_structure():
    """NON-REGRESSION GUARD — the accepted tree already passes this.

    It is pinned because the remedy for the quadratic scan REPLACES the thing that
    currently gets this right, and the two directions fail in opposite ways. An
    escape-blind scan reads `\\"` as closing the string, so brackets that are
    TEXT become structure and a legitimate ANSI pane capture — which carries
    brackets, quotes and backslashes by the thousand — is refused. The reverse
    case is the one a reader expects less: an escaped BACKSLASH does close the
    string, so nesting after it is real and must still be caught.
    """
    protocol, _transport = _modules()
    expect = protocol.ReplyExpectation()
    deep = "[" * (protocol.MAX_REPLY_NESTING + 6)
    accepted: dict[str, str] = {
        "brackets and braces inside a captured string": '{"text":"\\u001b[2mDIM [[[ {{{ "}',
        "an escaped quote then brackets, all inside the string": f'{{"text":"q\\"{deep}"}}',
        "an escaped backslash at the end of a string": '{"text":"trail\\\\"}',
    }
    for defect, body in accepted.items():
        raw = f'{{"id":"{REQUEST_ID}","result":{body}}}'.encode()
        assert json.loads(raw.decode("utf-8"))["result"], f"{defect} must be valid JSON"
        reading = protocol.read_reply(raw=raw, request_id=REQUEST_ID, expect=expect)
        assert reading.ok is True, (
            f"{defect} was refused; brackets inside a string literal are text, and "
            f"an ANSI capture is full of them — {reading.error}"
        )

    # The mirror image: the escaped backslash CLOSES the string, so what follows
    # is genuine structure and the bound must still fire.
    past_bound = (
        f'{{"id":"{REQUEST_ID}","result":{{"text":"path\\\\","deep":'
        f"{deep}{']' * (protocol.MAX_REPLY_NESTING + 6)}}}}}"
    )
    reading = protocol.read_reply(
        raw=past_bound.encode("utf-8"), request_id=REQUEST_ID, expect=expect
    )
    assert reading.ok is False, "real nesting past the bound must be refused"
    assert "nests deeper" in reading.error
