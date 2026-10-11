"""Public deliberate-start behavior for exact Herdr panes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import herdr_identity
import pane_router
import registry
import supervisor
from test_supervisor_builders import isolate_store, make_plan

__all__: list[str] = []


def _coordinate(*, pane_id: str) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/run/user/1000/herdr-start.sock",
            server_pid=4242,
            server_starttime="987654",
            pane_id=pane_id,
        )
    )


@dataclass(kw_only=True)
class NativeStartDriver:
    owner: str
    created: str
    live: dict[str, str] = field(default_factory=dict)
    calls: list[tuple[str, str]] = field(default_factory=list)

    def session_exists(self, *, session: str) -> bool:
        return session == self.owner or session in self.live

    def pane_current_command(self, *, session: str) -> str | None:
        return self.live.get(session, "bash" if session == self.owner else None)

    def create_initial_pane(self, *, source: str, name: str, cwd: str) -> Any:
        assert source == self.owner
        self.calls.append(("create", source))
        self.live[self.created] = "bash"
        return SimpleNamespace(ok=True, target=self.created, error="", effect_unknown=False)

    def launch_initial_agent(
        self,
        *,
        session: str,
        cwd: str,
        command: str,
        env: object,
        expected_process: str,
    ) -> Any:
        del cwd, command, env
        self.calls.append(("launch", session))
        self.live[session] = expected_process
        return SimpleNamespace(ok=True, target=session, error="", effect_unknown=False)

    def pane_id(self, *, session: str) -> str | None:
        return session if session in self.live else None

    def capture_pane(self, *, session: str) -> str:
        assert session in self.live
        return "─\n❯ \n─\n"

    def submit_prompt_once(
        self, *, session: str, text: str, expect_codex: bool, sleep: object
    ) -> tuple[bool, bool]:
        del text, expect_codex, sleep
        self.calls.append(("resume", session))
        return True, False


def test_public_start_launches_the_exact_created_herdr_pane_once(
    *, tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    repo, topic = make_plan(tmp_path=tmp_path)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    claude = tmp_path / "bin" / "claude"
    claude.parent.mkdir()
    claude.write_text("#!/bin/sh\n", encoding="utf-8")
    claude.chmod(0o755)
    monkeypatch.setenv("PATH", str(claude.parent))
    owner = _coordinate(pane_id="w2:p1")
    created = _coordinate(pane_id="w2:p9")
    assert created != owner
    driver = NativeStartDriver(owner=owner, created=created)
    monkeypatch.setattr(pane_router, "current_process_coordinate", lambda: owner)
    monkeypatch.setattr(pane_router, "default_pane_driver", lambda: driver)

    argv = ["start", "--repo", str(repo), "--topic", topic]
    assert supervisor.main(argv=argv) == 0
    assert supervisor.main(argv=argv) == 0

    assert driver.calls.count(("create", owner)) == 1
    assert driver.calls.count(("launch", created)) == 1
    rows = registry.read_valid_mapping(store_path=store)
    assert len(rows) == 1
    assert rows[0].tmux == created
    assert herdr_identity.decode_herdr_target(
        value=rows[0].tmux
    ) == herdr_identity.decode_herdr_target(value=created)
    assert "already running" in capsys.readouterr().out
