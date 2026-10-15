"""A daemon tick routes every track through its recorded terminal instance."""

from __future__ import annotations

import importlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import _supervisor_diagnostics
import _supervisor_discovery_adoption
import _supervisor_render
import herdr_adapter
import herdr_calls
import herdr_identity
import herdr_transport
import herdr_write
import registry
import supervisor
import terminal_ownership
import terminal_probes
from test_supervisor_builders import idle_capture
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

PACKAGE = Path(__file__).resolve().parents[2] / "overseer"
ROUTER_PATH = PACKAGE / "pane_router.py"


def _claude_composer(*, text: str) -> str:
    rule = "─" * 40
    first_line = next(line for line in text.splitlines() if line.strip())
    return f"{rule}\n❯ {first_line}\n{rule}\n"


@dataclass(kw_only=True)
class RecordedHerdr:
    captures: dict[str, str]
    repositories: dict[str, str]
    generations: dict[str, tuple[int, str]] = field(default_factory=dict)
    unavailable: set[str] = field(default_factory=set)
    calls: list[tuple[str, herdr_identity.HerdrPaneTarget]] = field(default_factory=list)

    def identify(self, *, socket_path: str) -> herdr_adapter.InstanceIdentification:
        generation = self.generations.get(socket_path)
        if generation is None:
            return herdr_adapter.InstanceIdentification(
                ok=False,
                peer=None,
                error="server is unavailable",
            )
        pid, starttime = generation
        return herdr_adapter.InstanceIdentification(
            ok=True,
            peer=herdr_transport.PeerIdentity(pid=pid, uid=1000, starttime=starttime),
            error="",
        )

    def list_panes(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_adapter.PaneListing:
        self.calls.append(("list", target))
        if target.socket_path in self.unavailable:
            return herdr_adapter.PaneListing(ok=False, panes=(), error="recorded server is gone")
        return herdr_adapter.PaneListing(
            ok=True,
            panes=(
                herdr_calls.PaneRow(
                    # list_panes receives an instance probe whose pane id is blank;
                    # the native API returns the pane ids owned by that instance.
                    pane_id="w1:p1",
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
    native: RecordedHerdr
    calls: list[tuple[str, herdr_identity.HerdrPaneTarget, str]] = field(default_factory=list)
    paste_outcome: herdr_write.WriteOutcome = field(
        default_factory=lambda: herdr_write.WriteOutcome(ok=True, error="", effect_unknown=False)
    )
    enter_outcome: herdr_write.WriteOutcome = field(
        default_factory=lambda: herdr_write.WriteOutcome(ok=True, error="", effect_unknown=False)
    )
    render_after_paste: bool = True
    render_after_enter: bool = True

    def bracketed_paste(
        self, *, target: herdr_identity.HerdrPaneTarget, text: str
    ) -> herdr_write.WriteOutcome:
        self.calls.append(("paste", target, text))
        self.native.calls.append(("paste", target))
        if self.paste_outcome.ok and self.render_after_paste:
            self.native.captures[target.socket_path] = _claude_composer(text=text)
        return self.paste_outcome

    def send_enter(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_write.WriteOutcome:
        self.calls.append(("enter", target, ""))
        self.native.calls.append(("enter", target))
        if self.enter_outcome.ok and self.render_after_enter:
            self.native.captures[target.socket_path] = (
                "✻ Working… (running stop hooks… 1/3 · 1s · ↓ 1 tokens)\n"
            )
        return self.enter_outcome


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
        generations={
            target_a.socket_path: (target_a.server_pid, target_a.server_starttime),
            target_b.socket_path: (target_b.server_pid, target_b.server_starttime),
        },
        unavailable={stale.socket_path},
    )
    writes, legacy = RecordedWrites(native=native), FakeTmux()
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
    alpha_operations = [
        operation for operation, target in scenario.native.calls if target == scenario.target_a
    ]
    assert alpha_operations[-4:] == ["paste", "capture", "enter", "capture"]
    assert scenario.writes.calls[0][:2] == ("paste", scenario.target_a)
    assert scenario.writes.calls[1][:2] == ("enter", scenario.target_a)
    assert any(call == ("capture", "legacy-topic") for call in scenario.legacy.calls)

    before = list(scenario.legacy.calls)
    assert scenario.driver.session_exists(session=scenario.stale_coordinate) is False
    assert (
        scenario.legacy.calls == before
    ), "an unavailable Herdr generation must not fall back to tmux"


def test_qualified_adoption_never_repoints_an_exact_target_to_a_namesake(
    *, tmp_path: Path, monkeypatch: Any
) -> None:
    repo = tmp_path / "repo"
    for topic in ("qualified", "legacy"):
        (repo / "plan" / topic).mkdir(parents=True)
    recorded = herdr_identity.encode_herdr_target(
        target=_target(socket_path="/run/herdr-recorded.sock", pid=401)
    )
    namesake = herdr_identity.encode_herdr_target(
        target=_target(socket_path="/run/herdr-namesake.sock", pid=402)
    )
    sup = _supervisor(tmp_path=tmp_path, driver=FakeTmux())
    registry.append_mapping(
        track=registry.PlanTrack(
            topic="qualified", repo=str(repo), tmux=recorded, epic="qualified"
        ),
        store_path=sup.store_path,
    )
    registry.append_mapping(
        track=registry.PlanTrack(topic="legacy", repo=str(repo), tmux="legacy-old", epic="legacy"),
        store_path=sup.store_path,
    )
    monkeypatch.setattr(
        _supervisor_discovery_adoption,
        "_adoptable_live_sessions",
        lambda *, sup, pane_pids: [
            (namesake, "qualified", str(repo)),
            ("legacy-new", "legacy", str(repo)),
        ],
    )
    monkeypatch.setattr(
        _supervisor_discovery_adoption,
        "_live_profile_sources",
        lambda *, sup, pane_pids: {},
    )

    assert _supervisor_discovery_adoption.adopt_sessions(sup=sup, watch=[str(repo)]) == []

    targets = {
        track.topic: track.tmux for track in registry.read_valid_mapping(store_path=sup.store_path)
    }
    assert targets == {"qualified": recorded, "legacy": "legacy-new"}


def test_policy_only_upsert_preserves_an_unqualified_legacy_target(*, tmp_path: Path) -> None:
    store = tmp_path / "mapping.jsonl"
    registry.append_mapping(
        track=registry.PlanTrack(
            topic="alpha",
            repo=str(tmp_path),
            tmux="operator-window",
            epic="alpha",
            ctx_threshold=45,
        ),
        store_path=store,
    )

    assert registry.upsert_mapping(
        track=registry.PlanTrack(
            topic="alpha",
            repo=str(tmp_path),
            tmux="derived-topic-name",
            epic="alpha",
            ctx_threshold=60,
        ),
        store_path=store,
        update_fields=frozenset({"tmux", "ctx_threshold"}),
        allow_retarget=False,
    )

    updated = registry.read_valid_mapping(store_path=store)[0]
    assert (updated.tmux, updated.ctx_threshold) == ("operator-window", 60)


def test_native_submit_refuses_to_replay_an_uncertain_paste(*, tmp_path: Path) -> None:
    module = importlib.import_module("pane_router")
    scenario = _scenario(tmp_path=tmp_path, pane_router=module)
    scenario.writes.paste_outcome = herdr_write.WriteOutcome(
        ok=False,
        error="reply lost after write",
        effect_unknown=True,
    )
    scenario.writes.render_after_paste = False
    # The composer holds text that is not the payload, so the paste is UNCONFIRMED, not
    # FAILED (SPECIFICATION v059): the attempt is held and the payload never replayed.
    scenario.writes.native.captures["/run/herdr-a.sock"] = _claude_composer(text="operator draft")

    assert scenario.sup._submit_prompt(target=scenario.coordinate_a, text="one prompt") is False
    assert scenario.sup._submit_prompt(target=scenario.coordinate_a, text="one prompt") is False

    assert [call[0] for call in scenario.writes.calls] == ["paste"]


def test_native_submit_releases_a_paste_never_seen_in_an_empty_composer(*, tmp_path: Path) -> None:
    """SPECIFICATION v059: an empty composer after the paste and before Enter is FAILED.

    Holding the attempt instead was the wedge that answered every later paste to the
    pane from a dead state, so the attempt is released and the next request pastes
    afresh. Nothing is ever submitted into the empty composer.
    """
    module = importlib.import_module("pane_router")
    scenario = _scenario(tmp_path=tmp_path, pane_router=module)
    scenario.writes.render_after_paste = False

    assert scenario.sup._submit_prompt(target=scenario.coordinate_a, text="one prompt") is False
    assert scenario.sup._submit_prompt(target=scenario.coordinate_a, text="one prompt") is False

    assert [call[0] for call in scenario.writes.calls] == ["paste", "paste"]


def test_native_submit_never_calls_an_acknowledged_but_visible_prompt_delivered(
    *, tmp_path: Path
) -> None:
    module = importlib.import_module("pane_router")
    scenario = _scenario(tmp_path=tmp_path, pane_router=module)
    scenario.writes.render_after_enter = False

    assert scenario.sup._submit_prompt(target=scenario.coordinate_a, text="one prompt") is False
    assert scenario.sup._submit_prompt(target=scenario.coordinate_a, text="one prompt") is False

    operations = [call[0] for call in scenario.writes.calls]
    assert operations.count("paste") == 1
    assert operations.count("enter") >= 2


@dataclass(kw_only=True)
class NamedTmuxProbe:
    socket_path: str
    calls: list[str] = field(default_factory=list)

    def endpoints(self, *, environ: Any) -> tuple[str, ...]:
        del environ
        return (terminal_probes.DEFAULT_TMUX_ENDPOINT, self.socket_path)

    def owned_panes(self, *, endpoint: str) -> terminal_ownership.ClaimReading:
        self.calls.append(endpoint)
        return terminal_ownership.ClaimReading(
            panes=(
                terminal_ownership.OwnedPane(
                    backend=herdr_identity.TMUX_BACKEND,
                    socket_path=endpoint,
                    server_pid=777,
                    server_starttime="named-start",
                    pane_id="%3",
                    pane_process_pids=(701,),
                ),
            ),
            error="",
        )


def test_named_tmux_adoption_records_the_exact_server_generation(
    *, tmp_path: Path, monkeypatch: Any
) -> None:
    module = importlib.import_module("pane_router")
    socket_path = str(tmp_path / "named-tmux.sock")
    probe = NamedTmuxProbe(socket_path=socket_path)
    monkeypatch.setenv(terminal_probes.TMUX_ENV, f"{socket_path},777,0")
    monkeypatch.setattr(terminal_probes, "TmuxOwnershipProbe", lambda **_kwargs: probe)
    ambient = FakeTmux()
    ambient.pane_pids[701] = "ambient-session"
    driver = module.MixedPaneDriver(tmux=ambient)

    coordinate = driver.pane_pid_sessions()[701]

    assert coordinate != "ambient-session"
    assert herdr_identity.decode_target(value=coordinate).tmux == herdr_identity.TmuxPaneTarget(
        socket_path=socket_path,
        server_pid=777,
        server_starttime="named-start",
        pane_id="%3",
    )
    assert probe.calls == [socket_path]


def test_production_router_discovers_the_default_herdr_socket_without_environment(
    *, tmp_path: Path, monkeypatch: Any
) -> None:
    module = importlib.import_module("pane_router")
    monkeypatch.delenv(terminal_probes.HERDR_SOCKET_ENV, raising=False)
    default_socket = str(tmp_path / ".config" / "herdr" / "herdr.sock")
    monkeypatch.setattr(
        terminal_probes,
        "default_herdr_socket",
        lambda *, home=None: default_socket,
    )
    target = _target(socket_path=default_socket, pid=606)
    native = RecordedHerdr(
        captures={default_socket: idle_capture(ctx=81)},
        repositories={default_socket: str(tmp_path)},
        generations={default_socket: (target.server_pid, target.server_starttime)},
    )
    writes = RecordedWrites(native=native)
    driver = module.MixedPaneDriver(tmux=FakeTmux(), herdr=native, herdr_writer=writes)

    coordinate = driver.pane_pid_sessions()[7000 + target.server_pid]

    assert herdr_identity.decode_target(value=coordinate).herdr == target


def test_herdr_attention_uses_native_coordinates_and_a_native_jump(
    *, tmp_path: Path, capsys: Any
) -> None:
    target = _target(socket_path="/run/herdr-attention.sock", pid=505)
    coordinate = herdr_identity.encode_herdr_target(target=target)
    row = supervisor.RowView(
        topic="alpha",
        repo=str(tmp_path / "repo"),
        tmux=coordinate,
        ctx=10,
        status="danger",
        runtime="claude",
    )

    rendered = "\n".join(_supervisor_render.attention_lines(rows=[row]))

    assert (
        "herdr: /run/herdr-attention.sock · server 505/start-505 · pane w1:p1 (claude)" in rendered
    )
    assert "jump: env HERDR_ENV=1 HERDR_SOCKET_PATH=/run/herdr-attention.sock" in rendered
    assert "HERDR_PANE_ID=w1:p1 herdr" in rendered
    assert "tmux switch-client" not in rendered

    sup = _supervisor(tmp_path=tmp_path, driver=FakeTmux())
    _supervisor_diagnostics.alert(
        request=_supervisor_diagnostics.AlertRequest(
            sup=sup,
            repo=str(tmp_path / "repo"),
            topic="alpha",
            session=coordinate,
            pane=coordinate,
            message="needs attention",
            condition="danger",
        )
    )
    event = json.loads(capsys.readouterr().err)
    message = event["message"]
    assert "herdr socket '/run/herdr-attention.sock' server 505/start-505 pane w1:p1" in message
    assert "jump: env HERDR_ENV=1 HERDR_SOCKET_PATH=/run/herdr-attention.sock" in message
    assert "tmux session" not in message


def test_herdr_picker_reminder_is_delivered_as_paste_without_submission(*, tmp_path: Path) -> None:
    module = importlib.import_module("pane_router")
    scenario = _scenario(tmp_path=tmp_path, pane_router=module)

    assert (
        scenario.driver.bracketed_paste(
            session=scenario.coordinate_a,
            text="Charter reminder only",
        )
        is True
    )

    assert scenario.writes.calls == [("paste", scenario.target_a, "Charter reminder only")]
