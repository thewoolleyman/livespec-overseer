"""A daemon tick routes every track through its recorded terminal instance."""

from __future__ import annotations

import importlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import herdr_adapter
import herdr_calls
import herdr_identity
import herdr_write
import registry
import supervisor
from test_supervisor_builders import idle_capture
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

PACKAGE = Path(__file__).resolve().parent.parent / "overseer"
ROUTER_PATH = PACKAGE / "pane_router.py"


@dataclass(kw_only=True)
class RecordedHerdr:
    captures: dict[str, str]
    repositories: dict[str, str]
    unavailable: set[str] = field(default_factory=set)
    calls: list[tuple[str, herdr_identity.HerdrPaneTarget]] = field(default_factory=list)

    def list_panes(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_adapter.PaneListing:
        self.calls.append(("list", target))
        if target.socket_path in self.unavailable:
            return herdr_adapter.PaneListing(ok=False, panes=(), error="recorded server is gone")
        return herdr_adapter.PaneListing(
            ok=True,
            panes=(
                herdr_calls.PaneRow(
                    pane_id=target.pane_id,
                    tab_id="w1:t1",
                    workspace_id="w1",
                    cwd=self.repositories[target.socket_path],
                    foreground_cwd=self.repositories[target.socket_path],
                    focused=False,
                ),
            ),
            error="",
        )

    def capture_pane(
        self, *, target: herdr_identity.HerdrPaneTarget, retain_ansi: bool = True
    ) -> herdr_adapter.PaneCapture:
        assert retain_ansi is True
        self.calls.append(("capture", target))
        return herdr_adapter.PaneCapture(
            ok=True,
            text=self.captures[target.socket_path],
            error="",
        )

    def foreground(
        self, *, target: herdr_identity.HerdrPaneTarget
    ) -> herdr_adapter.ForegroundReading:
        self.calls.append(("foreground", target))
        return herdr_adapter.ForegroundReading(
            ok=True,
            process=herdr_calls.ForegroundProcess(
                pane_id=target.pane_id,
                shell_pid=7000 + target.server_pid,
                process_group_id=8000 + target.server_pid,
                name="claude",
                cmdline="claude --dangerously-skip-permissions",
                cwd=self.repositories[target.socket_path],
            ),
            error="",
        )


@dataclass(kw_only=True)
class RecordedWrites:
    calls: list[tuple[str, herdr_identity.HerdrPaneTarget, str]] = field(default_factory=list)

    def bracketed_paste(
        self, *, target: herdr_identity.HerdrPaneTarget, text: str
    ) -> herdr_write.WriteOutcome:
        self.calls.append(("paste", target, text))
        return herdr_write.WriteOutcome(ok=True, error="", effect_unknown=False)

    def send_enter(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_write.WriteOutcome:
        self.calls.append(("enter", target, ""))
        return herdr_write.WriteOutcome(ok=True, error="", effect_unknown=False)


@dataclass(frozen=True, kw_only=True)
class Scenario:
    sup: supervisor.Supervisor
    native: RecordedHerdr
    writes: RecordedWrites
    legacy: FakeTmux
    driver: Any
    target_a: herdr_identity.HerdrPaneTarget
    coordinate_a: str
    coordinate_b: str
    stale_coordinate: str
    tracks: tuple[registry.PlanTrack, registry.PlanTrack, registry.PlanTrack]


def _target(*, socket_path: str, pid: int) -> herdr_identity.HerdrPaneTarget:
    return herdr_identity.HerdrPaneTarget(
        socket_path=socket_path,
        server_pid=pid,
        server_starttime=f"start-{pid}",
        pane_id="w1:p1",
    )


def _supervisor(*, tmp_path: Path, driver: Any) -> supervisor.Supervisor:
    return supervisor.Supervisor(
        tmux=driver,
        store_path=tmp_path / "mapping.jsonl",
        stamp_path=tmp_path / "stamps.json",
        out=io.StringIO(),
        require_render_terminal=False,
        now=lambda: 1000.0,
        sleep=lambda _seconds: None,
        codex_home=tmp_path / "no-codex",
        codex_pids_of_comm=lambda *, comm: [],
        runtime_model_of=lambda *, pid: None,
    )


def _scenario(*, tmp_path: Path, pane_router: Any) -> Scenario:
    repo_a, repo_b, repo_legacy = (tmp_path / name for name in ("repo-a", "repo-b", "repo-legacy"))
    for repo in (repo_a, repo_b, repo_legacy):
        repo.mkdir()
    target_a = _target(socket_path="/run/herdr-a.sock", pid=101)
    target_b = _target(socket_path="/run/herdr-b.sock", pid=202)
    stale = _target(socket_path="/run/herdr-stale.sock", pid=303)
    coordinate_a, coordinate_b, stale_coordinate = (
        herdr_identity.encode_herdr_target(target=target) for target in (target_a, target_b, stale)
    )
    native = RecordedHerdr(
        captures={
            target_a.socket_path: "\x1b[2mnative-a\x1b[0m\n" + idle_capture(ctx=40),
            target_b.socket_path: "\x1b[2mnative-b\x1b[0m\n" + idle_capture(ctx=70),
        },
        repositories={target_a.socket_path: str(repo_a), target_b.socket_path: str(repo_b)},
        unavailable={stale.socket_path},
    )
    writes, legacy = RecordedWrites(), FakeTmux()
    legacy.serve(session="legacy-topic", repo=repo_legacy, capture=idle_capture(ctx=65))
    driver = pane_router.MixedPaneDriver(tmux=legacy, herdr=native, herdr_writer=writes)
    sup = _supervisor(tmp_path=tmp_path, driver=driver)
    sup.claude_names_by_session = {
        coordinate_a: {"alpha"},
        coordinate_b: {"beta"},
        "legacy-topic": {"legacy"},
    }
    sup.claude_status_by_session = {
        coordinate_a: "idle",
        coordinate_b: "idle",
        "legacy-topic": "idle",
    }
    tracks = (
        registry.PlanTrack(topic="alpha", repo=str(repo_a), tmux=coordinate_a, epic="alpha"),
        registry.PlanTrack(topic="beta", repo=str(repo_b), tmux=coordinate_b, epic="beta"),
        registry.PlanTrack(
            topic="legacy", repo=str(repo_legacy), tmux="legacy-topic", epic="legacy"
        ),
    )
    return Scenario(
        sup=sup,
        native=native,
        writes=writes,
        legacy=legacy,
        driver=driver,
        target_a=target_a,
        coordinate_a=coordinate_a,
        coordinate_b=coordinate_b,
        stale_coordinate=stale_coordinate,
        tracks=tracks,
    )


def test_mixed_daemon_routes_equal_pane_ids_to_their_recorded_generations(
    *, tmp_path: Path
) -> None:
    assert ROUTER_PATH.is_file(), "the daemon needs a qualified per-track pane router"
    pane_router = importlib.import_module("pane_router")
    scenario = _scenario(tmp_path=tmp_path, pane_router=pane_router)
    alpha, beta, legacy_track = scenario.tracks
    alpha_row = scenario.sup.evaluate(track=alpha, act=True)
    beta_row = scenario.sup.evaluate(track=beta, act=False)
    legacy_row = scenario.sup.evaluate(track=legacy_track, act=False)

    assert (alpha_row.ctx, beta_row.ctx, legacy_row.ctx) == (40, 70, 65)
    assert [call[1] for call in scenario.native.calls if call[0] == "capture"] == [
        scenario.target_a,
        scenario.target_a,
        scenario.target_a,
        scenario.target_a,
        scenario.target_a,
        herdr_identity.decode_target(value=scenario.coordinate_b).herdr,
    ]
    assert scenario.writes.calls[0][:2] == ("paste", scenario.target_a)
    assert scenario.writes.calls[1][:2] == ("enter", scenario.target_a)
    assert any(call == ("capture", "legacy-topic") for call in scenario.legacy.calls)

    before = list(scenario.legacy.calls)
    assert scenario.driver.session_exists(session=scenario.stale_coordinate) is False
    assert (
        scenario.legacy.calls == before
    ), "an unavailable Herdr generation must not fall back to tmux"
