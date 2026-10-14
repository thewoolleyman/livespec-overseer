"""A live Herdr process survives positional pane renumbering."""

from __future__ import annotations

import argparse
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import _supervisor_cli_actions
import codex_sessions
import herdr_adapter
import herdr_calls
import herdr_identity
import herdr_transport
import pane_router
import pytest
import registry
import supervisor
from test_supervisor_builders import declare, idle_capture
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@dataclass(frozen=True, kw_only=True)
class PaneProcess:
    pid: int
    starttime: str
    name: str = "claude"


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
                name=process.name,
                cmdline=f"{process.name} --dangerously-skip-permissions",
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


def make_scenario(
    *, tmp_path: Path, observed_session_identity: str | None = "matching"
) -> Scenario:
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
    actual_identity = f"claude:{process.pid}:{process.starttime}:renumbered"
    recorded_identity = (
        actual_identity if observed_session_identity == "matching" else observed_session_identity
    )
    track = registry.PlanTrack(
        topic="renumbered",
        repo=str(repo),
        tmux=old_coordinate,
        epic="overseer-uzvcbn",
        observed_session_identity=recorded_identity,
    )
    registry.append_mapping(track=track, store_path=sup.store_path)
    for coordinate in (old_coordinate, current_coordinate):
        sup.claude_names_by_session[coordinate] = {track.topic}
        sup.claude_status_by_session[coordinate] = "idle"
        sup.claude_identity_by_session[(coordinate, track.topic)] = actual_identity
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


def test_rekey_finds_the_matching_session_when_the_old_pane_id_was_reused(
    *, tmp_path: Path
) -> None:
    scenario = make_scenario(tmp_path=tmp_path)
    scenario.native.processes["w1:p7"] = PaneProcess(
        pid=909090,
        starttime="replacement-session-start",
    )

    row = scenario.sup.evaluate(track=scenario.track, act=True)

    stored = registry.read_valid_mapping(store_path=scenario.sup.store_path)[0]
    assert stored.tmux == scenario.current_coordinate
    assert row.tmux == scenario.current_coordinate
    assert ("capture", "w5:p6") in scenario.native.calls
    assert ("capture", "w1:p7") not in scenario.native.calls


def test_matching_session_at_the_recorded_pane_id_remains_managed(*, tmp_path: Path) -> None:
    scenario = make_scenario(tmp_path=tmp_path)
    process = scenario.native.processes.pop("w5:p6")
    scenario.native.processes["w1:p7"] = process

    row = scenario.sup.evaluate(track=scenario.track, act=True)

    stored = registry.read_valid_mapping(store_path=scenario.sup.store_path)[0]
    assert stored.tmux == scenario.old_coordinate
    assert row.tmux == scenario.old_coordinate
    assert row.ctx == 70
    assert ("capture", "w1:p7") in scenario.native.calls


def test_rekey_refuses_the_current_pane_when_the_mapping_cannot_be_persisted(
    *, tmp_path: Path
) -> None:
    scenario = make_scenario(tmp_path=tmp_path)
    scenario.sup.store_path.unlink()

    row = scenario.sup.evaluate(track=scenario.track, act=True)

    assert not scenario.sup.store_path.exists()
    assert row.status == "session-gone"
    assert row.tmux is None


