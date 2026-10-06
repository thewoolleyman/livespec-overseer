"""A pane whose shell is registered under an ALIAS name is still a retained shell.

Native regression for a refusal that fires on a perfectly healthy host. The
retained-shell gate requires the server's reported name and the kernel's
executable to describe one program, and it decided that by comparing BASENAMES.
On a Debian-family host `/bin/sh` is a symlink to `dash`, so a pane rooted at
`/bin/sh` reports `name='sh'` while `/proc/<pid>/exe` resolves to
`/usr/bin/dash` — two truthful answers about one process, and the comparison
read them as a contradiction:

    herdr calls shell 623375 'sh' while the kernel runs '/usr/bin/dash';
    one of the two is wrong

Neither source was wrong. `sh` is what the shell was INVOKED as and `dash` is
what the kernel RESOLVED it to, and this host registers `/bin/sh` in
`/etc/shells` — so it is a supported login shell by the system's own answer.

**Why it was never seen until a janitor run.** Herdr roots a pane at `$SHELL`
and falls back to `/bin/sh` when that variable is absent. An interactive
operator shell exports `SHELL=/bin/bash`, so every pane came up as `bash`,
whose name and resolved executable agree. A gate invocation has no login shell
and therefore no `$SHELL`, so every pane came up as `sh` and EVERY positive
layout case refused. Measured on this host:

    SHELL=/bin/bash   name='bash'  exe=/usr/bin/bash  -> basenames agree
    SHELL unset       name='sh'    exe=/usr/bin/dash  -> basenames disagree
    SHELL=/bin/sh     name='sh'    exe=/usr/bin/dash  -> basenames disagree

So each server here is launched with an EXPLICIT environment rather than
inheriting the ambient one. That is what makes the regression deterministic in
both directions: the sh-context test would pass by accident under an operator
shell, and the bash-context control would stop being a control.

**The fix must not become a blanket acceptance, so three of these four tests
bound it.** The alias table is the host's own shell register, and it is what
authorizes: an empty table and a table whose entry resolves to a DIFFERENT
binary must both still refuse the very same live pane. Only the registry may
mediate between a name and an executable; nothing here relaxes the rule that
one lying source refuses rather than decides.

Session isolation is herdr's own `--session` mechanism: every session name
carries this test process's pid, and teardown stops and deletes BY THAT EXACT
NAME, so no other session — including the operator's `default` — is touched.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

__all__: list[str] = []

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
LAUNCH_TIMEOUT = 20.0
PANE_CWD = "/tmp"
TOP_RATIO = 0.25

MARKER = "OVALIAS1"
LAUNCH_COMMAND = f"sleep 120 #{MARKER}"
LAUNCH_NAME = "sleep"
# A real binary that is emphatically not a shell, used to build an alias table
# that names the right shell and resolves to the wrong program.
NOT_A_SHELL = "/usr/bin/sleep"


@dataclass(frozen=True, kw_only=True)
class LiveServer:
    """One live herdr server child, its socket, its root pane and that pane's shell."""

    session: str
    socket_path: str
    server_pid: int
    root: str
    reported_name: str
    kernel_executable: str


def _socket_for(*, session: str) -> Path:
    return Path.home() / ".config" / "herdr" / "sessions" / session / "herdr.sock"


def _cli(*, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, *args], capture_output=True, text=True, timeout=60, check=False
    )


def _raw_request(*, socket_path: str, method: str, params: dict[str, object]) -> dict[str, Any]:
    """One raw round trip, used ONLY for setup and for control facts.

    Control evidence must not come from the surface under test, or the file
    would only prove the adapter is self-consistent.
    """
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(15.0)
    sock.connect(socket_path)
    sock.sendall(json.dumps({"id": "fixture", "method": method, "params": params}).encode() + b"\n")
    buffered = b""
    try:
        while not buffered.endswith(b"\n"):
            chunk = sock.recv(65536)
            if not chunk:
                break
            buffered += chunk
    finally:
        sock.close()
    parsed: dict[str, Any] = json.loads((buffered or b"{}").split(b"\n")[0])
    return parsed


