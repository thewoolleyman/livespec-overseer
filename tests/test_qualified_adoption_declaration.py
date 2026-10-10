"""Qualified native panes join live runtime records and implicit declarations."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from overseer import (
    declare,
    herdr_adapter,
    herdr_calls,
    herdr_identity,
    herdr_transport,
    pane_router,
    signals,
    supervisor,
    terminal_ownership,
)
from overseer.test_supervisor_builders import write_session
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@dataclass(frozen=True, kw_only=True)
class NativePane:
    target: herdr_identity.HerdrPaneTarget
    shell_pid: int
    process_pid: int
    cwd: str
    command: str


@dataclass(kw_only=True)
class ControlledHerdr:
    panes: dict[str, NativePane]
    stale: str
    calls: list[tuple[str, str]]

    def identify(self, *, socket_path: str) -> herdr_adapter.InstanceIdentification:
        self.calls.append(("identify", socket_path))
        pane = self.panes.get(socket_path)
        if pane is None:
            return herdr_adapter.InstanceIdentification(ok=False, peer=None, error="gone")
        return herdr_adapter.InstanceIdentification(
            ok=True,
            peer=herdr_transport.PeerIdentity(
                pid=pane.target.server_pid,
                uid=1000,
                starttime=pane.target.server_starttime,
            ),
            error="",
        )

    def list_panes(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_adapter.PaneListing:
        self.calls.append(("list", target.socket_path))
        pane = self.panes.get(target.socket_path)
        if pane is None or target.socket_path == self.stale:
            return herdr_adapter.PaneListing(ok=False, panes=(), error="gone")
        return herdr_adapter.PaneListing(
            ok=True,
            panes=(
                herdr_calls.PaneRow(
                    pane_id=pane.target.pane_id,
                    tab_id="w1:t1",
                    workspace_id="w1",
                    cwd=pane.cwd,
                    foreground_cwd=pane.cwd,
                    focused=False,
                ),
            ),
            error="",
        )

    def capture_pane(
        self, *, target: herdr_identity.HerdrPaneTarget, retain_ansi: bool = True
    ) -> herdr_adapter.PaneCapture:
        assert retain_ansi
        return herdr_adapter.PaneCapture(ok=True, text="\x1b[2mnative\x1b[0m", error="")

    def foreground(
        self, *, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.ForegroundReading:
        self.calls.append(("foreground", target.socket_path))
        pane = self.panes[target.socket_path]
        return herdr_adapter.ForegroundReading(
            ok=True,
            process=herdr_calls.ForegroundProcess(
                pane_id=target.pane_id,
                shell_pid=pane.shell_pid,
                process_group_id=pane.process_pid,
                name=pane.command,
                cmdline=pane.command,
                cwd=pane.cwd,
            ),
            error="",
        )


@dataclass(frozen=True, kw_only=True)
class OwnedProbe:
    pane: NativePane
    backend: str = herdr_identity.HERDR_BACKEND

    def endpoints(self, *, environ: dict[str, str]) -> tuple[str, ...]:
        _ = environ
        return (self.pane.target.socket_path,)

    def owned_panes(self, *, endpoint: str) -> terminal_ownership.ClaimReading:
        assert endpoint == self.pane.target.socket_path
        return terminal_ownership.ClaimReading(
            panes=(
                terminal_ownership.OwnedPane(
                    backend=self.backend,
                    socket_path=endpoint,
                    server_pid=self.pane.target.server_pid,
                    server_starttime=self.pane.target.server_starttime,
                    pane_id=self.pane.target.pane_id,
                    pane_process_pids=(self.pane.shell_pid, self.pane.process_pid),
                ),
            ),
            error="",
        )


def _target(*, socket: str, server: int) -> herdr_identity.HerdrPaneTarget:
    return herdr_identity.HerdrPaneTarget(
        socket_path=socket,
        server_pid=server,
        server_starttime=f"start-{server}",
        pane_id="w1:p1",
    )


@dataclass(frozen=True, kw_only=True)
class AdoptionScenario:
    repo_a: Path
    repo_b: Path
    pane_a: NativePane
    pane_b: NativePane
    native: ControlledHerdr
    sup: supervisor.Supervisor


def _scenario(*, tmp_path: Path) -> AdoptionScenario:
    repo_a, repo_b = tmp_path / "repo-a", tmp_path / "repo-b"
    for repo, topic in ((repo_a, "alpha"), (repo_b, "beta")):
        (repo / "plan" / topic).mkdir(parents=True)
    pane_a = NativePane(
        target=_target(socket="/run/herdr-a.sock", server=701),
        shell_pid=501,
        process_pid=502,
        cwd=str(repo_a),
        command="claude",
    )
    pane_b = NativePane(
        target=_target(socket="/run/herdr-b.sock", server=702),
        shell_pid=601,
        process_pid=602,
        cwd=str(repo_b),
        command="codex",
    )
    native = ControlledHerdr(
        panes={pane_a.target.socket_path: pane_a, pane_b.target.socket_path: pane_b},
        stale="/run/herdr-stale.sock",
        calls=[],
    )
    driver = pane_router.MixedPaneDriver(
        tmux=FakeTmux(),
        herdr=native,
        herdr_endpoints=lambda: (*native.panes, native.stale),
    )
    sessions = tmp_path / "claude-sessions"
    sessions.mkdir()
    write_session(sessions_dir=sessions, pid=1001, name="alpha", cwd=repo_a)
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    session_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    (codex_home / "session_index.jsonl").write_text(
        json.dumps({"id": session_id, "thread_name": "beta"}) + "\n",
        encoding="utf-8",
    )
    parents = {1001: pane_a.process_pid, 2002: pane_b.process_pid}
    sup = supervisor.Supervisor(
        tmux=driver,
        store_path=tmp_path / "mapping.jsonl",
        stamp_path=tmp_path / "stamps.json",
        watch_repos=[str(repo_a), str(repo_b)],
        sessions_dir=sessions,
        ppid_of=lambda *, pid: parents.get(pid),
        starttime_of=lambda *, pid: "pt" if pid == 1001 else None,
        cmdline_of=lambda *, pid: b"claude\0" if pid == 1001 else None,
        environ_of=lambda *, pid: b"" if pid in {1001, 2002} else None,
        runtime_model_of=lambda *, pid: None,
        codex_home=codex_home,
        codex_pids_of_comm=lambda *, comm: [2002] if comm == "codex" else [],
        codex_fd_targets_of=lambda *, pid: [f"rollout-now-{session_id}.jsonl"],
        codex_cwd_of=lambda *, pid: str(repo_b) if pid == 2002 else None,
        children_of=lambda *, pid: [],
        out=io.StringIO(),
        require_render_terminal=False,
    )
    return AdoptionScenario(
        repo_a=repo_a,
        repo_b=repo_b,
        pane_a=pane_a,
        pane_b=pane_b,
        native=native,
        sup=sup,
    )


def test_live_claude_and_codex_adopt_and_implicitly_declare_their_qualified_tracks(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    default = supervisor.Supervisor()
    assert isinstance(default.tmux, pane_router.MixedPaneDriver)
    scenario = _scenario(tmp_path=tmp_path)
    adopted = scenario.sup.adopt_sessions()
    expected = {
        (str(scenario.repo_a), "alpha"): herdr_identity.encode_herdr_target(
            target=scenario.pane_a.target
        ),
        (str(scenario.repo_b), "beta"): herdr_identity.encode_herdr_target(
            target=scenario.pane_b.target
        ),
    }
    assert {(track.repo, track.topic): track.tmux for track in adopted} == expected
    assert scenario.native.stale in {
        socket for operation, socket in scenario.native.calls if operation == "identify"
    }

    monkeypatch.setattr(declare.registry, "DEFAULT_STORE_PATH", str(scenario.sup.store_path))
    monkeypatch.setattr(declare.registry, "DEFAULT_STAMP_PATH", str(scenario.sup.stamp_path))
    monkeypatch.delenv("OVERSEER_TOPIC", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    monkeypatch.setattr(pane_router, "PROCESS_PID", lambda: 9000)
    current = {"pane": scenario.pane_a}
    monkeypatch.setattr(
        pane_router, "OWNERSHIP_PROBES", lambda: (OwnedProbe(pane=current["pane"]),)
    )
    monkeypatch.setattr(
        pane_router,
        "PROCESS_PPID",
        lambda *, pid: {
            9000: current["pane"].process_pid,
            current["pane"].process_pid: current["pane"].target.server_pid,
            current["pane"].target.server_pid: 1,
        }.get(pid),
    )

    assert declare.main(argv=["ready", "--repo", str(scenario.repo_a)]) == 0
    assert signals.read_state(repo=str(scenario.repo_a), topic="alpha").token == signals.STATE_READY
    current["pane"] = scenario.pane_b
    assert declare.main(argv=["ready", "--repo", str(scenario.repo_b)]) == 0
    assert signals.read_state(repo=str(scenario.repo_b), topic="beta").token == signals.STATE_READY
