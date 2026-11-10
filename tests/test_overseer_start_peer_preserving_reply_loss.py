"""Postimplementation native proof for reply loss on the verified Herdr peer.

The original public-entrypoint Red remains frozen in
``test_overseer_start_public_herdr.py``.  This later strengthening closes a proof
gap in that exercise without rewriting its chronology: an AF_UNIX forwarding
proxy changes the peer whose credentials the ownership probe verifies.

The fault here lives at the installed client's reply boundary instead.  A
``sitecustomize`` fixture patches only ``HerdrTransport._send_and_read`` in the
genuine, non-editably installed ``overseer-start`` process. The launch-loss fixture
waits for two matching native/kernel readings of the
new split's idle shell, because the split reply can precede the shell's exec.
This bounded test-only wait observes the original peer and never repeats a mutation.
The normal transport
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
from typing import Any, Final, cast

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
# A liveness guard against a hung daemon, never a duration budget.
LIVENESS_GUARD_SECONDS: Final = 600.0
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
    deadline = time.monotonic() + LIVENESS_GUARD_SECONDS
    while time.monotonic() < deadline:
        reading = _foreground(case=case, pane=pane)
        named = reading.pids_named(name=name)
        if named and reading.group_id != reading.shell_pid:
            return named[0]
        time.sleep(POLL_SECONDS)
    pytest.fail(f"test hung waiting for {name!r} to occupy {pane!r}")


def _isolate_candidate_from_forge(*, directory: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the forge read the installed daemon performs every tick a degraded verdict.

    The installed candidate daemon runs the release-currency check each tick
    (``_supervisor_release_runtime``) through ``gh``. Where ``gh`` reaches the forge
    (the factory sandbox, with its minted installation token) and the forge's
    ``release`` ref is green and differs from the installed build's ``v<version>``
    commit, the daemon provisions that release runtime and ``execve``s into it. The
    process keeps its pid and start time but gets a new image, a new daemon instance
    id and a reset tick generation, so ``_await_candidate_daemon`` waits forever for
    the pre-exec identity: the hang this proof reported inside the sandbox while it
    passed wherever ``gh`` could not authenticate. Master CI never offered a release.

    This test grades reply loss, not release adoption, so its Herdr server (hence the
    pane shell the daemon is launched from) gets a ``gh`` that always fails. The
    adapter turns that into a value-level ``currency-blocked`` verdict and the daemon
    keeps its image. The wait stays event-guarded; nothing here retries on a clock.
    """
    stub = directory / "gh"
    _ = stub.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    stub.chmod(0o700)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")