def _process_info(*, socket_path: str, pane_id: str) -> dict[str, Any]:
    reply = _raw_request(
        socket_path=socket_path, method="pane.process_info", params={"pane_id": pane_id}
    )
    info: dict[str, Any] = reply["result"]["process_info"]
    return info


def _leader_name(*, info: dict[str, Any]) -> str:
    """The name the server gives the entry that OWNS the foreground group."""
    group_id = int(info["foreground_process_group_id"])
    named = [
        str(entry["name"])
        for entry in info["foreground_processes"]
        if int(entry["pid"]) == group_id
    ]
    assert len(named) == 1, f"the reply must name exactly one group leader: {info}"
    return named[0]


def _capture(*, socket_path: str, pane_id: str) -> str:
    reply = _raw_request(
        socket_path=socket_path,
        method="pane.read",
        params={"pane_id": pane_id, "source": "visible", "format": "text", "strip_ansi": True},
    )
    return str(reply["result"]["read"]["text"])


def _pane_ids(*, socket_path: str) -> list[str]:
    reply = _raw_request(socket_path=socket_path, method="pane.list", params={})
    return [str(pane["pane_id"]) for pane in reply["result"]["panes"]]


def _parent_pid_of(*, pid: int) -> int:
    """`pid`'s parent, read from `/proc` — the one place the lineage is a FACT.

    The comm field can contain spaces and parentheses, so the fields after it
    are taken from the LAST close parenthesis rather than by splitting the whole
    line.
    """
    stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    return int(stat[stat.rindex(")") + 1 :].split()[1])


def _await_foreground(*, socket_path: str, pane_id: str, name: str) -> dict[str, Any]:
    """Poll until `name` is `pane_id`'s foreground process, or the bound expires."""
    deadline = time.monotonic() + LAUNCH_TIMEOUT
    info = _process_info(socket_path=socket_path, pane_id=pane_id)
    while time.monotonic() < deadline:
        info = _process_info(socket_path=socket_path, pane_id=pane_id)
        if any(str(entry.get("name")) == name for entry in info.get("foreground_processes", [])):
            return info
        time.sleep(0.1)
    return info


def _start_server(*, session: str, scratch: Path, shell_path: str | None) -> LiveServer:
    """A server whose panes are rooted at `shell_path`, or at herdr's own fallback.

    The environment is built EXPLICITLY — `$SHELL` removed rather than merely
    left alone — because the whole subject of this file is which shell the pane
    comes up as, and inheriting the ambient value would make that the operator's
    choice rather than the test's.
    """
    environment = dict(os.environ)
    if shell_path is None:
        _ = environment.pop("SHELL", None)
    else:
        environment["SHELL"] = shell_path
    log_name = f"{session.rsplit('-', 1)[-1]}.log"
    log = (scratch / log_name).open("wb")
    child = subprocess.Popen(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, "--session", session, "server"],
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=str(scratch),
        env=environment,
    )
    address = _socket_for(session=session)
    deadline = time.monotonic() + SERVER_READY_TIMEOUT
    while time.monotonic() < deadline and not address.exists():
        time.sleep(0.1)
    log.close()
    assert address.exists(), (
        f"herdr session {session!r} never created {address}; "
        f"server log: {(scratch / log_name).read_text(errors='replace')[:500]}"
    )
    created = _raw_request(
        socket_path=str(address),
        method="workspace.create",
        params={"cwd": PANE_CWD, "label": session, "focus": False},
    )
    assert "result" in created, f"workspace.create failed: {created}"
    root = str(created["result"]["root_pane"]["pane_id"])
    info = _process_info(socket_path=str(address), pane_id=root)
    return LiveServer(
        session=session,
        socket_path=str(address),
        server_pid=child.pid,
        root=root,
        reported_name=_leader_name(info=info),
        kernel_executable=str(Path(f"/proc/{int(info['shell_pid'])}/exe").readlink().resolve()),
    )