def test_rekeyed_track_alerts_jump_to_the_current_pane(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scenario = make_scenario(tmp_path=tmp_path)
    declare(
        repo=Path(scenario.track.repo),
        topic=scenario.track.topic,
        value="blocked: operator decision needed",
    )

    row = scenario.sup.evaluate(track=scenario.track, act=True)

    messages = [json.loads(line)["message"] for line in capsys.readouterr().err.splitlines()]
    alerts = [message for message in messages if "jump:" in message]
    assert row.status == "blocked:human"
    assert any("HERDR_PANE_ID=w5:p6 herdr" in message for message in alerts)
    assert all("HERDR_PANE_ID=w1:p7 herdr" not in message for message in alerts)


def test_renumbered_pane_with_mismatched_process_identity_stays_unmanaged(
    *, tmp_path: Path
) -> None:
    mismatches = {
        "pid": "claude:999999:session-start:renumbered",
        "starttime": "claude:2616353:different-start:renumbered",
    }
    for name, identity in mismatches.items():
        case_path = tmp_path / name
        case_path.mkdir()
        scenario = make_scenario(
            tmp_path=case_path,
            observed_session_identity=identity,
        )

        row = scenario.sup.evaluate(track=scenario.track, act=True)

        stored = registry.read_valid_mapping(store_path=scenario.sup.store_path)[0]
        assert stored.tmux == scenario.old_coordinate
        assert row.status == "session-gone"
        assert row.tmux is None


def test_renumbered_pane_on_replaced_herdr_server_stays_unmanaged(*, tmp_path: Path) -> None:
    scenario = make_scenario(tmp_path=tmp_path)
    scenario.native.server_pid = 4433221
    scenario.native.server_starttime = "replacement-server-start"

    row = scenario.sup.evaluate(track=scenario.track, act=True)

    stored = registry.read_valid_mapping(store_path=scenario.sup.store_path)[0]
    assert stored.tmux == scenario.old_coordinate
    assert row.status == "session-gone"
    assert row.tmux is None


def test_renumbered_pane_without_recorded_session_identity_stays_unmanaged(
    *, tmp_path: Path
) -> None:
    scenario = make_scenario(tmp_path=tmp_path, observed_session_identity=None)

    row = scenario.sup.evaluate(track=scenario.track, act=True)

    stored = registry.read_valid_mapping(store_path=scenario.sup.store_path)[0]
    assert stored.tmux == scenario.old_coordinate
    assert row.status == "session-gone"
    assert row.tmux is None


@pytest.mark.parametrize(
    "recorded_identity",
    [
        "codex:0199a767-c521-7af0-a31d-a65b6486c9cf",
        "claude:not-a-pid:session-start:renumbered",
        "legacy-identity",
    ],
)
def test_unusable_recorded_identity_refuses_rekey_without_raising(
    *, tmp_path: Path, recorded_identity: str
) -> None:
    scenario = make_scenario(
        tmp_path=tmp_path,
        observed_session_identity=recorded_identity,
    )

    row = scenario.sup.evaluate(track=scenario.track, act=True)

    stored = registry.read_valid_mapping(store_path=scenario.sup.store_path)[0]
    assert stored.tmux == scenario.old_coordinate
    assert row.status == "session-gone"
    assert row.tmux is None


def test_malformed_herdr_coordinate_refuses_rekey_without_raising(*, tmp_path: Path) -> None:
    scenario = make_scenario(tmp_path=tmp_path)
    malformed_coordinate = f"{herdr_identity.HERDR_SCHEME}malformed"
    assert registry.repoint_tmux(
        repo=scenario.track.repo,
        topic=scenario.track.topic,
        new_tmux=malformed_coordinate,
        store_path=scenario.sup.store_path,
    )
    track = registry.read_valid_mapping(store_path=scenario.sup.store_path)[0]

    row = scenario.sup.evaluate(track=track, act=True)

    stored = registry.read_valid_mapping(store_path=scenario.sup.store_path)[0]
    assert stored.tmux == malformed_coordinate
    assert row.status == "session-gone"
    assert row.tmux is None


def test_read_only_tick_reports_renumbered_pane_without_rewriting_mapping(
    *, tmp_path: Path
) -> None:
    scenario = make_scenario(tmp_path=tmp_path)

    row = scenario.sup.evaluate(track=scenario.track, act=False)

    stored = registry.read_valid_mapping(store_path=scenario.sup.store_path)[0]
    assert stored.tmux == scenario.old_coordinate
    assert row.status != "session-gone"
    assert row.tmux == scenario.current_coordinate
    assert row.ctx == 70


def test_reused_pane_id_without_recorded_identity_or_topic_name_stays_unmanaged(
    *, tmp_path: Path
) -> None:
    scenario = make_scenario(tmp_path=tmp_path, observed_session_identity=None)
    scenario.native.processes["w1:p7"] = PaneProcess(
        pid=909090,
        starttime="replacement-session-start",
    )
    del scenario.sup.claude_names_by_session[scenario.old_coordinate]

    row = scenario.sup.evaluate(track=scenario.track, act=True)

    stored = registry.read_valid_mapping(store_path=scenario.sup.store_path)[0]
    assert stored.tmux == scenario.old_coordinate
    assert row.status == "session-gone"
    assert row.tmux is None
    assert ("capture", "w1:p7") not in scenario.native.calls


def test_pane_without_recorded_identity_stays_managed_when_its_claude_names_the_topic(
    *, tmp_path: Path
) -> None:
    scenario = make_scenario(tmp_path=tmp_path, observed_session_identity=None)
    process = scenario.native.processes.pop("w5:p6")
    scenario.native.processes["w1:p7"] = process

    row = scenario.sup.evaluate(track=scenario.track, act=True)

    stored = registry.read_valid_mapping(store_path=scenario.sup.store_path)[0]
    assert stored.tmux == scenario.old_coordinate
    assert row.tmux == scenario.old_coordinate
    assert row.ctx == 70
    assert ("capture", "w1:p7") in scenario.native.calls


def test_codex_track_with_recorded_codex_identity_stays_managed_at_its_recorded_pane(
    *, tmp_path: Path
) -> None:
    codex_identity = "codex:0199a767-c521-7af0-a31d-a65b6486c9cf"
    scenario = make_scenario(tmp_path=tmp_path, observed_session_identity=codex_identity)
    scenario.native.processes.pop("w5:p6")
    scenario.native.processes["w1:p7"] = PaneProcess(
        pid=5150,
        starttime="codex-start",
        name="codex",
    )
    del scenario.sup.claude_names_by_session[scenario.old_coordinate]
    scenario.sup.live_codex[(scenario.old_coordinate, scenario.track.topic)] = (
        codex_sessions.CodexSession(
            pid=5150,
            name=scenario.track.topic,
            cwd=scenario.track.repo,
            session_id="0199a767-c521-7af0-a31d-a65b6486c9cf",
        )
    )

    row = scenario.sup.evaluate(track=scenario.track, act=True)

    stored = registry.read_valid_mapping(store_path=scenario.sup.store_path)[0]
    assert stored.tmux == scenario.old_coordinate
    assert row.status != "session-gone"
    assert row.tmux == scenario.old_coordinate
    assert ("capture", "w1:p7") in scenario.native.calls


def test_list_command_reports_renumbered_pane_without_rewriting_mapping(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scenario = make_scenario(tmp_path=tmp_path)
    (Path(scenario.track.repo) / "plan" / scenario.track.topic).mkdir(parents=True)
    sessions_dir = tmp_path / "claude-sessions"
    sessions_dir.mkdir()
    scenario.sup.watch_repos = [scenario.track.repo]
    scenario.sup.sessions_dir = str(sessions_dir)
    store_before = scenario.sup.store_path.read_bytes()

    exit_code = _supervisor_cli_actions.list_once(
        args=argparse.Namespace(json=True),
        build_supervisor=lambda: scenario.sup,
    )

    rows = json.loads(capsys.readouterr().out)["rows"]
    row = next(row for row in rows if row["topic"] == scenario.track.topic)
    assert exit_code == 0
    assert scenario.sup.store_path.read_bytes() == store_before
    assert row["status"] != "session-gone"
    assert row["tmux"] == scenario.current_coordinate
