"""Postimplementation native proof for reply loss on the verified Herdr peer.

The original public-entrypoint Red remains frozen in
``test_overseer_start_public_herdr.py``.  This later strengthening closes a proof
gap in that exercise without rewriting its chronology: an AF_UNIX forwarding
proxy changes the peer whose credentials the ownership probe verifies.

The fault here lives at the installed client's reply boundary instead.  A
``sitecustomize`` fixture patches only ``HerdrTransport._send_and_read`` in the
genuine, non-editably installed ``overseer-start`` process.  The normal transport
still connects directly to the real Herdr socket, checks ``SO_PEERCRED``, sends
the real native mutation, and receives its reply.  Before the fixture withholds
that reply from product code, it opens a second direct connection to the same
socket, checks the peer generation again, and observes the created pane or exact
daemon process.  No product ownership check is weakened or bypassed.
"""

from __future__ import annotations

import itertools
import json
import os
import shlex
import shutil
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from test_herdr_live_observations import (
    PANE_CWD,
    pane_ids,
    process_info_reply,
    raw_request,
    read_foreground,
    run_in_pane,
    split_pane,
    start_owned_server,
    stop_owned_server,
)

from overseer import claude_sessions, runtime_prefix

__all__: list[str] = []

REPO_ROOT = Path(__file__).resolve().parent.parent
WAIT_SECONDS = 180.0
POLL_SECONDS = 0.2
_counter = itertools.count(1)


@dataclass(frozen=True, kw_only=True)
class LiveCase:
    session: str
    socket_path: str
    server_pid: int
    server_starttime: str
    invoking: str
    sibling: str
    invoking_shell: int
    sibling_shell: int
    sentinel_pid: int
    scratch: Path


def _foreground(*, case: LiveCase, pane: str) -> Any:
    reading = read_foreground(reply=process_info_reply(socket_path=case.socket_path, pane_id=pane))
    assert reading is not None
    return reading


def _await_named(*, case: LiveCase, pane: str, name: str) -> int:
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        reading = _foreground(case=case, pane=pane)
        named = reading.pids_named(name=name)
        if named and reading.group_id != reading.shell_pid:
            return named[0]
        time.sleep(POLL_SECONDS)
    pytest.fail(f"{name!r} never occupied {pane!r}")


@pytest.fixture
def live_case(*, tmp_path: Path) -> Iterator[LiveCase]:
    session = f"overseer-peer-loss-{os.getpid()}-{next(_counter)}"
    try:
        owned = start_owned_server(session=session, scratch=tmp_path, cwd=PANE_CWD)
        sibling = split_pane(
            socket_path=owned.socket_path,
            pane_id=owned.root,
            direction="down",
            ratio=0.5,
        )
        run_in_pane(socket_path=owned.socket_path, pane_id=sibling, command="sleep 600")
        server_starttime = claude_sessions.proc_starttime(pid=owned.server_pid)
        assert server_starttime is not None
        provisional = LiveCase(
            session=session,
            socket_path=owned.socket_path,
            server_pid=owned.server_pid,
            server_starttime=server_starttime,
            invoking=owned.root,
            sibling=sibling,
            invoking_shell=0,
            sibling_shell=0,
            sentinel_pid=0,
            scratch=tmp_path,
        )
        sentinel = _await_named(case=provisional, pane=sibling, name="sleep")
        yield LiveCase(
            session=session,
            socket_path=owned.socket_path,
            server_pid=owned.server_pid,
            server_starttime=server_starttime,
            invoking=owned.root,
            sibling=sibling,
            invoking_shell=_foreground(case=provisional, pane=owned.root).shell_pid,
            sibling_shell=_foreground(case=provisional, pane=sibling).shell_pid,
            sentinel_pid=sentinel,
            scratch=tmp_path,
        )
    finally:
        stop_owned_server(session=session)