def _serve(*, scratch: Path, label: str, shell_path: str | None) -> Iterator[LiveServer]:
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    session = f"overseer-test-{os.getpid()}-alias-{label}"
    server = _start_server(session=session, scratch=scratch, shell_path=shell_path)
    try:
        yield server
    finally:
        _ = _cli(args=["--session", session, "server", "stop"])
        _ = _cli(args=["session", "delete", session])


@pytest.fixture(name="alias_server")
def _alias_server(*, tmp_path: Path) -> Iterator[LiveServer]:
    """A server with NO `$SHELL`, so herdr roots its panes at `/bin/sh`."""
    yield from _serve(scratch=tmp_path, label="sh", shell_path=None)


@pytest.fixture(name="exact_server")
def _exact_server(*, tmp_path: Path) -> Iterator[LiveServer]:
    """A server with `SHELL=/bin/bash`, whose reported name needs no alias."""
    yield from _serve(scratch=tmp_path, label="bash", shell_path="/bin/bash")


def _split_top(*, server: LiveServer, command: str, **overrides: Any) -> Any:
    writer_module = importlib.import_module("herdr_write")
    identity = importlib.import_module("herdr_identity")
    claude_sessions = importlib.import_module("claude_sessions")
    starttime = claude_sessions.proc_starttime(pid=server.server_pid)
    assert starttime is not None, "the live herdr server must have a readable start time"
    return writer_module.HerdrWriter(**overrides).split_window_top(
        target=identity.HerdrPaneTarget(
            socket_path=server.socket_path,
            server_pid=server.server_pid,
            server_starttime=starttime,
            pane_id=server.root,
        ),
        cwd=PANE_CWD,
        command=command,
        ratio=TOP_RATIO,
    )


