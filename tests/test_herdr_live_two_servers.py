"""TWO live herdr servers, both holding a pane called `w1:p1`, kept apart.

Herdr pane ids are unique only WITHIN a server (measured: a fresh server's root
pane is `w1:p1` every time), so the bare id an operator sees is ambiguous across
instances. `SPECIFICATION/contracts.md` requires a backend operation to identify
the actual backend INSTANCE as well as the target, and
`SPECIFICATION/constraints.md` requires instance identity to include the live
server generation. Those two rules exist for exactly the situation staged here.

**This is the live counterpart to `tests/test_herdr_pane_identity.py`.** That
file proves the ENCODING keeps two instances distinct — a pure, deterministic
property of the coordinate. It cannot prove that the ADAPTER actually routes by
that coordinate, because it never opens a socket. Here two REAL servers run at
once with deliberately different content in their identically-named panes, so a
read that went to the wrong instance returns the wrong text rather than merely
comparing unequal in a dataclass.

The failure this guards against is silent and plausible: an adapter that
remembered a generation, or that addressed panes by bare id, would answer every
question about `w1:p1` from whichever server happened to be reachable, and
every answer would look well-formed.
"""

from __future__ import annotations

import importlib
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import claude_sessions
import pytest
from herdr_live_server import (
    create_workspace,
    raw_request,
    start_server,
    stop_server,
    unique_session,
)

__all__: list[str] = []

MARKER_TIMEOUT = 15.0
PANE_CWD = "/tmp"

# Each server's pane prints a marker naming ITSELF, so a cross-read is visible
# as the wrong word rather than as an absence.
MARKERS = {"alpha": "OVSERVERALPHA", "beta": "OVSERVERBETA"}


@dataclass(frozen=True, kw_only=True)
class LiveServer:
    """One live herdr server child, its socket, its root pane and its marker."""

    name: str
    session: str
    socket_path: str
    server_pid: int
    pane_id: str
    marker: str


def _await_marker(*, server: LiveServer) -> None:
    """Wait until the pane's own marker is on screen, so a capture is meaningful.

    **This wait used to be a silent 15-second sleep per server.** Its `pane.read`
    omitted the protocol's required `source` field, so herdr answered every poll
    with "invalid_request: missing field source" (measured 2026-10-12, herdr
    0.9.3), the marker was never seen, and the loop simply fell out at its bound and
    returned — 2 x 15 s = the ~30.5 s of setup every test in this file paid. It now
    asks a well-formed question and FAILS by name if the marker never appears.
    """
    deadline = time.monotonic() + MARKER_TIMEOUT
    reply: dict[str, Any] = {}
    while time.monotonic() < deadline:
        reply = raw_request(
            socket_path=server.socket_path,
            method="pane.read",
            params={
                "pane_id": server.pane_id,
                "source": "visible",
                "format": "text",
                "strip_ansi": True,
            },
        )
        text = str(reply.get("result", {}).get("read", {}).get("text", ""))
        if server.marker in text:
            return
        time.sleep(0.05)
    pytest.fail(
        f"{server.name} pane {server.pane_id!r} never showed {server.marker!r} within "
        f"{MARKER_TIMEOUT}s; last reply: {reply!r}"
    )


def _start_server(*, name: str, session: str, scratch: Path) -> LiveServer:
    """Spawn one request-proven herdr server and print this server's marker in its pane."""
    started = start_server(scratch=scratch, session=session, log_name=f"{name}.log")
    server = LiveServer(
        name=name,
        session=session,
        socket_path=started.socket_path,
        server_pid=started.server_pid,
        pane_id=create_workspace(socket_path=started.socket_path, label=session, cwd=PANE_CWD),
        marker=MARKERS[name],
    )
    _ = raw_request(
        socket_path=server.socket_path,
        method="pane.send_input",
        params={
            "pane_id": server.pane_id,
            "text": f"printf '{server.marker}\\n'",
            "keys": ["Enter"],
        },
    )
    _await_marker(server=server)
    return server


