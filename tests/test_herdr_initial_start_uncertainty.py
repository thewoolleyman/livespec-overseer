"""Durable public-start interlocks for uncertain native effects."""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bootstrap_journal
import herdr_adapter
import herdr_calls
import herdr_identity
import herdr_transport
import pane_router
import registry
import supervisor
from test_supervisor_builders import isolate_store, make_plan

__all__: list[str] = []

MODULE_PATH = Path(__file__).parents[1] / "overseer" / "herdr_initial_start.py"


def _coordinate(*, pane_id: str) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/run/user/1000/herdr-uncertain.sock",
            server_pid=5252,
            server_starttime="876543",
            pane_id=pane_id,
        )
    )


def _pane_id(*, coordinate: str) -> str:
    target = herdr_identity.decode_herdr_target(value=coordinate)
    assert target is not None
    return target.pane_id


def _rpc(
    *, ok: bool, result: dict[str, object] | None = None, error: str = ""
) -> herdr_transport.RpcOutcome:
    return herdr_transport.RpcOutcome(
        ok=ok,
        result=result or {},
        error=error,
        peer=None,
        timed_out=not ok,
        request_sent=True,
    )


@dataclass(kw_only=True)
class NativeWorld:
    owner: str
    created: str
    failed_method: str
    ack_shape: str
    panes: dict[str, str] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def request(
        self, *, target: object, method: str, params: dict[str, object], expect: object
    ) -> herdr_transport.RpcOutcome:
        del target, expect
        self.calls.append((method, params))
        handlers = {
            "pane.list": self._list,
            "workspace.create": self._create,
            "pane.process_info": self._process,
            "pane.send_input": self._send,
            "pane.close": self._close,
        }
        return handlers[method](params=params)

    def _list(self, *, params: dict[str, object]) -> herdr_transport.RpcOutcome:
        del params
        rows = [{"pane_id": pane} for pane in self.panes]
        return _rpc(ok=True, result={"type": "pane_list", "panes": rows})

    def _create(self, *, params: dict[str, object]) -> herdr_transport.RpcOutcome:
        del params
        pane_id = _pane_id(coordinate=self.created)
        self.panes[pane_id] = "bash"
        if self.failed_method == "workspace.create":
            return _rpc(ok=False, error=f"{self.ack_shape} workspace.create acknowledgement")
        return _rpc(
            ok=True,
            result={"type": "workspace_created", "root_pane": {"pane_id": pane_id}},
        )

    def _process(self, *, params: dict[str, object]) -> herdr_transport.RpcOutcome:
        pane_id = str(params["pane_id"])
        leader = {"pid": 7001, "name": "bash", "cmdline": "bash", "cwd": "/r"}
        info = {
            "pane_id": pane_id,
            "shell_pid": 7001,
            "foreground_process_group_id": 7001,
            "foreground_processes": [leader],
        }
        return _rpc(
            ok=True,
            result={"type": "pane_process_info", "process_info": info},
        )

    def _send(self, *, params: dict[str, object]) -> herdr_transport.RpcOutcome:
        self.panes[str(params["pane_id"])] = "claude"
        if self.failed_method == "pane.send_input":
            return _rpc(ok=False, error=f"{self.ack_shape} pane.send_input acknowledgement")
        return _rpc(ok=True, result={"type": "ok"})

    def _close(self, *, params: dict[str, object]) -> herdr_transport.RpcOutcome:
        self.panes.pop(str(params["pane_id"]), None)
        return _rpc(ok=True, result={"type": "ok"})

    def list_panes(self, *, target: object) -> herdr_adapter.PaneListing:
        del target
        rows = tuple(
            herdr_calls.PaneRow(
                pane_id=pane,
                tab_id="w2:t1",
                workspace_id="w2",
                cwd="/r",
                foreground_cwd="/r",
                focused=False,
            )
            for pane in self.panes
        )
        return herdr_adapter.PaneListing(ok=True, panes=rows, error="")


@dataclass(frozen=True, kw_only=True)
class Case:
    argv: list[str]
    repo: Path
    created: str
    pane_id: str
    failed_method: str
    world: NativeWorld
    capsys: Any