@dataclass(frozen=True, kw_only=True)
class Candidate:
    home: Path
    prefix: Path
    start: Path
    daemon: Path
    python: Path
    codex_python: Path
    module_dir: Path
    version: str


def _candidate(*, home: Path) -> Candidate:
    prefix = runtime_prefix.runtime_prefix(home=home)
    venv = prefix / "venv"
    if shutil.which("uv") is None:
        pytest.skip("uv is unavailable")
    installed_daemon = runtime_prefix.ensure_runtime(
        prefix=prefix,
        install_source=str(REPO_ROOT),
    )
    assert installed_daemon is not None
    assert installed_daemon == venv / "bin/overseerd"
    python = venv / "bin/python"
    codex_python = venv / "bin/codex"
    codex_python.symlink_to(python.resolve())
    completed = subprocess.run(  # noqa: S603
        [
            str(python),
            "-I",
            "-c",
            (
                "import importlib.metadata as m,json,overseer;"
                "d=m.distribution('livespec-overseer');"
                "u=next(p for p in d.files or () if p.name=='direct_url.json');"
                "print(json.dumps({'version':d.version,'module':overseer.__file__,"
                "'direct':json.loads(d.locate_file(u).read_text())}))"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    raw_metadata: object = json.loads(completed.stdout)
    assert isinstance(raw_metadata, dict)
    metadata = cast(dict[str, object], raw_metadata)
    module_file = Path(str(metadata["module"])).resolve()
    assert module_file.is_relative_to(venv.resolve())
    direct = metadata["direct"]
    assert isinstance(direct, dict)
    direct_map = cast(dict[str, object], direct)
    raw_dir_info = direct_map.get("dir_info")
    assert isinstance(raw_dir_info, dict)
    dir_info = cast(dict[str, object], raw_dir_info)
    assert dir_info.get("editable") is not True
    return Candidate(
        home=home,
        prefix=prefix,
        start=venv / "bin/overseer-start",
        daemon=installed_daemon,
        python=python,
        codex_python=codex_python,
        module_dir=module_file.parent,
        version=str(metadata["version"]),
    )


_FAULT_SOURCE = r"""
import json
import os
import socket
import struct
import sys
import time
from pathlib import Path


def _starttime(pid):
    tail = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rpartition(") ")[2]
    return tail.split()[19]


def _frame(conn):
    data = b""
    while not data.endswith(b"\n"):
        chunk = conn.recv(65536)
        if not chunk:
            break
        data += chunk
    return data


def _observe(method, params):
    path = os.environ["HERDR_SOCKET_PATH"]
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(15.0)
        conn.connect(path)
        raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        peer_pid, _uid, _gid = struct.unpack("3i", raw)
        peer_starttime = _starttime(peer_pid)
        expected_pid = int(os.environ["OVERSEER_FAULT_SERVER_PID"])
        expected_starttime = os.environ["OVERSEER_FAULT_SERVER_STARTTIME"]
        if (peer_pid, peer_starttime) != (expected_pid, expected_starttime):
            raise RuntimeError(
                f"observation reached {(peer_pid, peer_starttime)}, expected "
                f"{(expected_pid, expected_starttime)}"
            )
        request = {"id": "peer-preserving-observer", "method": method, "params": params}
        conn.sendall(json.dumps(request, separators=(",", ":")).encode() + b"\n")
        reply = json.loads(_frame(conn).split(b"\n", 1)[0])
    if "result" not in reply:
        raise RuntimeError(f"observation failed: {reply}")
    return reply["result"], peer_pid, peer_starttime


def _leader(result):
    info = result["process_info"]
    group = info["foreground_process_group_id"]
    leaders = [process for process in info["foreground_processes"] if process["pid"] == group]
    if len(leaders) != 1:
        return None
    return info, leaders[0]


def _record_split(request, mutation_reply):
    pane_id = mutation_reply["result"]["pane"]["pane_id"]
    panes, peer_pid, peer_starttime = _observe("pane.list", {})
    if pane_id not in {pane["pane_id"] for pane in panes["panes"]}:
        raise RuntimeError(f"created pane {pane_id!r} was not independently listed")
    process, _pid, _start = _observe("pane.process_info", {"pane_id": pane_id})
    info, leader = _leader(process)
    if leader is None:
        raise RuntimeError(f"created pane {pane_id!r} has no exact group leader")
    return {
        "kind": "split",
        "method": request["method"],
        "server_pid": peer_pid,
        "server_starttime": peer_starttime,
        "pane_id": pane_id,
        "shell_pid": info["shell_pid"],
        "foreground_pid": leader["pid"],
    }


def _record_daemon(request):
    pane_id = request["params"]["pane_id"]
    deadline = time.monotonic() + 120.0
    last = None
    while time.monotonic() < deadline:
        result, peer_pid, peer_starttime = _observe(
            "pane.process_info", {"pane_id": pane_id}
        )
        parsed = _leader(result)
        if parsed is not None:
            info, leader = parsed
            expected_daemon = os.environ["OVERSEER_FAULT_DAEMON"]
            expected_python = os.environ["OVERSEER_FAULT_PYTHON"]
            candidates = []
            for process in info["foreground_processes"]:
                pid = process["pid"]
                try:
                    executable = str(Path(f"/proc/{pid}/exe").readlink().resolve())
                    cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(
                        b"\0", b" "
                    ).decode(errors="replace")
                except OSError:
                    continue
                if executable == expected_python and expected_daemon in cmdline:
                    candidates.append((pid, executable, cmdline))
            last = (info, leader, candidates)
            if len(candidates) == 1 and info["foreground_process_group_id"] != info["shell_pid"]:
                pid, executable, cmdline = candidates[0]
                return {
                    "kind": "daemon-launch",
                    "method": request["method"],
                    "server_pid": peer_pid,
                    "server_starttime": peer_starttime,
                    "pane_id": pane_id,
                    "shell_pid": info["shell_pid"],
                    "daemon_pid": pid,
                    "daemon_starttime": _starttime(pid),
                    "daemon_executable": executable,
                    "daemon_cmdline": cmdline,
                    "installed_command": request["params"]["text"],
                }
        time.sleep(0.05)
    raise RuntimeError(f"daemon never became independently observable; last={last!r}")


if Path(sys.argv[0]).name == "overseer-start" and os.environ.get("OVERSEER_FAULT_METHOD"):
    import herdr_transport

    _original = herdr_transport.HerdrTransport._send_and_read

    def _withhold_after_observation(self, *, sock, payload, deadline):
        raw, error, timed_out = _original(self, sock=sock, payload=payload, deadline=deadline)
        if error:
            return raw, error, timed_out
        request = json.loads(payload)
        method = os.environ["OVERSEER_FAULT_METHOD"]
        output = Path(os.environ["OVERSEER_FAULT_OBSERVATION"])
        if request["method"] != method or output.exists():
            return raw, error, timed_out
        mutation_reply = json.loads(raw)
        if "result" not in mutation_reply:
            return raw, error, timed_out
        if method == "pane.split":
            record = _record_split(request, mutation_reply)
        else:
            record = _record_daemon(request)
        record["observation_completed_before_reply_loss"] = True
        output.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
        return b"", "controlled reply loss after real-peer effect observation", False

    herdr_transport.HerdrTransport._send_and_read = _withhold_after_observation
"""


@dataclass(frozen=True, kw_only=True)
class Fault:
    directory: Path
    method: str
    observation: Path


def _fault(*, case: LiveCase, stem: str, method: str) -> Fault:
    directory = case.scratch / f"fault-{stem}"
    directory.mkdir()
    _ = (directory / "sitecustomize.py").write_text(_FAULT_SOURCE, encoding="utf-8")
    return Fault(
        directory=directory,
        method=method,
        observation=case.scratch / f"{stem}-observation.json",
    )


def _run_public(
    *, case: LiveCase, candidate: Candidate, stem: str, fault: Fault | None = None
) -> tuple[int, str]:
    rc = case.scratch / f"{stem}.rc"
    stderr = case.scratch / f"{stem}.err"
    assignments = [
        f"HOME={shlex.quote(str(candidate.home))}",
        f"HERDR_SOCKET_PATH={shlex.quote(case.socket_path)}",
    ]
    if fault is not None:
        assignments.extend(
            (
                f"PYTHONPATH={shlex.quote(f'{fault.directory}:{candidate.module_dir}')}",
                f"OVERSEER_FAULT_METHOD={shlex.quote(fault.method)}",
                f"OVERSEER_FAULT_OBSERVATION={shlex.quote(str(fault.observation))}",
                f"OVERSEER_FAULT_SERVER_PID={case.server_pid}",
                f"OVERSEER_FAULT_SERVER_STARTTIME={case.server_starttime}",
                f"OVERSEER_FAULT_DAEMON={shlex.quote(str(candidate.daemon))}",
                f"OVERSEER_FAULT_PYTHON={shlex.quote(str(candidate.python.resolve()))}",
            )
        )
    command = (
        " ".join(assignments)
        + " "
        + f"{shlex.quote(str(candidate.codex_python))} {shlex.quote(str(candidate.start))} "
        + f">/dev/null 2>{shlex.quote(str(stderr))}; "
        + f"printf '%s' $? > {shlex.quote(str(rc))}"
    )
    run_in_pane(socket_path=case.socket_path, pane_id=case.invoking, command=command)
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        if rc.is_file():
            return int(rc.read_text(encoding="utf-8")), stderr.read_text(encoding="utf-8")
        time.sleep(POLL_SECONDS)
    pytest.fail(f"public overseer-start did not finish for {stem}")


def _observation(*, fault: Fault) -> dict[str, object]:
    assert fault.observation.is_file()
    raw: object = json.loads(fault.observation.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return cast(dict[str, object], raw)


def _integer(*, record: dict[str, object], name: str) -> int:
    value = record[name]
    assert isinstance(value, int) and not isinstance(value, bool)
    return value


def _geometry(*, case: LiveCase) -> tuple[dict[str, int], str]:
    reply = raw_request(
        socket_path=case.socket_path,
        method="pane.layout",
        params={"pane_id": case.invoking},
    )
    layout = reply["result"]["layout"]
    tops = {str(row["pane_id"]): int(row["rect"]["y"]) for row in layout["panes"]}
    return tops, str(layout["focused_pane_id"])


def _assert_unrelated_unchanged(*, case: LiveCase) -> None:
    _tops, focused = _geometry(case=case)
    assert focused == case.invoking
    assert _foreground(case=case, pane=case.invoking).shell_pid == case.invoking_shell
    assert _foreground(case=case, pane=case.sibling).shell_pid == case.sibling_shell
    assert Path(f"/proc/{case.sentinel_pid}").exists()


def _candidate_daemon_pids(*, candidate: Candidate) -> set[int]:
    found: set[int] = set()
    needle = str(candidate.daemon).encode()
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            command = (proc / "cmdline").read_bytes()
        except OSError:
            continue
        if needle in command:
            found.add(int(proc.name))
    return found


@dataclass(frozen=True, kw_only=True)
class ObservedDaemon:
    pane: str
    pid: int
    starttime: str
    panes: frozenset[str]


def _verified_daemon_effect(
    *,
    case: LiveCase,
    candidate: Candidate,
    fault: Fault,
    original: set[str],
) -> ObservedDaemon:
    observed = _observation(fault=fault)
    assert observed["observation_completed_before_reply_loss"] is True
    assert (observed["server_pid"], observed["server_starttime"]) == (
        case.server_pid,
        case.server_starttime,
    )
    pane = str(observed["pane_id"])
    pid = _integer(record=observed, name="daemon_pid")
    starttime = str(observed["daemon_starttime"])
    assert starttime == claude_sessions.proc_starttime(pid=pid)
    assert Path(str(observed["daemon_executable"])) == candidate.python.resolve()
    assert str(candidate.daemon) in str(observed["daemon_cmdline"])
    assert str(candidate.daemon) in str(observed["installed_command"])
    assert _await_named(case=case, pane=pane, name="overseerd") == pid
    assert _candidate_daemon_pids(candidate=candidate) == {pid}
    tops, focused = _geometry(case=case)
    assert tops[pane] < tops[case.invoking]
    assert focused == case.invoking
    panes = frozenset(pane_ids(socket_path=case.socket_path))
    assert panes == original | {pane}
    assert Path(f"/proc/{pid}").exists()
    _assert_unrelated_unchanged(case=case)
    return ObservedDaemon(pane=pane, pid=pid, starttime=starttime, panes=panes)


def test_split_reply_loss_preserves_the_real_peer_and_never_replays(*, live_case: LiveCase) -> None:
    candidate = _candidate(home=live_case.scratch / "home-split")
    original = set(pane_ids(socket_path=live_case.socket_path))
    loss = _fault(case=live_case, stem="split", method="pane.split")

    first_rc, first_err = _run_public(
        case=live_case,
        candidate=candidate,
        stem="split-lost",
        fault=loss,
    )

    assert first_rc == 1
    assert "effect is unknown" in first_err
    observed = _observation(fault=loss)
    assert observed["observation_completed_before_reply_loss"] is True
    assert (observed["server_pid"], observed["server_starttime"]) == (
        live_case.server_pid,
        live_case.server_starttime,
    )
    created = str(observed["pane_id"])
    created_shell = _integer(record=observed, name="shell_pid")
    after_first = set(pane_ids(socket_path=live_case.socket_path))
    assert after_first == original | {created}
    assert Path(f"/proc/{created_shell}").exists()

    repeat_rc, repeat_err = _run_public(
        case=live_case,
        candidate=candidate,
        stem="split-repeat",
    )

    assert repeat_rc == 1
    assert "fresh exact-instance, pane and process evidence" in repeat_err
    assert set(pane_ids(socket_path=live_case.socket_path)) == after_first
    assert _foreground(case=live_case, pane=created).shell_pid == created_shell
    assert Path(f"/proc/{created_shell}").exists()
    assert _candidate_daemon_pids(candidate=candidate) == set()
    _assert_unrelated_unchanged(case=live_case)


def test_daemon_launch_reply_loss_observes_exact_candidate_before_reuse(
    *, live_case: LiveCase
) -> None:
    candidate = _candidate(home=live_case.scratch / "home-launch")
    assert candidate.version
    original = set(pane_ids(socket_path=live_case.socket_path))
    loss = _fault(case=live_case, stem="launch", method="pane.send_input")

    first_rc, first_err = _run_public(
        case=live_case,
        candidate=candidate,
        stem="launch-lost",
        fault=loss,
    )

    assert first_rc == 1
    assert "effect is unknown" in first_err
    observed = _verified_daemon_effect(
        case=live_case,
        candidate=candidate,
        fault=loss,
        original=original,
    )

    repeat_rc, repeat_err = _run_public(
        case=live_case,
        candidate=candidate,
        stem="launch-repeat",
    )

    assert repeat_rc == 0, repeat_err
    assert frozenset(pane_ids(socket_path=live_case.socket_path)) == observed.panes
    assert _await_named(case=live_case, pane=observed.pane, name="overseerd") == observed.pid
    assert claude_sessions.proc_starttime(pid=observed.pid) == observed.starttime
    assert _candidate_daemon_pids(candidate=candidate) == {observed.pid}
    assert Path(f"/proc/{observed.pid}").exists()
    _assert_unrelated_unchanged(case=live_case)