@pytest.fixture
def live_case(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[LiveCase]:
    session = f"overseer-peer-loss-{os.getpid()}-{next(_counter)}"
    forge_stub = tmp_path / "no-forge-bin"
    forge_stub.mkdir()
    _isolate_candidate_from_forge(directory=forge_stub, monkeypatch=monkeypatch)
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
import shutil
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
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(float(os.environ["OVERSEER_FAULT_LIVENESS_GUARD_SECONDS"]))
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
    except TimeoutError as exc:
        raise RuntimeError("test hung waiting for fault-server observation reply") from exc
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


def _await_split_shell(mutation_reply):
    # Establish the real split's coherent shell before grading launch ACK loss.
    pane_id = mutation_reply["result"]["pane"]["pane_id"]
    deadline = time.monotonic() + float(os.environ["OVERSEER_FAULT_LIVENESS_GUARD_SECONDS"])
    previous = None
    while time.monotonic() < deadline:
        result, peer_pid, peer_starttime = _observe("pane.process_info", {"pane_id": pane_id})
        parsed = _leader(result)
        if parsed is not None:
            info, leader = parsed
            pid = info["shell_pid"]
            try:
                executable = str(Path(f"/proc/{pid}/exe").readlink().resolve())
                registered = shutil.which(leader["name"])
                coherent = Path(executable).name == leader["name"] or (
                    registered is not None and str(Path(registered).resolve()) == executable
                )
                identity = (pid, _starttime(pid), executable)
                if info["pane_id"] == pane_id and leader["pid"] == pid and coherent:
                    if identity == previous:
                        return {"pane_id": pane_id, "shell_pid": pid,
                                "shell_starttime": identity[1], "executable": executable,
                                "reported_name": leader["name"], "server_pid": peer_pid,
                                "server_starttime": peer_starttime}
                    previous = identity
                else:
                    previous = None
            except OSError:
                previous = None
        time.sleep(0.05)
    raise RuntimeError(f"test hung waiting for pane {pane_id!r} to supply retained-shell evidence")


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
    deadline = time.monotonic() + float(os.environ["OVERSEER_FAULT_LIVENESS_GUARD_SECONDS"])
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
                starttime = _starttime(pid)
                readiness = _await_daemon_readiness(pid=pid, starttime=starttime)
                return {
                    "kind": "daemon-launch",
                    "method": request["method"],
                    "server_pid": peer_pid,
                    "server_starttime": peer_starttime,
                    "pane_id": pane_id,
                    "shell_pid": info["shell_pid"],
                    "daemon_pid": pid,
                    "daemon_starttime": starttime,
                    "daemon_executable": executable,
                    "daemon_cmdline": cmdline,
                    "installed_command": request["params"]["text"],
                    "daemon_ready": True,
                    "daemon_instance_id": readiness["daemon_instance_id"],
                    "daemon_tick_generation": readiness["tick_generation"],
                }
        time.sleep(0.05)
    raise RuntimeError(f"test hung waiting for daemon observation; last={last!r}")


def _await_daemon_readiness(*, pid, starttime):
    # The daemon itself publishes this only after completing a live tick.
    snapshot = Path.home() / ".livespec-overseer-status.json"
    expected_package = Path(os.environ["OVERSEER_FAULT_MODULE_DIR"]).resolve()
    expected_version = os.environ["OVERSEER_FAULT_VERSION"]
    deadline = time.monotonic() + float(os.environ["OVERSEER_FAULT_LIVENESS_GUARD_SECONDS"])
    while time.monotonic() < deadline:
        try:
            document = json.loads(snapshot.read_text(encoding="utf-8"))
            package = document.get("daemon_package")
            generation = document.get("tick_generation")
            instance_id = document.get("daemon_instance_id")
            ready = (
                isinstance(package, dict)
                and Path(str(package.get("package_dir"))).resolve() == expected_package
                and package.get("version") == expected_version
                and isinstance(generation, int)
                and not isinstance(generation, bool)
                and generation >= 1
                and isinstance(instance_id, str)
                and instance_id
            )
        except (OSError, json.JSONDecodeError):
            ready = False
        if ready:
            if _starttime(pid) != starttime:
                raise RuntimeError("daemon exited before publishing readiness")
            return {"daemon_instance_id": instance_id, "tick_generation": generation}
        try:
            still_running = _starttime(pid) == starttime
        except OSError:
            still_running = False
        if not still_running:
            raise RuntimeError("daemon exited before publishing readiness")
        time.sleep(0.05)
    raise RuntimeError("test hung waiting for daemon readiness snapshot")


if Path(sys.argv[0]).name == "overseer-start" and os.environ.get("OVERSEER_FAULT_METHOD"):
    import herdr_transport

    _original = herdr_transport.HerdrTransport._send_and_read
    _split_readiness = {}

    def _withhold_after_observation(self, *, sock, payload, deadline):
        raw, error, timed_out = _original(self, sock=sock, payload=payload, deadline=deadline)
        if error:
            return raw, error, timed_out
        request = json.loads(payload)
        method = os.environ["OVERSEER_FAULT_METHOD"]
        output = Path(os.environ["OVERSEER_FAULT_OBSERVATION"])
        if request["method"] == "pane.split" and method == "pane.send_input":
            split_reply = json.loads(raw)
            if "result" in split_reply:
                _split_readiness.update(_await_split_shell(split_reply))
        if request["method"] != method or output.exists():
            return raw, error, timed_out
        mutation_reply = json.loads(raw)
        if "result" not in mutation_reply:
            return raw, error, timed_out
        if method == "pane.split":
            record = _record_split(request, mutation_reply)
        else:
            record = _record_daemon(request)
            record["split_readiness"] = dict(_split_readiness)
        ack_shape = os.environ["OVERSEER_FAULT_ACK_SHAPE"]
        record["observation_completed_before_reply_loss"] = True
        record["ack_shape"] = ack_shape
        output.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
        if ack_shape == "lost":
            return b"", "controlled reply loss after real-peer effect observation", False
        if ack_shape == "malformed":
            return b'{"controlled":', "", False
        raise RuntimeError(f"unknown acknowledgement shape: {ack_shape!r}")

    herdr_transport.HerdrTransport._send_and_read = _withhold_after_observation
"""


@dataclass(frozen=True, kw_only=True)
class Fault:
    directory: Path
    method: str
    observation: Path
    ack_shape: str


def _fault(*, case: LiveCase, stem: str, method: str, ack_shape: str) -> Fault:
    directory = case.scratch / f"fault-{stem}"
    directory.mkdir()
    _ = (directory / "sitecustomize.py").write_text(_FAULT_SOURCE, encoding="utf-8")
    return Fault(
        directory=directory,
        method=method,
        observation=case.scratch / f"{stem}-observation.json",
        ack_shape=ack_shape,
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
                f"OVERSEER_FAULT_ACK_SHAPE={shlex.quote(fault.ack_shape)}",
                f"OVERSEER_FAULT_OBSERVATION={shlex.quote(str(fault.observation))}",
                f"OVERSEER_FAULT_SERVER_PID={case.server_pid}",
                f"OVERSEER_FAULT_SERVER_STARTTIME={case.server_starttime}",
                f"OVERSEER_FAULT_DAEMON={shlex.quote(str(candidate.daemon))}",
                f"OVERSEER_FAULT_PYTHON={shlex.quote(str(candidate.python.resolve()))}",
                f"OVERSEER_FAULT_MODULE_DIR={shlex.quote(str(candidate.module_dir))}",
                f"OVERSEER_FAULT_VERSION={shlex.quote(candidate.version)}",
                f"OVERSEER_FAULT_LIVENESS_GUARD_SECONDS={LIVENESS_GUARD_SECONDS}",
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
    deadline = time.monotonic() + LIVENESS_GUARD_SECONDS
    while time.monotonic() < deadline:
        if rc.is_file():
            return int(rc.read_text(encoding="utf-8")), stderr.read_text(encoding="utf-8")
        time.sleep(POLL_SECONDS)
    pytest.fail(f"test hung waiting for public overseer-start to finish for {stem}")


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


@dataclass(frozen=True, kw_only=True)
class CandidateProcess:
    pid: int
    starttime: str
    executable: Path
    command: bytes


def _candidate_diagnostic(*, candidate: CandidateProcess) -> str:
    return (
        f"pid={candidate.pid}, starttime={candidate.starttime!r}, "
        f"executable={str(candidate.executable)!r}, command={candidate.command!r}"
    )


def _pane_process_diagnostics(*, reading: Any) -> tuple[str, ...]:
    details: list[str] = []
    for pid, name in reading.processes:
        process = Path(f"/proc/{pid}")
        try:
            executable = str((process / "exe").readlink().resolve())
        except OSError as error:
            executable = f"<unreadable: {error}>"
        try:
            command = (process / "cmdline").read_bytes()
        except OSError as error:
            command = f"<unreadable: {error}>"
        details.append(
            f"pid={pid}, reported_name={name!r}, executable={executable!r}, " f"command={command!r}"
        )
    return tuple(details)


def _candidate_daemon_pids(*, candidate: Candidate) -> dict[int, CandidateProcess]:
    found: dict[int, CandidateProcess] = {}
    command_needle = str(candidate.daemon).encode()
    expected_executable = candidate.python.resolve()
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        pid = int(proc.name)
        try:
            command = (proc / "cmdline").read_bytes()
            executable = (proc / "exe").readlink().resolve()
        except OSError:
            continue
        starttime = claude_sessions.proc_starttime(pid=pid)
        if (
            starttime is not None
            and executable == expected_executable
            and command_needle in command.split(b"\0")
        ):
            found[pid] = CandidateProcess(
                pid=pid,
                starttime=starttime,
                executable=executable,
                command=command,
            )
    return found


def _daemon_readiness_generation(
    *, candidate: Candidate, instance_id: str, minimum_generation: int
) -> int | None:
    snapshot = candidate.home / ".livespec-overseer-status.json"
    try:
        raw: object = json.loads(snapshot.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    document = cast(dict[str, object], raw)
    package = document.get("daemon_package")
    if not isinstance(package, dict):
        return None
    package_info = cast(dict[str, object], package)
    package_dir = package_info.get("package_dir")
    generation = document.get("tick_generation")
    if (
        not isinstance(package_dir, str)
        or Path(package_dir).resolve() != candidate.module_dir
        or package_info.get("version") != candidate.version
        or document.get("daemon_instance_id") != instance_id
        or isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < minimum_generation
    ):
        return None
    return generation


def _await_candidate_daemon(
    *,
    case: LiveCase,
    pane: str,
    candidate: Candidate,
    expected: CandidateProcess,
    instance_id: str,
    minimum_generation: int,
) -> CandidateProcess:
    deadline = time.monotonic() + LIVENESS_GUARD_SECONDS
    last: tuple[Any, tuple[str, ...]] | None = None
    while time.monotonic() < deadline:
        reading = _foreground(case=case, pane=pane)
        pane_pids = {pid for pid, _name in reading.processes}
        diagnostics = _pane_process_diagnostics(reading=reading)
        last = (reading, diagnostics)
        actual_starttime = claude_sessions.proc_starttime(pid=expected.pid)
        if actual_starttime != expected.starttime:
            pytest.fail(
                "candidate daemon identity changed before readiness: "
                f"expected=({_candidate_diagnostic(candidate=expected)}); "
                f"pane_processes={diagnostics!r}"
            )
        if (
            expected.pid in pane_pids
            and reading.group_id != reading.shell_pid
            and _daemon_readiness_generation(
                candidate=candidate,
                instance_id=instance_id,
                minimum_generation=minimum_generation,
            )
            is not None
        ):
            return expected
        time.sleep(POLL_SECONDS)
    pytest.fail(
        f"test hung waiting for installed candidate daemon in {pane!r}; "
        f"expected=({_candidate_diagnostic(candidate=expected)}); last={last!r}"
    )


@dataclass(frozen=True, kw_only=True)
class ObservedDaemon:
    pane: str
    pid: int
    starttime: str
    panes: frozenset[str]
    instance_id: str
    tick_generation: int


def _verified_daemon_effect(
    *,
    case: LiveCase,
    candidate: Candidate,
    fault: Fault,
    original: set[str],
) -> ObservedDaemon:
    observed = _observation(fault=fault)
    assert observed["observation_completed_before_reply_loss"] is True
    assert observed.get("daemon_ready") is True
    assert observed["ack_shape"] == fault.ack_shape
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
    instance_id = str(observed["daemon_instance_id"])
    tick_generation = _integer(record=observed, name="daemon_tick_generation")
    assert tick_generation >= 1
    expected = CandidateProcess(
        pid=pid,
        starttime=starttime,
        executable=candidate.python.resolve(),
        command=Path(f"/proc/{pid}/cmdline").read_bytes(),
    )
    identity = _await_candidate_daemon(
        case=case,
        pane=pane,
        candidate=candidate,
        expected=expected,
        instance_id=instance_id,
        minimum_generation=tick_generation,
    )
    assert identity == expected
    assert _candidate_daemon_pids(candidate=candidate) == {pid: identity}
    tops, focused = _geometry(case=case)
    assert tops[pane] < tops[case.invoking]
    assert focused == case.invoking
    panes = frozenset(pane_ids(socket_path=case.socket_path))
    assert panes == original | {pane}
    assert Path(f"/proc/{pid}").exists()
    _assert_unrelated_unchanged(case=case)
    return ObservedDaemon(
        pane=pane,
        pid=pid,
        starttime=starttime,
        panes=panes,
        instance_id=instance_id,
        tick_generation=tick_generation,
    )


@pytest.mark.parametrize("ack_shape", ["lost", "malformed"])
def test_split_reply_loss_preserves_the_real_peer_and_never_replays(
    *, live_case: LiveCase, ack_shape: str
) -> None:
    candidate = _candidate(home=live_case.scratch / f"home-split-{ack_shape}")
    original = set(pane_ids(socket_path=live_case.socket_path))
    before_daemons = _candidate_daemon_pids(candidate=candidate)
    assert before_daemons == {}
    loss = _fault(
        case=live_case,
        stem=f"split-{ack_shape}",
        method="pane.split",
        ack_shape=ack_shape,
    )

    first_rc, first_err = _run_public(
        case=live_case,
        candidate=candidate,
        stem=f"split-{ack_shape}",
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
        stem=f"split-{ack_shape}-repeat",
    )

    assert repeat_rc == 1
    assert "fresh exact-instance, pane and process evidence" in repeat_err
    assert set(pane_ids(socket_path=live_case.socket_path)) == after_first
    assert _foreground(case=live_case, pane=created).shell_pid == created_shell
    assert Path(f"/proc/{created_shell}").exists()
    assert _candidate_daemon_pids(candidate=candidate) == before_daemons
    _assert_unrelated_unchanged(case=live_case)


@pytest.mark.parametrize("ack_shape", ["lost", "malformed"])
def test_daemon_launch_reply_loss_observes_exact_candidate_before_reuse(
    *, live_case: LiveCase, ack_shape: str
) -> None:
    candidate = _candidate(home=live_case.scratch / f"home-launch-{ack_shape}")
    assert candidate.version
    original = set(pane_ids(socket_path=live_case.socket_path))
    before_daemons = _candidate_daemon_pids(candidate=candidate)
    assert before_daemons == {}
    loss = _fault(
        case=live_case,
        stem=f"launch-{ack_shape}",
        method="pane.send_input",
        ack_shape=ack_shape,
    )

    first_rc, first_err = _run_public(
        case=live_case,
        candidate=candidate,
        stem=f"launch-{ack_shape}",
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
        stem=f"launch-{ack_shape}-repeat",
    )

    assert repeat_rc == 0, repeat_err
    assert frozenset(pane_ids(socket_path=live_case.socket_path)) == observed.panes
    repeat_identity = _await_candidate_daemon(
        case=live_case,
        pane=observed.pane,
        candidate=candidate,
        expected=CandidateProcess(
            pid=observed.pid,
            starttime=observed.starttime,
            executable=candidate.python.resolve(),
            command=Path(f"/proc/{observed.pid}/cmdline").read_bytes(),
        ),
        instance_id=observed.instance_id,
        minimum_generation=observed.tick_generation + 1,
    )
    assert repeat_identity.pid == observed.pid
    assert repeat_identity.starttime == observed.starttime
    assert claude_sessions.proc_starttime(pid=observed.pid) == observed.starttime
    assert Path(f"/proc/{observed.pid}").exists()
    _assert_unrelated_unchanged(case=live_case)