@dataclass(frozen=True, kw_only=True)
class ExerciseContext:
    native_module: Any
    tmp_path: Path
    monkeypatch: Any
    capsys: Any
    owner: str


def _assert_first(*, case: Case) -> None:
    assert supervisor.main(argv=case.argv) == 1
    first_error = case.capsys.readouterr().err
    assert "effect is unknown" in first_error
    assert case.created in first_error
    rows = registry.read_valid_mapping(store_path=None)
    assert any(row.repo == str(case.repo) and row.tmux == case.created for row in rows)
    assert sum(method == case.failed_method for method, _params in case.world.calls) == 1
    assert case.world.panes[case.pane_id] in {"bash", "claude"}
    assert "w2:p8" in case.world.panes


def _assert_repeat(*, case: Case) -> None:
    assert supervisor.main(argv=case.argv) == 1
    repeat_error = case.capsys.readouterr().err
    assert "fresh exact-instance, pane and process evidence" in repeat_error
    assert case.created in repeat_error
    assert sum(method == case.failed_method for method, _params in case.world.calls) == 1
    assert not any(method == "pane.close" for method, _params in case.world.calls)
    assert case.world.panes[case.pane_id] in {"bash", "claude"}
    assert "w2:p8" in case.world.panes


def _exercise_phase(
    *,
    context: ExerciseContext,
    ack_shape: str,
    phase: str,
    failed_method: str,
    pane_id: str,
) -> None:
    topic = f"{phase}-{ack_shape}"
    repo, _ = make_plan(
        tmp_path=context.tmp_path,
        repo_name=f"repo-{topic}",
        topic=topic,
    )
    created = _coordinate(pane_id=pane_id)
    assert created != context.owner
    world = NativeWorld(
        owner=context.owner,
        created=created,
        failed_method=failed_method,
        ack_shape=ack_shape,
        panes={_pane_id(coordinate=context.owner): "bash", "w2:p8": "claude"},
    )
    starter = context.native_module.HerdrInitialStart(
        writer=world,
        journal=bootstrap_journal.BootstrapMutationJournal(
            root=context.tmp_path / "journal" / topic
        ),
        shell_evidence_of=lambda *, pid: context.native_module.ShellIdentity(
            pid=pid, executable="/bin/bash", starttime="12345"
        ),
        login_shells=frozenset({"/bin/bash"}),
        shell_aliases=frozenset(),
    )
    driver = pane_router.MixedPaneDriver(herdr=world, herdr_writer=world)
    driver.initial_start = starter
    context.monkeypatch.setattr(pane_router, "current_process_coordinate", lambda: context.owner)
    context.monkeypatch.setattr(pane_router, "default_pane_driver", lambda driver=driver: driver)
    argv = ["start", "--repo", str(repo), "--topic", topic]
    case = Case(
        argv=argv,
        repo=repo,
        created=created,
        pane_id=pane_id,
        failed_method=failed_method,
        world=world,
        capsys=context.capsys,
    )
    _assert_first(case=case)
    _assert_repeat(case=case)
    if phase == "launch":
        sent = next(params for method, params in world.calls if method == "pane.send_input")
        assert "env -u" in str(sent["text"])
        assert "claude" in str(sent["text"])


def test_lost_or_malformed_native_acknowledgements_are_durable_no_replay_boundaries(
    *, tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    assert MODULE_PATH.is_file(), "the concrete initial-start adapter is not implemented"
    native_module = importlib.import_module("herdr_initial_start")
    _ = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    claude = tmp_path / "bin" / "claude"
    claude.parent.mkdir()
    claude.write_text("#!/bin/sh\n", encoding="utf-8")
    claude.chmod(0o755)
    monkeypatch.setenv("PATH", str(claude.parent))
    owner = _coordinate(pane_id="w2:p1")
    context = ExerciseContext(
        native_module=native_module,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        capsys=capsys,
        owner=owner,
    )

    for ack_shape in ("lost", "malformed"):
        for phase, failed_method, pane_id in (
            ("create", "workspace.create", "w2:p9"),
            ("launch", "pane.send_input", "w2:p10"),
        ):
            _exercise_phase(
                context=context,
                ack_shape=ack_shape,
                phase=phase,
                failed_method=failed_method,
                pane_id=pane_id,
            )