@pytest.fixture(name="pair", scope="module")
def _pair(*, tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[LiveServer, LiveServer]]:
    """ONE pair of servers for the whole module: every test here only READS them.

    Nothing below writes to a pane, stops a server or changes server-wide state, so
    starting a fresh pair per test bought no isolation — only two more servers.
    """
    scratch = tmp_path_factory.mktemp("two-servers")
    names = {name: unique_session(label=name) for name in MARKERS}
    started: list[LiveServer] = []
    try:
        for name, session in names.items():
            started.append(_start_server(name=name, session=session, scratch=scratch))
        assert started[0].pane_id == started[1].pane_id, (
            "this test is only meaningful while both servers name their root pane "
            f"identically; got {started[0].pane_id} and {started[1].pane_id}"
        )
        yield (started[0], started[1])
    finally:
        for session in names.values():
            stop_server(session=session)


def _target(*, identity: Any, server: LiveServer) -> Any:
    starttime = claude_sessions.proc_starttime(pid=server.server_pid)
    assert starttime is not None, "a live herdr server must have a readable start time"
    return identity.HerdrPaneTarget(
        socket_path=server.socket_path,
        server_pid=server.server_pid,
        server_starttime=starttime,
        pane_id=server.pane_id,
    )


def _adapter() -> Any:
    return importlib.import_module("herdr_adapter").HerdrAdapter()


def test_each_server_s_identically_named_pane_reads_only_its_own_content(
    *, pair: tuple[LiveServer, LiveServer]
):
    """Same pane id, two live servers, two different answers — each the right one."""
    identity = importlib.import_module("herdr_identity")
    adapter = _adapter()
    alpha, beta = pair

    first = adapter.capture_pane(target=_target(identity=identity, server=alpha))
    second = adapter.capture_pane(target=_target(identity=identity, server=beta))

    assert first.ok is True and second.ok is True, f"{first.error} / {second.error}"
    assert alpha.marker in first.text, first.text[-300:]
    assert beta.marker not in first.text, "alpha's capture leaked beta's pane"
    assert beta.marker in second.text, second.text[-300:]
    assert alpha.marker not in second.text, "beta's capture leaked alpha's pane"


def test_each_server_s_identically_named_pane_reports_its_own_process(
    *, pair: tuple[LiveServer, LiveServer]
):
    """The foreground reading is per-INSTANCE too, not merely the capture."""
    identity = importlib.import_module("herdr_identity")
    adapter = _adapter()
    alpha, beta = pair

    first = adapter.foreground(target=_target(identity=identity, server=alpha))
    second = adapter.foreground(target=_target(identity=identity, server=beta))

    assert first.ok is True and second.ok is True, f"{first.error} / {second.error}"
    assert first.process.pane_id == second.process.pane_id == alpha.pane_id
    assert (
        first.process.shell_pid != second.process.shell_pid
    ), "two distinct servers must not report the same shell for the same pane id"


def test_a_coordinate_naming_the_other_server_s_generation_is_refused(
    *, pair: tuple[LiveServer, LiveServer]
):
    """The socket and the generation must agree, or nothing is read.

    Alpha's socket with BETA's process generation is a coordinate that could
    only arise from a stale or mixed-up record, and it is the shape that would
    silently adopt the wrong instance if the adapter trusted the path alone.
    """
    identity = importlib.import_module("herdr_identity")
    alpha, beta = pair
    beta_starttime = claude_sessions.proc_starttime(pid=beta.server_pid)
    assert beta_starttime is not None
    crossed = identity.HerdrPaneTarget(
        socket_path=alpha.socket_path,
        server_pid=beta.server_pid,
        server_starttime=beta_starttime,
        pane_id=alpha.pane_id,
    )

    outcome = _adapter().capture_pane(target=crossed)

    assert outcome.ok is False
    assert outcome.text == ""
    assert "generation" in outcome.error, outcome.error


def test_the_two_instances_carry_different_instance_keys(*, pair: tuple[LiveServer, LiveServer]):
    """The durable key a mapping store would hold distinguishes them as well.

    Asserted on LIVE servers rather than on constructed values, so the key is
    shown to separate instances that genuinely coexist.
    """
    identity = importlib.import_module("herdr_identity")
    alpha, beta = pair

    first = identity.herdr_instance_key(target=_target(identity=identity, server=alpha))
    second = identity.herdr_instance_key(target=_target(identity=identity, server=beta))

    assert first != second
    assert alpha.pane_id not in first, "an instance key must not embed the pane"
