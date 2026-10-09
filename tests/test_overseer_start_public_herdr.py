"""Native public-entrypoint proof for the Herdr two-pane bootstrap.

Each exercise invokes the genuinely installed ``overseer-start`` console script
from a process inside a real Herdr pane.  The candidate is installed non-editably
into a fresh versioned runtime prefix, and its interpreter is also exposed under
the ``codex`` basename solely to satisfy the entrypoint's existing supported-agent
admission guard.  Terminal authority still comes only from the real pane/server
ancestry that the public command must verify.

The fault proxy forwards the selected native mutation to completion and only then
drops its reply.  Repeats are new console-script processes, so replay prevention
cannot come from an in-memory flag.
"""

from __future__ import annotations

import contextlib
import itertools
import json
import os
import shlex
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
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


@pytest.fixture(name="live_case")
def _live_case(*, tmp_path: Path) -> Iterator[LiveCase]:
    session = f"overseer-public-{os.getpid()}-{next(_counter)}"
    try:
        owned = start_owned_server(session=session, scratch=tmp_path, cwd=PANE_CWD)
        sibling = split_pane(
            socket_path=owned.socket_path, pane_id=owned.root, direction="down", ratio=0.5
        )
        run_in_pane(socket_path=owned.socket_path, pane_id=sibling, command="sleep 600")
        provisional = LiveCase(
            session=session,
            socket_path=owned.socket_path,
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
    raw_dir_info = cast(dict[str, object], direct).get("dir_info")
    assert isinstance(raw_dir_info, dict)
    assert cast(dict[str, object], raw_dir_info).get("editable") is not True
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


@dataclass(frozen=True, kw_only=True)
class CandidateProcess:
    pid: int
    starttime: str
    executable: Path
    command: bytes


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


def _await_candidate_daemon(*, case: LiveCase, pane: str, candidate: Candidate) -> CandidateProcess:
    deadline = time.monotonic() + WAIT_SECONDS
    last: object = None
    while time.monotonic() < deadline:
        reading = _foreground(case=case, pane=pane)
        candidates = [
            identity
            for pid, identity in _candidate_daemon_pids(candidate=candidate).items()
            if pid == reading.group_id
        ]
        last = (reading, candidates)
        if len(candidates) == 1 and reading.group_id != reading.shell_pid:
            return candidates[0]
        time.sleep(POLL_SECONDS)
    pytest.fail(f"installed candidate daemon never occupied {pane!r}; last={last!r}")


def _run_public(
    *, case: LiveCase, candidate: Candidate, socket_path: str, stem: str
) -> tuple[int, str]:
    rc = case.scratch / f"{stem}.rc"
    stderr = case.scratch / f"{stem}.err"
    command = (
        f"HOME={shlex.quote(str(candidate.home))} "
        f"HERDR_SOCKET_PATH={shlex.quote(socket_path)} "
        f"{shlex.quote(str(candidate.codex_python))} {shlex.quote(str(candidate.start))} "
        f">/dev/null 2>{shlex.quote(str(stderr))}; "
        f"printf '%s' $? > {shlex.quote(str(rc))}"
    )
    run_in_pane(socket_path=case.socket_path, pane_id=case.invoking, command=command)
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        if rc.is_file():
            return int(rc.read_text(encoding="utf-8")), stderr.read_text(encoding="utf-8")
        time.sleep(POLL_SECONDS)
    pytest.fail(f"public overseer-start did not finish for {stem}")


def _daemon_pane(*, case: LiveCase, original: set[str]) -> str:
    added = set(pane_ids(socket_path=case.socket_path)) - original
    assert len(added) == 1
    return next(iter(added))


def _assert_unchanged(*, case: LiveCase) -> None:
    layout = raw_request(
        socket_path=case.socket_path, method="pane.layout", params={"pane_id": case.invoking}
    )["result"]["layout"]
    assert layout["focused_pane_id"] == case.invoking
    assert _foreground(case=case, pane=case.invoking).shell_pid == case.invoking_shell
    assert _foreground(case=case, pane=case.sibling).shell_pid == case.sibling_shell
    assert Path(f"/proc/{case.sentinel_pid}").exists()


@dataclass(kw_only=True)
class ProxyState:
    drop_method: str
    methods: list[str] = field(default_factory=list)
    created: str = ""
    dropped: int = 0


def _frame(*, conn: socket.socket) -> bytes:
    data = b""
    while not data.endswith(b"\n"):
        chunk = conn.recv(65536)
        if not chunk:
            break
        data += chunk
    return data


def _proxy_loop(*, listener: socket.socket, real: str, state: ProxyState) -> None:
    while True:
        try:
            conn, _ = listener.accept()
        except OSError:
            return
        with conn:
            raw = _frame(conn=conn)
            if not raw:
                continue
            request = json.loads(raw)
            method = str(request["method"])
            state.methods.append(method)
            upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            with upstream:
                upstream.connect(real)
                upstream.sendall(raw)
                reply = _frame(conn=upstream)
            if method == "pane.split" and reply:
                state.created = str(json.loads(reply)["result"]["pane"]["pane_id"])
            if method == state.drop_method:
                state.dropped += 1
                continue
            with contextlib.suppress(OSError):
                conn.sendall(reply)


@contextlib.contextmanager
def _proxy(*, case: LiveCase, drop_method: str) -> Iterator[tuple[str, ProxyState]]:
    path = str(case.scratch / f"proxy-{drop_method.replace('.', '-')}.sock")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(path)
    listener.listen(16)
    state = ProxyState(drop_method=drop_method)
    thread = threading.Thread(
        target=_proxy_loop,
        kwargs={"listener": listener, "real": case.socket_path, "state": state},
        daemon=True,
    )
    thread.start()
    try:
        yield path, state
    finally:
        listener.close()
        thread.join(timeout=5.0)


def test_public_start_creates_and_reuses_one_verified_daemon(*, live_case: LiveCase) -> None:
    candidate = _candidate(home=live_case.scratch / "home-positive")
    original = set(pane_ids(socket_path=live_case.socket_path))

    first_rc, first_err = _run_public(
        case=live_case, candidate=candidate, socket_path=live_case.socket_path, stem="first"
    )

    assert first_rc == 0, first_err
    daemon = _daemon_pane(case=live_case, original=original)
    daemon_identity = _await_candidate_daemon(case=live_case, pane=daemon, candidate=candidate)
    assert candidate.version
    assert candidate.module_dir.is_relative_to(candidate.prefix)
    assert daemon_identity.pid == _foreground(case=live_case, pane=daemon).group_id
    assert daemon_identity.starttime == claude_sessions.proc_starttime(pid=daemon_identity.pid)
    assert daemon_identity.executable == candidate.python.resolve()
    assert str(candidate.daemon).encode() in daemon_identity.command.split(b"\0")
    assert _candidate_daemon_pids(candidate=candidate) == {daemon_identity.pid: daemon_identity}
    _assert_unchanged(case=live_case)

    repeat_rc, repeat_err = _run_public(
        case=live_case, candidate=candidate, socket_path=live_case.socket_path, stem="repeat"
    )
    assert repeat_rc == 0, repeat_err
    assert set(pane_ids(socket_path=live_case.socket_path)) == original | {daemon}
    assert (
        _await_candidate_daemon(case=live_case, pane=daemon, candidate=candidate) == daemon_identity
    )


def test_public_start_refuses_a_real_foreground_tail_with_a_daemon_marker(
    *, live_case: LiveCase
) -> None:
    candidate = _candidate(home=live_case.scratch / "home-tail-lookalike")
    lookalike = split_pane(
        socket_path=live_case.socket_path,
        pane_id=live_case.invoking,
        direction="down",
        ratio=0.5,
    )
    swapped = raw_request(
        socket_path=live_case.socket_path,
        method="pane.swap",
        params={
            "source_pane_id": live_case.invoking,
            "target_pane_id": lookalike,
        },
    )
    assert swapped["result"]["swap"]["changed"] is True
    log_path = live_case.scratch / "overseerd.log"
    log_path.touch()
    tail = shutil.which("tail")
    assert tail is not None
    run_in_pane(
        socket_path=live_case.socket_path,
        pane_id=lookalike,
        command=f"{shlex.quote(tail)} -f {shlex.quote(str(log_path))}",
    )
    tail_pid = _await_named(case=live_case, pane=lookalike, name="tail")
    tail_start = claude_sessions.proc_starttime(pid=tail_pid)
    tail_executable = Path(f"/proc/{tail_pid}/exe").readlink().resolve()
    before_panes = set(pane_ids(socket_path=live_case.socket_path))

    rc, stderr = _run_public(
        case=live_case,
        candidate=candidate,
        socket_path=live_case.socket_path,
        stem="tail-lookalike",
    )

    assert rc == 1, stderr
    assert "not the overseer daemon" in stderr
    assert set(pane_ids(socket_path=live_case.socket_path)) == before_panes
    after = _foreground(case=live_case, pane=lookalike)
    assert after.group_id == tail_pid
    assert claude_sessions.proc_starttime(pid=tail_pid) == tail_start
    assert Path(f"/proc/{tail_pid}/exe").readlink().resolve() == tail_executable
    assert tail_executable == Path(tail).resolve()
    _assert_unchanged(case=live_case)


def test_public_repeat_never_replays_a_real_split_whose_reply_was_lost(
    *, live_case: LiveCase
) -> None:
    candidate = _candidate(home=live_case.scratch / "home-split")
    original = set(pane_ids(socket_path=live_case.socket_path))
    with _proxy(case=live_case, drop_method="pane.split") as (proxy, state):
        first_rc, first_err = _run_public(
            case=live_case, candidate=candidate, socket_path=proxy, stem="split-lost"
        )
        assert first_rc == 1
        assert "unknown" in first_err.lower()
        assert state.dropped == 1
        created = state.created
        created_shell = _foreground(case=live_case, pane=created).shell_pid

        repeat_rc, repeat_err = _run_public(
            case=live_case, candidate=candidate, socket_path=proxy, stem="split-repeat"
        )
        assert repeat_rc == 1
        assert "fresh exact-instance, pane and process evidence" in repeat_err
        assert state.methods.count("pane.split") == 1
        assert set(pane_ids(socket_path=live_case.socket_path)) == original | {created}
        assert _foreground(case=live_case, pane=created).shell_pid == created_shell
        assert Path(f"/proc/{created_shell}").exists()
        _assert_unchanged(case=live_case)


def test_public_repeat_reuses_a_real_daemon_when_its_launch_reply_was_lost(
    *, live_case: LiveCase
) -> None:
    candidate = _candidate(home=live_case.scratch / "home-launch")
    original = set(pane_ids(socket_path=live_case.socket_path))
    with _proxy(case=live_case, drop_method="pane.send_input") as (proxy, state):
        first_rc, first_err = _run_public(
            case=live_case, candidate=candidate, socket_path=proxy, stem="launch-lost"
        )
        assert first_rc == 1
        assert "unknown" in first_err.lower()
        assert state.dropped == 1
        daemon = state.created
        daemon_identity = _await_candidate_daemon(case=live_case, pane=daemon, candidate=candidate)

        repeat_rc, repeat_err = _run_public(
            case=live_case, candidate=candidate, socket_path=proxy, stem="launch-repeat"
        )
        assert repeat_rc == 0, repeat_err
        assert state.methods.count("pane.split") == 1
        assert state.methods.count("pane.send_input") == 1
        assert set(pane_ids(socket_path=live_case.socket_path)) == original | {daemon}
        assert (
            _await_candidate_daemon(case=live_case, pane=daemon, candidate=candidate)
            == daemon_identity
        )
        assert Path(f"/proc/{daemon_identity.pid}").exists()
        _assert_unchanged(case=live_case)