def _assert_alias_context(*, server: LiveServer) -> None:
    """The precondition is ASSERTED, never assumed: name and executable differ.

    If this host's `/bin/sh` were itself bash, the names would agree and the
    defect under test could not arise — so the condition is measured and the
    test skips rather than passing vacuously.
    """
    kernel_name = Path(server.kernel_executable).name
    if kernel_name == server.reported_name:
        pytest.skip(
            f"this host's fallback shell reports {server.reported_name!r} and resolves to "
            f"{server.kernel_executable!r}; there is no alias to mediate"
        )
    assert server.reported_name == "sh", (
        f"fixture precondition: a server with no $SHELL must root its panes at sh, "
        f"not {server.reported_name!r}"
    )
    assert Path("/etc/shells").is_file(), "fixture precondition: this host registers login shells"
    registered = {
        line.strip()
        for line in Path("/etc/shells").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    mediating = {
        entry
        for entry in registered
        if Path(entry).name == server.reported_name
        and os.path.realpath(entry) == server.kernel_executable
    }
    assert mediating, (
        f"fixture precondition: /etc/shells must register {server.reported_name!r} as a name for "
        f"{server.kernel_executable!r}; it registers {sorted(registered)}"
    )


def test_a_pane_rooted_at_an_alias_of_a_registered_shell_receives_the_launch(
    *, alias_server: LiveServer
):
    """The regression: a `/bin/sh` pane on a dash host is a retained shell.

    Driven through the adapter's own default readers, so the host's real
    `/etc/shells` and real `/proc` are what authorize the write — the same
    configuration a gate run uses. The launched process must be the SHELL'S
    child, which is what distinguishes a reusable retained-shell pane from one
    an `exec` launch would take down with its first command.
    """
    _assert_alias_context(server=alias_server)

    outcome = _split_top(server=alias_server, command=LAUNCH_COMMAND)

    assert outcome.ok is True, outcome.error
    info = _await_foreground(
        socket_path=alias_server.socket_path, pane_id=outcome.pane_id, name=LAUNCH_NAME
    )
    shell_pid = int(info["shell_pid"])
    assert (
        int(info["foreground_process_group_id"]) != shell_pid
    ), "the command must run UNDER the alias shell, not replace it"
    launched = [
        int(entry["pid"])
        for entry in info["foreground_processes"]
        if str(entry.get("name")) == LAUNCH_NAME
    ]
    assert len(launched) == 1, info
    assert _parent_pid_of(pid=launched[0]) == shell_pid, (
        f"the launched process {launched[0]} is not a child of the verified "
        f"retained shell {shell_pid}"
    )
    assert outcome.pane_id in _pane_ids(
        socket_path=alias_server.socket_path
    ), "the pane must survive its own first command"
    assert MARKER in _capture(socket_path=alias_server.socket_path, pane_id=outcome.pane_id)


def test_a_pane_whose_reported_name_needs_no_alias_still_receives_the_launch(
    *, exact_server: LiveServer
):
    """The bash-context control, so the sh case is not passing for harness reasons.

    This is the path that was already green under an operator shell. It is kept
    beside the alias case because the two differ in exactly one input — the
    server's `$SHELL` — and a fix that broke this one would be trading a
    refusal for a different refusal.
    """
    assert exact_server.reported_name == Path(exact_server.kernel_executable).name, (
        f"fixture precondition: {exact_server.reported_name!r} and "
        f"{exact_server.kernel_executable!r} must already agree without an alias"
    )

    outcome = _split_top(server=exact_server, command=LAUNCH_COMMAND)

    assert outcome.ok is True, outcome.error
    info = _await_foreground(
        socket_path=exact_server.socket_path, pane_id=outcome.pane_id, name=LAUNCH_NAME
    )
    launched = [
        int(entry["pid"])
        for entry in info["foreground_processes"]
        if str(entry.get("name")) == LAUNCH_NAME
    ]
    assert len(launched) == 1, info
    assert _parent_pid_of(pid=launched[0]) == int(info["shell_pid"])


def test_the_host_registry_is_what_authorizes_an_alias_and_nothing_else(
    *, alias_server: LiveServer
):
    """With no registered aliases, the very same live pane must still refuse.

    The bound that keeps the repair from being a relaxed name comparison. An
    empty table is the host declining to mediate, and the safe direction for a
    write is to refuse — so this drives the real sh pane, the real kernel
    reading, and an EMPTY alias table.
    """
    _assert_alias_context(server=alias_server)

    outcome = _split_top(server=alias_server, command=LAUNCH_COMMAND, shell_aliases=frozenset())

    assert outcome.ok is False, "an unmediated name disagreement must refuse the launch"
    assert outcome.effect_unknown is False, "the split was enumerated, so the layout is known"
    assert outcome.pane_id, "the created pane is reported so the partial layout can be re-observed"
    assert outcome.pane_id in _pane_ids(
        socket_path=alias_server.socket_path
    ), "a refusal must preserve the partial layout rather than tear it down"
    assert MARKER not in _capture(
        socket_path=alias_server.socket_path, pane_id=outcome.pane_id
    ), "a refused launch must deliver no command bytes"


def test_an_alias_naming_the_right_shell_but_the_wrong_binary_is_refused(
    *, alias_server: LiveServer
):
    """A registered name must resolve to the executable the KERNEL reports.

    The second bound, and the sharper one: the table names `sh`, exactly as the
    server does, but maps it to a program this pane is not running. Matching the
    name alone would accept it, which would reinstate the single-source trust
    the agreement rule exists to prevent.
    """
    _assert_alias_context(server=alias_server)

    outcome = _split_top(
        server=alias_server,
        command=LAUNCH_COMMAND,
        shell_aliases=frozenset({("sh", NOT_A_SHELL)}),
    )

    assert outcome.ok is False, "an alias resolving to another binary must not authorize the write"
    assert MARKER not in _capture(
        socket_path=alias_server.socket_path, pane_id=outcome.pane_id
    ), "a refused launch must deliver no command bytes"
