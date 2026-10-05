"""Ownership and identity refusals the observation adapter was MISSING.

Independent review of the observation adapter found four ways it turned an
unusable reply into affirmative evidence. All four are reproduced here against
the adapter as it stood, with a scripted transport and no native mutation:

  1. **Non-positive process identities were accepted as a live shell.** A reply
     with `shell_pid` 0 and `foreground_process_group_id` 0, carrying a `bash`
     entry, parsed into a `ForegroundProcess` — and because its shell pid EQUALS
     its group id, that is precisely the shape the daemon reads as "idle at the
     prompt". There is no process 0; this is a malformed reply wearing the
     costume of the most consequential reading the adapter produces.
  2. **A contradictory duplicate group leader was resolved by LIST ORDER.** Two
     entries both claiming the group id, with different names and cwds, returned
     whichever came first: `name='real'` in one order and `name='imposter'` in
     the other. The leader-selection rule exists precisely so order does not
     decide, so a duplicate defeats it rather than being an edge case of it.
  3. **Empty identifiers enumerated as a pane.** `pane_rows` accepted
     `{"pane_id": "", "tab_id": "", "workspace_id": ""}` as a row, manufacturing
     a pane with no identity at all.
  4. **The payload's own `pane_id` was DISCARDED, so a reply could answer about
     another pane.** With `w1:p1` requested and a correct request id, a payload
     echoing `w1:p999` returned `ok=True` and `text='WRONG PANE'`; a payload
     carrying no `pane_id` returned `ok=True` and `text='NO OWNERSHIP'`; and the
     process reading returned a `ForegroundProcess` belonging to the other pane.
     `SPECIFICATION/contracts.md` requires a backend operation to identify the
     actual target, and matching only the request id proves the reply answers
     THIS REQUEST, not that it describes THIS PANE.

**Where each guard belongs is itself part of the finding.** The pane-ownership
check lives on the BOUND adapter, where the requested target is known, and not
inside `foreground_process` — that function is a field parser with no notion of
a requested pane, and two already-frozen fixtures call it on payloads that carry
no `pane_id` at all. Tightening it to demand one would have broken them and
would have been the wrong seam regardless. The identity and duplicate checks DO
belong in the parser, because they are judgements about the reply's own internal
consistency.

Driven over a REAL AF_UNIX socket served by this process, so the peer
credentials and `/proc` start time are genuine; only the REPLIES are scripted,
which is the only way to present a correctly-addressed reply that lies about its
own pane.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import claude_sessions
import pytest

__all__: list[str] = []

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "overseer"
CALLS_PATH = PACKAGE_DIR / "herdr_calls.py"
ADAPTER_PATH = PACKAGE_DIR / "herdr_adapter.py"

PANE = "w1:p1"
FOREIGN_PANE = "w1:p999"


def _modules() -> tuple[Any, Any]:
    for path in (CALLS_PATH, ADAPTER_PATH):
        assert path.is_file(), f"the observation adapter needs {path.name}"
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


def _serve(*, address: Path, bodies: list[bytes]) -> None:
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(address))
    listener.listen(8)

    def run() -> None:
        listener.settimeout(5.0)
        for body in bodies:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            with conn:
                conn.settimeout(5.0)
                buffered = b""
                try:
                    while not buffered.endswith(b"\n"):
                        chunk = conn.recv(65536)
                        if not chunk:
                            break
                        buffered += chunk
                    conn.sendall(body + b"\n")
                except OSError:
                    return
        listener.close()

    threading.Thread(target=run, daemon=True).start()


def _ids(*, count: int) -> Iterator[str]:
    return (f"own-{index}" for index in range(1, count + 1))


def _bodies(*, results: list[dict[str, object]]) -> list[bytes]:
    return [
        json.dumps({"id": f"own-{index}", "result": result}).encode("utf-8")
        for index, result in enumerate(results, start=1)
    ]


def _target(*, identity: Any, address: Path) -> Any:
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None, "this process must have a readable /proc start time"
    return identity.HerdrPaneTarget(
        socket_path=str(address),
        server_pid=os.getpid(),
        server_starttime=starttime,
        pane_id=PANE,
    )


def _process_info(
    *, pane_id: str | None, shell_pid: int, group: int, name: str
) -> dict[str, object]:
    info: dict[str, object] = {
        "shell_pid": shell_pid,
        "foreground_process_group_id": group,
        "foreground_processes": [{"pid": group, "name": name, "cmdline": name, "cwd": "/x"}],
    }
    if pane_id is not None:
        info["pane_id"] = pane_id
    return {"type": "pane_process_info", "process_info": info}


def _read(*, pane_id: str | None, text: str) -> dict[str, object]:
    read: dict[str, object] = {"source": "visible", "format": "ansi", "text": text}
    if pane_id is not None:
        read["pane_id"] = pane_id
    return {"type": "pane_read", "read": read}


def test_a_non_positive_process_identity_is_not_a_live_shell():
    """There is no process 0, and a reply claiming one must not read as idle.

    The zero/zero case is the dangerous one and the reason this is not cosmetic:
    `shell_pid == foreground_process_group_id` is exactly how the adapter reports
    "the shell itself owns the foreground", which is the idle reading the daemon
    acts on. A malformed reply must not be able to synthesize it.

    The LEADER's own pid needs no separate case: the leader is selected by its
    pid equalling the foreground group id, so a non-positive leader pid is only
    reachable through a non-positive group id, which these cases already cover.
    A test naming the leader's pid specifically could not isolate it.
    """
    calls, _adapter = _modules()
    cases = {
        "a zero shell pid and group": (0, 0),
        "a negative shell pid and group": (-1, -1),
        "a zero foreground group": (5, 0),
        "a negative foreground group": (5, -7),
        "a zero shell pid under a live group": (0, 5),
    }

    for defect, (shell, group) in cases.items():
        reading = calls.foreground_process(
            result=_process_info(pane_id=PANE, shell_pid=shell, group=group, name="bash")
        )
        assert reading is None, f"{defect} was accepted as a process identity: {reading}"


def test_a_duplicate_process_identity_is_refused_in_either_order():
    """Two entries cannot share one pid, so a reply saying they do is malformed.

    Asserted in BOTH orders, because the defect was that order decided the
    answer: one order yielded `real`, the reverse yielded `imposter`. Refusing
    outright is the only resolution that does not depend on ordering, and a
    server cannot legitimately report one pid twice.
    """
    calls, _adapter = _modules()
    contradictory = [
        {"pid": 42, "name": "real", "cmdline": "real", "cwd": "/a"},
        {"pid": 42, "name": "imposter", "cmdline": "imposter", "cwd": "/b"},
    ]

    for order, processes in (
        ("leader first", contradictory),
        ("leader second", list(reversed(contradictory))),
    ):
        reading = calls.foreground_process(
            result={
                "process_info": {
                    "pane_id": PANE,
                    "shell_pid": 10,
                    "foreground_process_group_id": 42,
                    "foreground_processes": processes,
                }
            }
        )
        assert reading is None, f"{order}: a duplicated pid resolved to {reading}"


def test_a_duplicate_pid_that_is_not_the_leader_is_also_refused():
    """The reply's internal consistency is judged as a whole, not just at the leader.

    A list that repeats a non-leader pid is malformed for the same reason, and
    accepting it would mean the adapter trusts a reply it can already see is
    self-contradictory.
    """
    calls, _adapter = _modules()

    reading = calls.foreground_process(
        result={
            "process_info": {
                "pane_id": PANE,
                "shell_pid": 10,
                "foreground_process_group_id": 42,
                "foreground_processes": [
                    {"pid": 77, "name": "a"},
                    {"pid": 77, "name": "b"},
                    {"pid": 42, "name": "leader"},
                ],
            }
        }
    )

    assert reading is None


def test_a_pane_row_with_an_empty_identifier_is_not_a_pane():
    """An empty id identifies nothing, so a row carrying one is not a pane.

    Each of the three ids is checked separately: the earlier behaviour accepted a
    row whose every identifier was empty, which is a pane the daemon could then
    try to address.
    """
    calls, _adapter = _modules()
    cases = {
        "an empty pane id": {"pane_id": "", "tab_id": "w1:t1", "workspace_id": "w1"},
        "an empty tab id": {"pane_id": PANE, "tab_id": "", "workspace_id": "w1"},
        "an empty workspace id": {"pane_id": PANE, "tab_id": "w1:t1", "workspace_id": ""},
        "every id empty": {"pane_id": "", "tab_id": "", "workspace_id": ""},
    }

    for defect, row in cases.items():
        assert calls.pane_rows(result={"panes": [row]}) is None, f"{defect} was enumerated"


def test_a_capture_whose_payload_names_another_pane_is_refused(*, socket_dir: Path):
    """A correct request id proves the reply answers this REQUEST, not this PANE.

    The measured `pane.read` reply echoes `read.pane_id`, so the requested pane
    can be checked against what the server says it answered about. Without that
    check a reply about another pane returned `ok=True` and its text.
    """
    _calls, adapter_module = _modules()
    identity = importlib.import_module("herdr_identity")
    address = socket_dir / "h.sock"
    _serve(
        address=address,
        bodies=_bodies(
            results=[
                _read(pane_id=FOREIGN_PANE, text="WRONG PANE"),
                _read(pane_id=None, text="NO OWNERSHIP"),
            ]
        ),
    )
    adapter = adapter_module.HerdrAdapter(request_ids=_ids(count=2))
    target = _target(identity=identity, address=address)

    foreign = adapter.capture_pane(target=target)
    unowned = adapter.capture_pane(target=target)

    assert foreign.ok is False, "a capture of another pane was accepted"
    assert foreign.text == "", f"foreign pane text leaked: {foreign.text!r}"
    assert PANE in foreign.error and FOREIGN_PANE in foreign.error, foreign.error
    assert unowned.ok is False, "a capture with no pane ownership was accepted"
    assert unowned.text == ""
    assert PANE in unowned.error, unowned.error


def test_a_process_reading_whose_payload_names_another_pane_is_refused(*, socket_dir: Path):
    """The same guard on the reading the restart interlock would depend on."""
    _calls, adapter_module = _modules()
    identity = importlib.import_module("herdr_identity")
    address = socket_dir / "h.sock"
    _serve(
        address=address,
        bodies=_bodies(
            results=[
                _process_info(pane_id=FOREIGN_PANE, shell_pid=11, group=22, name="OTHERPANE"),
                _process_info(pane_id=None, shell_pid=11, group=22, name="UNOWNED"),
            ]
        ),
    )
    adapter = adapter_module.HerdrAdapter(request_ids=_ids(count=2))
    target = _target(identity=identity, address=address)

    foreign = adapter.foreground(target=target)
    unowned = adapter.foreground(target=target)

    assert foreign.ok is False, "a process reading for another pane was accepted"
    assert foreign.process is None, f"foreign process leaked: {foreign.process}"
    assert PANE in foreign.error and FOREIGN_PANE in foreign.error, foreign.error
    assert unowned.ok is False
    assert unowned.process is None
    assert PANE in unowned.error, unowned.error


def test_a_payload_that_does_echo_the_requested_pane_is_still_accepted(*, socket_dir: Path):
    """The positive control, so the ownership guard is not simply refusing everything.

    Without this, every assertion above would also pass against an adapter that
    had stopped working, which is the way an over-tightened guard hides.
    """
    _calls, adapter_module = _modules()
    identity = importlib.import_module("herdr_identity")
    address = socket_dir / "h.sock"
    _serve(
        address=address,
        bodies=_bodies(
            results=[
                _read(pane_id=PANE, text="MINE"),
                _process_info(pane_id=PANE, shell_pid=11, group=22, name="sleep"),
            ]
        ),
    )
    adapter = adapter_module.HerdrAdapter(request_ids=_ids(count=2))
    target = _target(identity=identity, address=address)

    capture = adapter.capture_pane(target=target)
    reading = adapter.foreground(target=target)

    assert capture.ok is True, capture.error
    assert capture.text == "MINE"
    assert reading.ok is True, reading.error
    assert reading.process is not None
    assert reading.process.name == "sleep"
    assert reading.process.process_group_id == 22
