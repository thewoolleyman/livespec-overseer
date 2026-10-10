"""Policy updates preserve qualified pane identity and legacy tmux behavior."""

from __future__ import annotations

import json
import types
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from overseer import (
    _supervisor_launch_profile,
    herdr_identity,
    pane_router,
    registry,
    supervisor,
)
from overseer.test_supervisor_builders import isolate_store
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@dataclass(kw_only=True)
class RecordingTmuxRun:
    captures: dict[str, str]
    calls: list[list[str]] = field(default_factory=list)

    def __call__(
        self,
        argv: Sequence[str],
        *,
        input: str | None = None,
        capture_output: bool | None = None,
        text: bool | None = None,
        check: bool | None = None,
        timeout: float | None = None,
    ) -> Any:
        del input, capture_output, text, check, timeout
        call = list(argv)
        self.calls.append(call)
        socket = call[2]
        command = call[5]
        stdout = ""
        if "capture-pane" in command:
            stdout = self.captures[socket]
        elif "#{pane_pid}" in command:
            stdout = "%0\t1\t4101\n"
        elif "#{pane_current_command}" in command:
            stdout = "%0\t1\tclaude\n"
        elif "#{pane_current_path}" in command:
            stdout = "%0\t1\t/repo\n"
        elif "#{pane_id}" in command:
            stdout = "%0\t1\t%0\n"
        return types.SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def _herdr_coordinate(*, socket: str, pid: int, pane: str = "w1:p1") -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=socket,
            server_pid=pid,
            server_starttime=f"start-{pid}",
            pane_id=pane,
        )
    )


def _assert_policy_updates(*, tmp_path: Path, monkeypatch: Any) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    for topic in ("alpha", "beta"):
        (repo / "plan" / topic).mkdir(parents=True)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    coordinate = _herdr_coordinate(socket="/run/herdr-a.sock", pid=701)
    original: dict[str, object] = {
        "kind": "plan",
        "topic": "alpha",
        "repo": str(repo),
        "tmux": coordinate,
        "resume": "preserve this resume",
        "epic": "overseer-alpha",
        "ctx_threshold": 45,
        "idle_nudge": False,
        "pinned_session_id": "session-alpha",
        "observed_session_identity": "claude:1001:start:alpha",
        "added_at": "2026-10-10T12:00:00Z",
        "model_profile": {"harness": "claude", "model": "opus[1m]", "wrapper": None},
        "future_field": {"kept": True},
    }
    store.write_text(json.dumps(original) + "\n", encoding="utf-8")

    assert (
        supervisor.main(
            argv=["add", "--repo", str(repo), "--topic", "alpha", "--ctx-threshold", "60"]
        )
        == 0
    )
    updated = json.loads(store.read_text(encoding="utf-8").splitlines()[0])
    assert updated == {**original, "ctx_threshold": 60}

    track = registry.read_valid_mapping(store_path=store)[0]
    launch = _supervisor_launch_profile.claude_launch_plan(track=track)
    assert isinstance(launch, _supervisor_launch_profile.ClaudeLaunchPlan)
    assert launch.command == "claude --model 'opus[1m]' --dangerously-skip-permissions -n alpha"
    assert launch.env == {
        "ANTHROPIC_MODEL": None,
        "ANTHROPIC_SMALL_FAST_MODEL": None,
        "CLAUDE_CODE_DISABLE_1M_CONTEXT": None,
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": None,
    }

    assert (
        supervisor.main(
            argv=["add", "--repo", str(repo), "--topic", "beta", "--ctx-threshold", "55"]
        )
        == 0
    )
    rows = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
    beta = next(row for row in rows if row["topic"] == "beta")
    assert beta["tmux"] == "beta"
    assert beta["ctx_threshold"] == 55

    replacement = _herdr_coordinate(socket="/run/herdr-b.sock", pid=702, pane="w1:p9")
    assert (
        supervisor.main(
            argv=[
                "add",
                "--repo",
                str(repo),
                "--topic",
                "alpha",
                "--retarget",
                replacement,
            ]
        )
        == 0
    )
    rows = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
    alpha = next(row for row in rows if row["topic"] == "alpha")
    assert alpha == {**original, "tmux": replacement, "ctx_threshold": 60}
    return repo, replacement


