"""Public bootstrap regression for a named tmux server nested in Herdr.

The native case is the failed assertion-3 proof from PR #2374: the same live
tmux generation is reachable both through the ambient client route and through
the explicit socket exported in ``TMUX``.  Those are two coordinates for one
owner, not two equally-near owners.  The deterministic companion pins which
coordinate survives the collapse: the explicit socket that can retain the
selected instance on every later call.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from test_herdr_live_observations import (
    pane_ids,
    run_in_pane,
    start_owned_server,
    stop_owned_server,
)

from overseer import runtime_prefix, terminal_ownership

__all__: list[str] = []

REPO_ROOT = Path(__file__).resolve().parent.parent
WAIT_SECONDS = 180.0
NAMED_SOCKET = "/tmp/overseer-nested-tmux.sock"
TMUX_BINARY = "tmux"


@dataclass(frozen=True, kw_only=True)
class DuplicateTmuxProbe:
    """One live generation exposed through ambient and explicit coordinates."""

    backend: str = "tmux"

    def endpoints(self, *, environ: dict[str, str]) -> tuple[str, ...]:
        del environ
        return "", NAMED_SOCKET

    def owned_panes(self, *, endpoint: str) -> terminal_ownership.ClaimReading:
        return terminal_ownership.ClaimReading(
            panes=(
                terminal_ownership.OwnedPane(
                    backend=self.backend,
                    socket_path=endpoint,
                    server_pid=300,
                    server_starttime="generation-one",
                    pane_id="%0",
                    pane_process_pids=(200,),
                ),
            ),
            error="",
        )


def _parent(*, pid: int) -> int:
    return {100: 200, 200: 300, 300: 400, 400: 1}.get(pid, 1)


def test_duplicate_routes_to_one_tmux_generation_retain_the_explicit_socket() -> None:
    selection = terminal_ownership.select_owner(
        pid=100,
        environ={"TMUX": f"{NAMED_SOCKET},300,0"},
        probes=(DuplicateTmuxProbe(),),
        ppid_of=_parent,
    )

    assert selection.ok, selection.error
    assert selection.claim is not None
    assert selection.claim.backend == "tmux"
    assert selection.claim.socket_path == NAMED_SOCKET
    assert selection.claim.server_pid == 300
    assert selection.claim.server_starttime == "generation-one"
    assert selection.claim.pane_id == "%0"


def _tmux(*, socket_path: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- the native tmux control for this owned server.
        [TMUX_BINARY, "-S", socket_path, *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30.0,
    )


def _must_tmux(*, socket_path: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    completed = _tmux(socket_path=socket_path, args=args)
    assert completed.returncode == 0, completed.stderr
    return completed


def _rows(*, socket_path: str) -> list[dict[str, object]]:
    listed = _must_tmux(
        socket_path=socket_path,
        args=[
            "list-panes",
            "-a",
            "-F",
            "#{pane_id}\t#{pane_pid}\t#{pid}\t#{pane_top}\t#{pane_active}",
        ],
    )
    rows: list[dict[str, object]] = []
    for line in listed.stdout.splitlines():
        pane, pane_pid, server_pid, top, active = line.split("\t")
        rows.append(
            {
                "pane": pane,
                "pane_pid": int(pane_pid),
                "server_pid": int(server_pid),
                "top": int(top),
                "active": active == "1",
            }
        )
    return rows


def _wait_for(predicate, *, description: str):
    deadline = time.monotonic() + WAIT_SECONDS
    last = None
    while time.monotonic() < deadline:
        try:
            last = predicate()
        except OSError as error:
            last = error
        if last:
            return last
        time.sleep(0.1)
    pytest.fail(f"timed out waiting for {description}; last={last!r}")


def _send(*, socket_path: str, pane: str, command: str) -> None:
    _ = _must_tmux(socket_path=socket_path, args=["send-keys", "-t", pane, "-l", command])
    _ = _must_tmux(socket_path=socket_path, args=["send-keys", "-t", pane, "Enter"])


@dataclass(frozen=True, kw_only=True)
class Candidate:
    home: Path
    prefix: Path
    start: Path
    codex: Path


@dataclass(frozen=True, kw_only=True)
class NativeCase:
    session: str
    herdr_socket: str
    outer_panes: list[str]
    tmux_socket: str
    original: dict[str, object]
    scratch: Path
    candidate: Candidate


def _candidate(*, scratch: Path) -> Candidate:
    home = scratch / "candidate-home"
    prefix = runtime_prefix.runtime_prefix(home=home)
    daemon = runtime_prefix.ensure_runtime(prefix=prefix, install_source=str(REPO_ROOT))
    assert daemon == prefix / "venv" / "bin" / "overseerd"
    codex = prefix / "venv" / "bin" / "codex"
    codex.symlink_to((prefix / "venv" / "bin" / "python").resolve())
    return Candidate(
        home=home,
        prefix=prefix,
        start=prefix / "venv" / "bin" / "overseer-start",
        codex=codex,
    )


def _run_public(*, case: NativeCase, stem: str) -> tuple[int, str]:
    rc = case.scratch / f"{stem}.rc"
    stderr = case.scratch / f"{stem}.stderr"
    command = (
        f"HOME={shlex.quote(str(case.candidate.home))} "
        f"HERDR_SOCKET_PATH={shlex.quote(case.herdr_socket)} "
        f"{shlex.quote(str(case.candidate.codex))} "
        f"{shlex.quote(str(case.candidate.start))} "
        f">/dev/null 2>{shlex.quote(str(stderr))}; "
        f"printf '%s' $? > {shlex.quote(str(rc))}"
    )
    _send(socket_path=case.tmux_socket, pane=str(case.original["pane"]), command=command)
    _wait_for(rc.is_file, description=f"public overseer-start completion for {stem}")
    return int(rc.read_text(encoding="utf-8")), stderr.read_text(encoding="utf-8")


def _descendant_daemon(*, root_pid: int, prefix: Path) -> int | None:
    descendants = {root_pid}
    changed = True
    while changed:
        changed = False
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit() or int(entry.name) in descendants:
                continue
            try:
                stat = (entry / "stat").read_text(encoding="utf-8")
                parent = int(stat.rpartition(") ")[2].split()[1])
            except (OSError, IndexError, ValueError):
                continue
            if parent in descendants:
                descendants.add(int(entry.name))
                changed = True
    for pid in descendants - {root_pid}:
        try:
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
        except OSError:
            continue
        if str(prefix) in cmdline and "overseerd" in cmdline:
            return pid
    return None


@pytest.fixture(name="native_case")
def _native_case(*, tmp_path: Path) -> Iterator[NativeCase]:
    if shutil.which("tmux") is None:
        pytest.skip("tmux is unavailable")
    session = f"overseer-public-nested-{os.getpid()}-{time.monotonic_ns()}"
    tmux_socket = str(tmp_path / "inner-tmux.sock")
    try:
        outer = start_owned_server(session=session, scratch=tmp_path)
        outer_before = pane_ids(socket_path=outer.socket_path)
        run_in_pane(
            socket_path=outer.socket_path,
            pane_id=outer.root,
            command=f"tmux -D -S {shlex.quote(tmux_socket)}",
        )
        _wait_for(Path(tmux_socket).exists, description="the nested tmux socket")
        _ = _must_tmux(
            socket_path=tmux_socket,
            args=["new-session", "-d", "-s", "inner", "-c", str(tmp_path)],
        )
        before = _rows(socket_path=tmux_socket)
        assert len(before) == 1
        yield NativeCase(
            session=session,
            herdr_socket=outer.socket_path,
            outer_panes=outer_before,
            tmux_socket=tmux_socket,
            original=before[0],
            scratch=tmp_path,
            candidate=_candidate(scratch=tmp_path),
        )
    finally:
        if Path(tmux_socket).exists():
            _ = _tmux(socket_path=tmux_socket, args=["kill-server"])
        stop_owned_server(session=session)


def test_public_start_selects_named_tmux_nested_in_herdr_and_reuses_it(
    *, native_case: NativeCase
) -> None:
    first_rc, first_stderr = _run_public(case=native_case, stem="first")

    assert first_rc == 0, first_stderr
    after = _rows(socket_path=native_case.tmux_socket)
    assert len(after) == 2
    original_after = next(row for row in after if row["pane"] == native_case.original["pane"])
    daemon_row = next(row for row in after if row["pane"] != native_case.original["pane"])
    assert int(daemon_row["top"]) < int(original_after["top"])
    assert original_after["active"]
    daemon_pid = _wait_for(
        lambda: _descendant_daemon(
            root_pid=int(daemon_row["pane_pid"]), prefix=native_case.candidate.prefix
        ),
        description="the installed candidate daemon",
    )

    repeat_rc, repeat_stderr = _run_public(case=native_case, stem="repeat")

    assert repeat_rc == 0, repeat_stderr
    assert _rows(socket_path=native_case.tmux_socket) == after
    assert (
        _descendant_daemon(
            root_pid=int(daemon_row["pane_pid"]), prefix=native_case.candidate.prefix
        )
        == daemon_pid
    )
    assert pane_ids(socket_path=native_case.herdr_socket) == native_case.outer_panes
