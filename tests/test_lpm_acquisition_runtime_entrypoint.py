"""The installed acquire entrypoint refuses before creating acquisition state."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol, cast

import pytest

import overseer._lpm_runtime_backend as backend
from overseer._lpm_commands import run_manager_command
from overseer._lpm_config import default_config
from overseer._lpm_prereq import RuntimePrerequisites
from overseer._lpm_results import ManagerError
from overseer._lpm_role_runner import RoleCompletion, RoleLaunch
from overseer._lpm_runtime import ConcreteManagerRuntime
from overseer._lpm_runtime_backend import RolePorts
from overseer._vendor.returns.result import Result, Success

__all__: list[str] = []


class _AcquirePort(Protocol):
    def acquire(self, *, request: dict[str, object]) -> Result[dict[str, object], ManagerError]: ...


def _role_launch(*, answer_status: str, request: dict[str, object]) -> RoleLaunch:
    def launch(
        *,
        argv: tuple[str, ...],
        environ: Mapping[str, str],
        request_bytes: bytes,
        timeout_seconds: float,
        inherited_fds: tuple[int, ...],
    ) -> RoleCompletion:
        _ = (environ, timeout_seconds, inherited_fds)
        assert argv[-1] == "acquisition-prerequisite"
        assert json.loads(request_bytes) == {**request, "op_executable": "/usr/bin/op"}
        return RoleCompletion(
            stdout=json.dumps({"version": 1, "status": answer_status}).encode(),
            exit_status=0,
            timed_out=False,
        )

    return launch


def _recording_start(*, events: list[object]) -> Callable[..., None]:
    def start(**members: object) -> None:
        events.append(members)

    return start


def test_acquire_refuses_missing_or_ambiguous_prerequisites_before_state(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from overseer._lpm_manager_argv import manager_invocation

    parsed = manager_invocation(arguments=("acquire", "--acquisition-json", "-"))
    assert isinstance(parsed, Success), "the installed manager must recognize acquire"

    def resolved_prerequisites(**_kwargs: object) -> Success[RuntimePrerequisites]:
        return Success(
            RuntimePrerequisites(machine_id_sha256="a" * 64, op_executable="/usr/bin/op")
        )

    monkeypatch.setattr(
        backend,
        "runtime_prerequisites",
        resolved_prerequisites,
    )
    request: dict[str, object] = {
        "version": 1,
        "provider": "anthropic",
        "account_id": "account-1",
        "kind": "claude-code-oauth",
        "purpose": "factory",
    }

    for status in ("absent", "malformed"):
        state_dir = tmp_path / status / "state"
        started: list[object] = []

        ports = cast("Callable[..., RolePorts]", RolePorts)(
            config=default_config(),
            owner_uid=os.getuid(),
            state_dir=state_dir,
            environ={"PATH": "/usr/bin:/bin"},
            launch=_role_launch(answer_status=status, request=request),
            python_executable=sys.executable,
            packaged_companion=str(tmp_path / "_lpm_companion.py"),
            start_acquisition=_recording_start(events=started),
        )
        acquiring_ports = cast("_AcquirePort", ports)
        runtime = cast("Callable[..., ConcreteManagerRuntime]", ConcreteManagerRuntime)(
            state_dir=state_dir,
            owner_uid=os.getuid(),
            config=default_config(),
            read_input=lambda: json.dumps(request),
            acquisition=acquiring_ports.acquire,
        )

        outcome = run_manager_command(
            arguments=("acquire", "--acquisition-json", "-"), runtime=runtime
        )

        assert outcome.exit_status == 2
        assert outcome.body["error_type"] == "invalid-request"
        assert started == []
        assert not state_dir.exists()
