"""The native herdr adapter's contract, DETERMINISTICALLY — no herdr binary needed.

The companion to `tests/test_herdr_live_observation.py`, and the reason both
exist. That file proves the adapter against a real herdr server and SKIPS where
herdr is absent; this repository's CI container
(`ghcr.io/thewoolleyman/livespec-fabro-sandbox:python-v1.64.1`,
`.github/workflows/ci.yml`) does not ship herdr, so on that lane the live file
contributes nothing at all. The coverage gate is unchanged there and must still
be met, so EVERY line and branch of the adapter and its pure call layer is
exercised here, with no herdr installed and nothing skipped.

The two files are not redundant and neither substitutes for the other:

  - **This file pins the CONTRACT** — the wire params, the reply expectations,
    the parse of each measured reply shape, and every fail-closed refusal. It
    can cover refusals a real server cannot be made to produce (a well-formed
    envelope whose payload is unreadable), and it runs anywhere.
  - **The live file pins the PREMISE** — that the shapes asserted here are the
    shapes herdr 0.9.3 actually sends, and that a real pane really does report
    its foreground child. A green run here against invented shapes would prove
    only self-consistency.

Every reply payload below is COPIED from a measurement taken against a live
`herdr --session … server` on this host, recorded in
`tests/test_herdr_live_observation.py`'s module docstring and in
`plan/herdr-overseer/research/002-herdr-api-evidence.md` — including the
`shell_pid` 143934 / `foreground_process_group_id` 143978 pair and the dim SGR
bytes. They are not hand-authored shapes.

The socket peer is REAL and is this very process, so `SO_PEERCRED` and the
`/proc` start time the adapter validates are genuine process evidence; only the
REPLIES are scripted. Module imports are function-local behind an assertion on
each expected module path, so this file collects and reaches a real assertion
rather than dying at collection time.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import tempfile
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import claude_sessions
import pytest

__all__: list[str] = []

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "overseer"
CALLS_PATH = PACKAGE_DIR / "herdr_calls.py"
ADAPTER_PATH = PACKAGE_DIR / "herdr_adapter.py"

PANE = "w1:p1"
# --- MEASURED payloads, copied verbatim from the live probes on this host ---
DIM_TEXT = "\x1b[0m\x1b[2mOVDIM\x1b[0m\r\nroot@fa0bc1fd1c85:/tmp# "
READ_RESULT: dict[str, object] = {
    "type": "pane_read",
    "read": {
        "pane_id": PANE,
        "workspace_id": "w1",
        "tab_id": "w1:t1",
        "source": "visible",
        "format": "ansi",
        "text": DIM_TEXT,
        "revision": 0,
        "truncated": False,
    },
}
LIST_RESULT: dict[str, object] = {
    "type": "pane_list",
    "panes": [
        {
            "pane_id": PANE,
            "terminal_id": "term_65d111d7416141",
            "workspace_id": "w1",
            "tab_id": "w1:t1",
            "focused": True,
            "cwd": "/tmp",
            "foreground_cwd": "/usr",
            "agent_status": "unknown",
            "revision": 0,
        }
    ],
}
PROCESS_INFO_RESULT: dict[str, object] = {
    "type": "pane_process_info",
    "process_info": {
        "pane_id": PANE,
        "shell_pid": 143934,
        "foreground_process_group_id": 143978,
        "foreground_processes": [
            {
                "pid": 143978,
                "name": "sleep",
                "argv": ["sleep", "120"],
                "cmdline": "sleep 120",
                "cwd": "/usr",
            }
        ],
    },
}


def _modules() -> tuple[Any, Any]:
    for path in (CALLS_PATH, ADAPTER_PATH):
        assert path.is_file(), (
            f"the native herdr observation adapter needs " f"{path.relative_to(PACKAGE_DIR.parent)}"
        )
    return (
        importlib.import_module("herdr_calls"),
        importlib.import_module("herdr_adapter"),
    )


@pytest.fixture(name="socket_dir")
def _socket_dir() -> Iterator[Path]:
    """A SHORT scratch directory, because an AF_UNIX address is capped near 108 bytes."""
    created = tempfile.mkdtemp(prefix="hrdr")
    yield Path(created)
    shutil.rmtree(created, ignore_errors=True)


def _answer_one(*, conn: socket.socket, body: bytes, received: list[bytes]) -> None:
    """Read ONE newline-terminated request off `conn` and answer it with `body`.

    A peer that connected and closed WITHOUT writing was refused before its
    request — a served refusal, not a dead listener. Answering it anyway would
    raise BrokenPipe and tear the listener down, so a LATER refusal on the same
    address would surface as `Connection refused` and hide the diagnostic the
    caller is actually asserting. Nothing is recorded for such a peer, which is
    what keeps a no-bytes-written assertion meaningful.
    """
    conn.settimeout(5.0)
    buffered = b""
    try:
        while not buffered.endswith(b"\n"):
            chunk = conn.recv(65536)
            if not chunk:
                break
            buffered += chunk
    except OSError:
        return
    if not buffered:
        return
    received.append(buffered)
    try:
        conn.sendall(body + b"\n")
    except OSError:
        return


def _serve(*, address: Path, bodies: list[bytes]) -> list[bytes]:
    """A REAL AF_UNIX peer answering `bodies` in order; returns the request record.

    One connection per reply, because the transport opens its own connection per
    request. The record lets a test assert the METHOD and PARAMS that actually
    crossed the socket rather than trusting the adapter's own account of them.
    """
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(address))
    listener.listen(8)
    received: list[bytes] = []

    def run() -> None:
        listener.settimeout(5.0)
        for body in bodies:
            try:
                conn, _ = listener.accept()
            except OSError:
                break
            with conn:
                _answer_one(conn=conn, body=body, received=received)
        listener.close()

    threading.Thread(target=run, daemon=True).start()
    return received


def _envelope(*, result: dict[str, object], request_id: str) -> bytes:
    return json.dumps({"id": request_id, "result": result}).encode("utf-8")


def _ids(*, prefix: str = "rq") -> Callable[[], Iterator[str]]:
    def make() -> Iterator[str]:
        return (f"{prefix}-{index}" for index in range(1, 64))

    return make


def _adapter(*, adapter_module: Any, **overrides: Any) -> Any:
    fields: dict[str, Any] = {"request_ids": _ids()()}
    fields.update(overrides)
    return adapter_module.HerdrAdapter(**fields)


def _live_target(*, identity: Any, address: Path, pane_id: str = PANE) -> Any:
    """A qualified target naming THIS process as the server generation."""
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None, "this process must have a readable /proc start time"
    return identity.HerdrPaneTarget(
        socket_path=str(address),
        server_pid=os.getpid(),
        server_starttime=starttime,
        pane_id=pane_id,
    )


def test_the_wire_params_and_expectations_are_the_measured_ones():
    """The pure call layer, asserted against what the live server was measured to want.

    `source=visible` is the default because the daemon reads what the pane is
    SHOWING, not its scrollback; `strip_ansi` is the inverse of the caller's
    retain flag rather than an independent knob, because a `format=ansi` reply
    with `strip_ansi=true` is a contradiction the caller should not be able to
    express.
    """
    calls, _adapter_module = _modules()

    styled = calls.read_params(pane_id=PANE, retain_ansi=True)
    plain = calls.read_params(pane_id=PANE, retain_ansi=False)

    assert styled == {
        "pane_id": PANE,
        "source": "visible",
        "format": "ansi",
        "strip_ansi": False,
    }
    assert plain["format"] == "text"
    assert plain["strip_ansi"] is True
    assert calls.list_params() == {}
    assert calls.process_info_params(pane_id=PANE) == {"pane_id": PANE}
    assert calls.EXPECT_READ.result_type == "pane_read"
    assert calls.EXPECT_READ.required_fields == ("read",)
    assert calls.EXPECT_LIST.result_type == "pane_list"
    assert calls.EXPECT_LIST.required_fields == ("panes",)
    assert calls.EXPECT_PROCESS_INFO.result_type == "pane_process_info"
    assert calls.EXPECT_PROCESS_INFO.required_fields == ("process_info",)


def test_the_measured_reply_shapes_parse_into_their_values():
    """Each parser against the exact payload the live server sent."""
    calls, _adapter_module = _modules()

    assert calls.visible_text(result=READ_RESULT) == DIM_TEXT
    rows = calls.pane_rows(result=LIST_RESULT)
    assert rows is not None
    assert len(rows) == 1
    assert rows[0].pane_id == PANE
    assert rows[0].tab_id == "w1:t1"
    assert rows[0].workspace_id == "w1"
    assert rows[0].cwd == "/tmp"
    assert rows[0].foreground_cwd == "/usr"
    assert rows[0].focused is True

    process = calls.foreground_process(result=PROCESS_INFO_RESULT)
    assert process is not None
    assert process.shell_pid == 143934
    assert process.process_group_id == 143978
    assert process.name == "sleep"
    assert process.cmdline == "sleep 120"
    assert process.cwd == "/usr"


def test_a_pane_row_missing_an_optional_path_reads_as_empty_not_absent():
    """A row is identified by its ids; its paths are reported, not required.

    herdr sends `cwd` and `foreground_cwd` on every measured row, but they are
    descriptive rather than identifying, so their absence must not discard a row
    whose identity is intact — that would hide a real pane.
    """
    calls, _adapter_module = _modules()

    rows = calls.pane_rows(
        result={
            "type": "pane_list",
            "panes": [{"pane_id": PANE, "tab_id": "w1:t1", "workspace_id": "w1"}],
        }
    )

    assert rows is not None
    assert rows[0].cwd == ""
    assert rows[0].foreground_cwd == ""
    assert rows[0].focused is False


def test_every_unreadable_result_payload_parses_to_nothing():
    """Fail-closed at the PURE layer, so no caller can read a shape as data.

    `SPECIFICATION/contracts.md` forbids treating an unsupported or malformed
    backend response as proof of an idle pane. These shapes all pass the
    envelope's `required_fields` gate — the named member is present — and are
    still unusable, which is precisely the gap a required-fields check leaves.
    """
    calls, _adapter_module = _modules()

    assert calls.visible_text(result={"read": "not an object"}) is None
    assert calls.visible_text(result={"read": {"text": 5}}) is None
    assert calls.pane_rows(result={"panes": "not a list"}) is None
    assert calls.pane_rows(result={"panes": ["not an object"]}) is None
    assert calls.pane_rows(result={"panes": [{"tab_id": "w1:t1", "workspace_id": "w1"}]}) is None

    assert calls.foreground_process(result={"process_info": "not an object"}) is None
    for defect, info in {
        "a non-integer shell pid": {"shell_pid": "x", "foreground_process_group_id": 2},
        "a boolean shell pid": {"shell_pid": True, "foreground_process_group_id": 2},
        "a non-integer process group": {"shell_pid": 1, "foreground_process_group_id": "x"},
        "no foreground process list": {"shell_pid": 1, "foreground_process_group_id": 2},
        "a non-list foreground set": {
            "shell_pid": 1,
            "foreground_process_group_id": 2,
            "foreground_processes": "x",
        },
        "an empty foreground set": {
            "shell_pid": 1,
            "foreground_process_group_id": 2,
            "foreground_processes": [],
        },
        "a non-object foreground entry": {
            "shell_pid": 1,
            "foreground_process_group_id": 2,
            "foreground_processes": ["x"],
        },
        "no entry owning the foreground group": {
            "shell_pid": 1,
            "foreground_process_group_id": 2,
            "foreground_processes": [{"pid": 99, "name": "other"}],
        },
        "a group leader with no name": {
            "shell_pid": 1,
            "foreground_process_group_id": 2,
            "foreground_processes": [{"pid": 2}],
        },
    }.items():
        assert calls.foreground_process(result={"process_info": info}) is None, defect


def test_the_group_leader_is_selected_rather_than_the_first_listed_process():
    """Which entry is the foreground process must not depend on list ORDER.

    `plan/herdr-overseer/research/002-herdr-api-evidence.md` warns against
    reading "arbitrary process-list order"; the principled answer is the entry
    that OWNS the reported foreground process group, so a reply listing the
    leader second resolves identically. A reply with no such entry is ambiguous
    and therefore unavailable, which the sibling test above pins.
    """
    calls, _adapter_module = _modules()

    process = calls.foreground_process(
        result={
            "process_info": {
                "shell_pid": 10,
                "foreground_process_group_id": 42,
                "foreground_processes": [
                    {"pid": 77, "name": "decoy", "cmdline": "decoy", "cwd": "/decoy"},
                    {"pid": 42, "name": "leader", "cmdline": "leader --go", "cwd": "/led"},
                ],
            }
        }
    )

    assert process is not None
    assert process.name == "leader"
    assert process.cmdline == "leader --go"
    assert process.cwd == "/led"


def test_a_group_leader_without_optional_detail_still_reports_its_identity():
    """Name and pids identify the process; cmdline and cwd are reported if sent."""
    calls, _adapter_module = _modules()

    process = calls.foreground_process(
        result={
            "process_info": {
                "shell_pid": 10,
                "foreground_process_group_id": 42,
                "foreground_processes": [{"pid": 42, "name": "bare"}],
            }
        }
    )

    assert process is not None
    assert process.name == "bare"
    assert process.cmdline == ""
    assert process.cwd == ""


def test_identification_learns_the_generation_without_mutating_anything(*, socket_dir: Path):
    """Identification is a read-only enumeration whose PEER is the answer.

    The transport reports the generation it validated on every outcome, so
    identification needs no probe method of its own — and must not invent a
    mutating one. The request that crosses the socket is asserted to be the
    enumeration, which is what makes "mutates nothing" checkable.
    """
    _calls, adapter_module = _modules()
    address = socket_dir / "h.sock"
    received = _serve(address=address, bodies=[_envelope(result=LIST_RESULT, request_id="rq-1")])

    identified = _adapter(adapter_module=adapter_module).identify(socket_path=str(address))

    assert identified.ok is True, identified.error
    assert identified.peer is not None
    assert identified.peer.pid == os.getpid()
    assert identified.peer.uid == os.getuid()
    assert len(received) == 1
    sent = json.loads(received[0].decode("utf-8"))
    assert sent["method"] == "pane.list"
    assert sent["params"] == {}


def test_an_unreachable_socket_is_an_identification_refusal(*, socket_dir: Path):
    _calls, adapter_module = _modules()

    identified = _adapter(adapter_module=adapter_module).identify(
        socket_path=str(socket_dir / "absent.sock")
    )

    assert identified.ok is False
    assert identified.peer is None
    assert identified.error != ""


def test_each_observation_addresses_the_qualified_target_and_parses_its_reply(*, socket_dir: Path):
    """The three observations, each over a real socket, asserted on the wire too.

    The params that cross the socket are checked because the adapter's job is
    precisely to turn a qualified coordinate into the right call: a capture that
    silently read the wrong pane, or read scrollback instead of the visible
    pane, would still return a plausible string.
    """
    _calls, adapter_module = _modules()
    identity = importlib.import_module("herdr_identity")
    target = _live_target(identity=identity, address=socket_dir / "h.sock")
    received = _serve(
        address=socket_dir / "h.sock",
        bodies=[
            _envelope(result=LIST_RESULT, request_id="rq-1"),
            _envelope(result=READ_RESULT, request_id="rq-2"),
            _envelope(result=READ_RESULT, request_id="rq-3"),
            _envelope(result=PROCESS_INFO_RESULT, request_id="rq-4"),
        ],
    )
    adapter = _adapter(adapter_module=adapter_module)

    listing = adapter.list_panes(target=target)
    styled = adapter.capture_pane(target=target)
    plain = adapter.capture_pane(target=target, retain_ansi=False)
    reading = adapter.foreground(target=target)

    assert listing.ok is True, listing.error
    assert [row.pane_id for row in listing.panes] == [PANE]
    assert styled.ok is True, styled.error
    assert styled.text == DIM_TEXT
    assert plain.ok is True, plain.error
    assert reading.ok is True, reading.error
    assert reading.process is not None
    assert reading.process.name == "sleep"

    methods = [json.loads(raw.decode("utf-8")) for raw in received]
    assert [one["method"] for one in methods] == [
        "pane.list",
        "pane.read",
        "pane.read",
        "pane.process_info",
    ]
    assert methods[1]["params"]["pane_id"] == PANE
    assert methods[1]["params"]["format"] == "ansi"
    assert methods[2]["params"]["format"] == "text"
    assert methods[3]["params"] == {"pane_id": PANE}
    # Distinct ids per request, which is what lets a mismatched reply be caught.
    assert len({one["id"] for one in methods}) == len(methods)


def test_a_well_formed_envelope_with_an_unreadable_payload_refuses_every_observation(
    *, socket_dir: Path
):
    """The refusal a real server cannot be made to produce, and the gap it closes.

    Each payload carries the member the expectation REQUIRES, so the envelope
    gate passes and only the adapter's own parse stands between it and a caller.
    A capture must not become `""`, a listing must not become `()`, and a
    foreground reading must not become a zero-pid process.
    """
    _calls, adapter_module = _modules()
    identity = importlib.import_module("herdr_identity")
    address = socket_dir / "h.sock"
    target = _live_target(identity=identity, address=address)
    _ = _serve(
        address=address,
        bodies=[
            _envelope(result={"type": "pane_list", "panes": "not a list"}, request_id="rq-1"),
            _envelope(result={"type": "pane_read", "read": 5}, request_id="rq-2"),
            _envelope(result={"type": "pane_process_info", "process_info": 5}, request_id="rq-3"),
        ],
    )
    adapter = _adapter(adapter_module=adapter_module)

    listing = adapter.list_panes(target=target)
    capture = adapter.capture_pane(target=target)
    reading = adapter.foreground(target=target)

    assert listing.ok is False and listing.panes == ()
    assert capture.ok is False and capture.text == ""
    assert reading.ok is False and reading.process is None
    for outcome in (listing, capture, reading):
        assert "unreadable" in outcome.error, outcome.error


def test_a_foreign_server_generation_refuses_every_observation(*, socket_dir: Path):
    """A coordinate bound to another generation reads nothing, on the same socket.

    The adapter builds the transport's expected peer from the TARGET, so this is
    the adapter's own guard rather than the transport's being exercised twice:
    getting it wrong would mean every call silently adopted whichever server
    happened to answer.
    """
    _calls, adapter_module = _modules()
    identity = importlib.import_module("herdr_identity")
    address = socket_dir / "h.sock"
    good = _live_target(identity=identity, address=address)
    foreign = identity.HerdrPaneTarget(
        socket_path=good.socket_path,
        server_pid=good.server_pid,
        server_starttime=good.server_starttime + "9",
        pane_id=good.pane_id,
    )
    # THREE connections, because the three observations below each open their own
    # and each must reach peer validation; one body would leave the later calls
    # racing a closed listener for a `Connection refused` instead of a refusal.
    received = _serve(
        address=address,
        bodies=[_envelope(result=LIST_RESULT, request_id=f"rq-{index}") for index in (1, 2, 3)],
    )
    adapter = _adapter(adapter_module=adapter_module)

    for name, outcome in (
        ("list", adapter.list_panes(target=foreign)),
        ("capture", adapter.capture_pane(target=foreign)),
        ("foreground", adapter.foreground(target=foreign)),
    ):
        assert outcome.ok is False, f"{name} accepted a foreign generation"
        assert "generation" in outcome.error, f"{name}: {outcome.error}"
    assert received == [], "nothing may be written to a server of the wrong generation"


def test_a_foreign_uid_is_refused_even_on_the_right_socket(*, socket_dir: Path):
    """The adapter's expected uid is part of the identity it validates.

    A socket served by another user's process is not this track's backend, and
    `expected_uid` is injectable only so that fact can be asserted; the daemon
    always takes its own uid.
    """
    _calls, adapter_module = _modules()
    identity = importlib.import_module("herdr_identity")
    address = socket_dir / "h.sock"
    target = _live_target(identity=identity, address=address)
    received = _serve(address=address, bodies=[_envelope(result=LIST_RESULT, request_id="rq-1")])

    outcome = _adapter(adapter_module=adapter_module, expected_uid=os.getuid() + 1).list_panes(
        target=target
    )

    assert outcome.ok is False
    assert "generation" in outcome.error
    assert received == []
