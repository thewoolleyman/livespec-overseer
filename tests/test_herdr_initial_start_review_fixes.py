"""Review regressions for durable mapping and native launch cwd semantics."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import _supervisor_cli_update
import bootstrap_journal
import herdr_identity
import herdr_initial_start
import herdr_transport
import pane_router
import supervisor
from test_supervisor_builders import isolate_store, make_plan

__all__: list[str] = []


def _coordinate(*, pane_id: str) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/run/user/1000/herdr-review.sock",
            server_pid=6262,
            server_starttime="765432",
            pane_id=pane_id,
        )
    )


@dataclass(kw_only=True)
class PublicStartDriver:
    owner: str
    created: str
    process_cwd: str
    live: dict[str, str] = field(default_factory=dict)
    calls: list[tuple[str, str]] = field(default_factory=list)

    def pending_initial_start(self, *, repo: str, topic: str, session: str) -> str:
        del repo, topic, session
        return ""

    def session_exists(self, *, session: str) -> bool:
        return session == self.owner or session in self.live

    def pane_current_command(self, *, session: str) -> str | None:
        return self.live.get(session, "bash" if session == self.owner else None)

    def pane_current_path(self, *, session: str) -> str | None:
        return self.process_cwd if session in self.live else None

    def create_initial_pane(self, *, source: str, name: str, cwd: str) -> Any:
        del name, cwd
        assert source == self.owner
        self.calls.append(("create", source))
        self.live[self.created] = "bash"
        return SimpleNamespace(ok=True, target=self.created, error="", effect_unknown=False)

    def created_initial_pane_persisted(self, *, repo: str, topic: str, session: str) -> None:
        del repo, topic
        self.calls.append(("persisted", session))

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

    def finish_initial_agent(self, *, repo: str, session: str, unresolved: bool) -> None:
        del repo
        self.calls.append(("finish-unresolved" if unresolved else "finish", session))

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

    def preserve_initial_pane(self, *, session: str) -> bool:
        self.calls.append(("preserve", session))
        return False

    cleanup_initial_pane = preserve_initial_pane


def _public_context(
    *, tmp_path: Path, monkeypatch: Any, process_cwd: str
) -> tuple[Path, str, str, PublicStartDriver]:
    repo, topic = make_plan(tmp_path=tmp_path)
    _ = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    owner = _coordinate(pane_id="w2:p1")
    created = _coordinate(pane_id="w2:p9")
    assert created != owner
    driver = PublicStartDriver(owner=owner, created=created, process_cwd=process_cwd)
    monkeypatch.setattr(pane_router, "current_process_coordinate", lambda: owner)
    monkeypatch.setattr(pane_router, "default_pane_driver", lambda: driver)
    return repo, topic, created, driver


def test_created_native_pane_is_not_launched_when_its_mapping_cannot_persist(
    *, tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    repo, topic, created, driver = _public_context(
        tmp_path=tmp_path, monkeypatch=monkeypatch, process_cwd=str(tmp_path)
    )
    monkeypatch.setattr(_supervisor_cli_update, "upsert_track", lambda **_kwargs: False)

    result = supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic])

    assert result == 1
    assert driver.calls == [("create", driver.owner)]
    error = capsys.readouterr().err
    assert "persist" in error.lower()
    assert created in error


def test_native_start_remains_unresolved_when_the_observed_process_cwd_drifted(
    *, tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    repo, topic, created, driver = _public_context(
        tmp_path=tmp_path, monkeypatch=monkeypatch, process_cwd=str(elsewhere)
    )

    result = supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic])

    assert result == 1
    assert ("resume", created) not in driver.calls
    assert ("finish-unresolved", created) in driver.calls
    error = capsys.readouterr().err
    assert created in error
    assert "preserved_uncertain" in error


@dataclass(kw_only=True)
class CoherentLaunchWorld:
    pane_id: str
    repo: str
    sent: bool = False
    launch_text: str = ""

    @staticmethod
    def _reply(*, result: dict[str, object]) -> herdr_transport.RpcOutcome:
        return herdr_transport.RpcOutcome(
            ok=True,
            result=result,
            error="",
            peer=None,
            timed_out=False,
            request_sent=True,
        )

    def request(
        self, *, target: object, method: str, params: dict[str, object], expect: object
    ) -> herdr_transport.RpcOutcome:
        del target, expect
        if method == "pane.send_input":
            self.sent = True
            self.launch_text = str(params["text"])
            return self._reply(result={"type": "ok"})
        assert method == "pane.process_info"
        name = "claude" if self.sent else "bash"
        pid = 7002 if self.sent else 7001
        cwd = self.repo if self.sent else "/before"
        return self._reply(
            result={
                "type": "pane_process_info",
                "process_info": {
                    "pane_id": self.pane_id,
                    "shell_pid": 7001,
                    "foreground_process_group_id": pid,
                    "foreground_processes": [
                        {"pid": pid, "name": name, "cmdline": name, "cwd": cwd}
                    ],
                },
            }
        )


def test_native_launch_changes_to_the_requested_repo_without_losing_env_delta(
    *, tmp_path: Path
) -> None:
    repo = tmp_path / "repo with spaces"
    repo.mkdir()
    coordinate = _coordinate(pane_id="w2:p9")
    world = CoherentLaunchWorld(pane_id="w2:p9", repo=str(repo))
    starter = herdr_initial_start.HerdrInitialStart(
        writer=world,
        journal=bootstrap_journal.BootstrapMutationJournal(root=tmp_path / "journal"),
        shell_evidence_of=lambda *, pid: herdr_initial_start.ShellIdentity(
            pid=pid, executable="/bin/bash", starttime="12345"
        ),
        login_shells=frozenset({"/bin/bash"}),
        shell_aliases=frozenset(),
    )

    result = starter.launch_initial_agent(
        session=coordinate,
        cwd=str(repo),
        command="claude --dangerously-skip-permissions -n topic",
        env={"UNSET_ME": None, "SET_ME": "two words"},
        expected_process="claude",
    )

    expected_env = "env -u UNSET_ME 'SET_ME=two words'"
    assert result.ok is True
    assert world.launch_text == (
        f"cd -- {shlex.quote(str(repo))} && {expected_env} "
        "claude --dangerously-skip-permissions -n topic"
    )