def _assert_qualified_tmux_routing(
    *, repo: Path, replacement: str, monkeypatch: Any
) -> tuple[pane_router.MixedPaneDriver, FakeTmux]:
    target_a = herdr_identity.TmuxPaneTarget(
        socket_path="/run/tmux-a.sock",
        server_pid=801,
        server_starttime="tmux-start-801",
        pane_id="%0",
    )
    target_b = herdr_identity.TmuxPaneTarget(
        socket_path="/run/tmux-b.sock",
        server_pid=802,
        server_starttime="tmux-start-802",
        pane_id="%0",
    )
    tmux_a = herdr_identity.encode_tmux_target(target=target_a)
    tmux_b = herdr_identity.encode_tmux_target(target=target_b)
    native = RecordingTmuxRun(
        captures={target_a.socket_path: "\x1b[2mserver-a\x1b[0m", target_b.socket_path: "server-b"}
    )
    legacy = FakeTmux()
    legacy.serve(session="legacy", repo=repo, capture="legacy capture")
    legacy.pane_titles["daemon"] = "legacy"
    legacy.pane_pids[4100] = "legacy"
    driver = pane_router.MixedPaneDriver(tmux=legacy, tmux_run=native)
    monkeypatch.setenv("TMUX", "/run/rival.sock,999,0")

    assert driver.capture_pane(session=tmux_a) == "\x1b[2mserver-a\x1b[0m"
    assert driver.capture_pane(session=tmux_b) == "server-b"
    assert driver.pane_id(session=tmux_a) == tmux_a
    assert driver.pane_pid(session=tmux_a) == 4101
    assert driver.pane_current_command(session=tmux_a) == "claude"
    assert driver.pane_current_path(session=tmux_a) == "/repo"
    assert driver.session_exists(session=tmux_a) is True
    assert driver.send_keys(session=tmux_a, keys="Enter") is True
    assert driver.bracketed_paste(session=tmux_a, text="one\ntwo") is True
    assert (
        driver.respawn_pane(
            session=tmux_a,
            cwd="/repo",
            command="claude",
            env={"ANTHROPIC_MODEL": None},
        )
        is True
    )
    assert driver.rename_window(pane=tmux_a, name="overseer") is True
    assert driver.pane_by_title(pane=tmux_a, title="daemon") is None
    assert driver.new_session(name=tmux_a, cwd="/repo") is False
    assert driver.kill_session(session=tmux_a) is False
    assert all(
        call[:3] in (["tmux", "-S", target_a.socket_path], ["tmux", "-S", target_b.socket_path])
        for call in native.calls
    )
    assert all("/run/rival.sock" not in call for call in native.calls)
    assert any(str(target_a.server_pid) in call[4] for call in native.calls)
    assert any(target_a.server_starttime in call[4] for call in native.calls)
    assert driver.respawn_pane(session=replacement, cwd="/repo", command="claude") is False
    return driver, legacy


def _assert_legacy_tmux_controls(
    *, driver: pane_router.MixedPaneDriver, legacy: FakeTmux, repo: Path
) -> None:
    assert driver.capture_pane(session="legacy") == "legacy capture"
    assert driver.pane_id(session="legacy") == "legacy"
    assert driver.pane_by_title(pane="legacy", title="daemon") == "legacy"
    assert driver.pane_current_command(session="legacy") == "node"
    assert driver.pane_current_path(session="legacy") == str(repo)
    assert driver.session_exists(session="legacy") is True
    assert driver.pane_pid_sessions()[4100] == "legacy"
    assert driver.send_keys(session="legacy", keys="Enter") is True
    assert driver.bracketed_paste(session="legacy", text="legacy") is True
    assert driver.respawn_pane(session="legacy", cwd=str(repo), command="claude") is True
    assert driver.new_session(name="new-legacy", cwd=str(repo)) is True
    assert driver.kill_session(session="new-legacy") is True
    assert driver.rename_window(pane="legacy", name="legacy-overseer") is True


def test_policy_updates_preserve_identity_and_explicit_retarget_is_the_only_override(
    *, tmp_path: Path, monkeypatch: Any
) -> None:
    repo, replacement = _assert_policy_updates(tmp_path=tmp_path, monkeypatch=monkeypatch)
    driver, legacy = _assert_qualified_tmux_routing(
        repo=repo, replacement=replacement, monkeypatch=monkeypatch
    )
    _assert_legacy_tmux_controls(driver=driver, legacy=legacy, repo=repo)
