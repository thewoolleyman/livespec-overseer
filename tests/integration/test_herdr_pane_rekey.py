"""A live Herdr process survives positional pane renumbering."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import herdr_adapter
import herdr_calls
import herdr_identity
import herdr_transport
import pane_router
import pytest
import registry
import supervisor
from test_supervisor_builders import idle_capture
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@dataclass(frozen=True, kw_only=True)
class PaneProcess:
    pid: int
    starttime: str


@dataclass(kw_only=True)
class RenumberingHerdr:
    """A server whose stale pane reads echo the pane's current positional id."""

    repo: str
    recorded: herdr_identity.HerdrPaneTarget
    current_pane_id: str
    processes: dict[str, PaneProcess]
    server_pid: int
    server_starttime: str
    calls: list[tuple[str, str]] = field(default_factory=list)

    def identify(self, *, socket_path: str) -> herdr_adapter.InstanceIdentification:
        self.calls.append(("identify", socket_path))
        if socket_path != self.recorded.socket_path:
            return herdr_adapter.InstanceIdentification(
                ok=False,
                peer=None,
                error="server is unavailable",
            )
        return herdr_adapter.InstanceIdentification(
            ok=True,
            peer=herdr_transport.PeerIdentity(
                pid=self.server_pid,
                uid=1000,
                starttime=self.server_starttime,
            ),
            error="",
        )

    def list_panes(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_adapter.PaneListing:
        self.calls.append(("list", target.pane_id))
        return herdr_adapter.PaneListing(
            ok=True,
            panes=tuple(
                herdr_calls.PaneRow(
                    pane_id=pane_id,
                    tab_id="tab",
                    workspace_id="workspace",
                    cwd=self.repo,
                    foreground_cwd=self.repo,
                    focused=False,
                )
                for pane_id in self.processes
            ),
            error="",
        )

    def capture_pane(
        self, *, target: herdr_identity.HerdrPaneTarget, retain_ansi: bool = True
    ) -> herdr_adapter.PaneCapture:
        assert retain_ansi is True
        self.calls.append(("capture", target.pane_id))
        if target.pane_id not in self.processes:
            return herdr_adapter.PaneCapture(
                ok=False,
                text="",
                error=f"read echoed renumbered pane {self.current_pane_id}",
            )
        return herdr_adapter.PaneCapture(ok=True, text=idle_capture(ctx=70), error="")

    def foreground(
        self, *, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.ForegroundReading:
        self.calls.append(("foreground", target.pane_id))
        process = self.processes.get(target.pane_id)
        if process is None:
            return herdr_adapter.ForegroundReading(
                ok=False,
                process=None,
                error=f"process_info echoed renumbered pane {self.current_pane_id}",
            )
        return herdr_adapter.ForegroundReading(
            ok=True,
            process=herdr_calls.ForegroundProcess(
                pane_id=target.pane_id,
                shell_pid=9000,
                process_group_id=process.pid,
                name="claude",
                cmdline="claude --dangerously-skip-permissions",
                cwd=self.repo,
            ),
            error="",
        )

    def starttime_of(self, *, pid: int) -> str | None:
        return next(
            (process.starttime for process in self.processes.values() if process.pid == pid),
            None,
        )


@dataclass(frozen=True, kw_only=True)
class Scenario:
    sup: supervisor.Supervisor
    track: registry.PlanTrack
    native: RenumberingHerdr
    old_coordinate: str
    current_coordinate: str


def make_scenario(*, tmp_path: Path) -> Scenario:
    repo = tmp_path / "repo"
    repo.mkdir()
    recorded = herdr_identity.HerdrPaneTarget(
        socket_path="/run/herdr-renumber.sock",
        server_pid=3384132,
        server_starttime="server-start",
        pane_id="w1:p7",
    )
    process = PaneProcess(pid=2616353, starttime="session-start")
    native = RenumberingHerdr(
        repo=str(repo),
        recorded=recorded,
        current_pane_id="w5:p6",
        processes={"w5:p6": process},
        server_pid=recorded.server_pid,
        server_starttime=recorded.server_starttime,
    )
    driver = pane_router.MixedPaneDriver(tmux=FakeTmux(), herdr=native)
    sup = supervisor.Supervisor(
        tmux=driver,
        store_path=tmp_path / "mapping.jsonl",
        stamp_path=tmp_path / "stamps.json",
        out=io.StringIO(),
        require_render_terminal=False,
        now=lambda: 1000.0,
        sleep=lambda _seconds: None,
        starttime_of=native.starttime_of,
        codex_home=tmp_path / "no-codex",
        codex_pids_of_comm=lambda *, comm: [],
        runtime_model_of=lambda *, pid: None,
    )
    old_coordinate = herdr_identity.encode_herdr_target(target=recorded)
    current_coordinate = herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=recorded.socket_path,
            server_pid=recorded.server_pid,
            server_starttime=recorded.server_starttime,
            pane_id=native.current_pane_id,
        )
    )
    identity = f"claude:{process.pid}:{process.starttime}:renumbered"
    track = registry.PlanTrack(
        topic="renumbered",
        repo=str(repo),
        tmux=old_coordinate,
        epic="overseer-uzvcbn",
        observed_session_identity=identity,
    )
    registry.append_mapping(track=track, store_path=sup.store_path)
    for coordinate in (old_coordinate, current_coordinate):
        sup.claude_names_by_session[coordinate] = {track.topic}
        sup.claude_status_by_session[coordinate] = "idle"
        sup.claude_identity_by_session[(coordinate, track.topic)] = identity
    return Scenario(
        sup=sup,
        track=track,
        native=native,
        old_coordinate=old_coordinate,
        current_coordinate=current_coordinate,
    )


def test_acting_tick_rekeys_a_matching_renumbered_pane_and_logs_both_ids(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scenario = make_scenario(tmp_path=tmp_path)

    _ = scenario.sup.evaluate(track=scenario.track, act=True)

    stored = registry.read_valid_mapping(store_path=scenario.sup.store_path)[0]
    messages = [json.loads(line)["message"] for line in capsys.readouterr().err.splitlines()]
    assert stored.tmux == scenario.current_coordinate
    assert any("re-keyed renumbered herdr pane w1:p7 -> w5:p6" in message for message in messages)


def test_rekeyed_tick_supervises_the_live_current_pane(*, tmp_path: Path) -> None:
    scenario = make_scenario(tmp_path=tmp_path)

    row = scenario.sup.evaluate(track=scenario.track, act=True)

    assert row.status != "session-gone"
    assert row.ctx == 70
    assert ("capture", "w5:p6") in scenario.native.calls
