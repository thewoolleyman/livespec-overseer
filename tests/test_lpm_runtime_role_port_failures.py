"""Production role ports retain typed pre-write and ambiguous failure distinctions."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest
from returns.primitives.exceptions import UnwrapFailedError

import overseer._lpm_runtime_backend as backend
from overseer._lpm_config import default_config
from overseer._lpm_prereq import RuntimePrerequisites
from overseer._lpm_results import ManagerError, store_unavailable
from overseer._lpm_role_runner import RoleCompletion
from overseer._lpm_runtime_backend import RolePorts
from overseer._lpm_runtime_roles import FinalProvisioningRequest, TargetStatusRequest
from overseer._lpm_target import CommitOutcome, TargetLock
from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = []


@dataclass(frozen=True, kw_only=True)
class _Completion:
    stdout: bytes
    started: bool = True

    def __call__(
        self,
        *,
        argv: tuple[str, ...],
        environ: Mapping[str, str],
        request_bytes: bytes,
        timeout_seconds: float,
        inherited_fds: tuple[int, ...],
    ) -> RoleCompletion:
        _ = (argv, environ, request_bytes, timeout_seconds, inherited_fds)
        return RoleCompletion(
            stdout=self.stdout,
            exit_status=0,
            timed_out=False,
            started=self.started,
        )


def _prerequisites_ok(
    *, root: Path, search_path: Sequence[Path], executable_name: str
) -> Result[RuntimePrerequisites, ManagerError]:
    _ = (root, search_path, executable_name)
    return Success(RuntimePrerequisites(machine_id_sha256="a" * 64, op_executable="/usr/bin/op"))


def _prerequisites_failed(
    *, root: Path, search_path: Sequence[Path], executable_name: str
) -> Result[RuntimePrerequisites, ManagerError]:
    _ = (root, search_path, executable_name)
    return Failure(store_unavailable(message="op is unavailable"))


def _ports(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, launch: _Completion) -> RolePorts:
    monkeypatch.setattr(
        backend,
        "runtime_prerequisites",
        _prerequisites_ok,
    )
    return RolePorts(
        config=default_config(),
        owner_uid=os.getuid(),
        state_dir=tmp_path / "state",
        environ={"PATH": "/usr/bin:/bin"},
        launch=launch,
        python_executable=sys.executable,
        packaged_companion=str(tmp_path / "_lpm_companion.py"),
    )


def _lock(*, tmp_path: Path) -> TargetLock:
    return TargetLock(
        path=tmp_path / "state" / "locks" / "target.lock",
        timeout_seconds=1.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )


def _final_request() -> FinalProvisioningRequest:
    return FinalProvisioningRequest(
        target_ref="target-a",
        consumer_run_id="run-a",
        record_id="3f2504e0-4f89-41d3-9a0c-0305e82c3301",
        value_generation="6ba7b810-9dad-41d1-80b4-00c04fd430c8",
        value_ref=(
            "op://llm-provider-manager-token-values/"
            "3f2504e0-4f89-41d3-9a0c-0305e82c3301-"
            "6ba7b810-9dad-41d1-80b4-00c04fd430c8/credential"
        ),
        lease_expires_at="2026-10-10T21:00:00Z",
        external_call_timeout_seconds=30,
        op_executable="",
    )


def _status_request() -> TargetStatusRequest:
    return TargetStatusRequest(
        target_ref="target-a",
        consumer_run_id="run-a",
        value_generation="6ba7b810-9dad-41d1-80b4-00c04fd430c8",
    )


def _error_type(*, invoke: Callable[[], Result[CommitOutcome, ManagerError]]) -> str:
    try:
        result = invoke()
    except UnwrapFailedError:
        return "raised"
    if isinstance(result, Failure):
        return result.failure().error_type
    return "success"


def _metadata_answer(*, ports: RolePorts) -> dict[str, object]:
    try:
        return ports.metadata_list()
    except UnwrapFailedError:
        return {"raised": True}


def test_role_ports_distinguish_prewrite_refusal_from_ambiguous_target_outcomes(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    committed = b'{"version":1,"status":"committed","committed_at":"2026-10-10T20:30:00Z"}'
    ports = _ports(
        tmp_path=tmp_path / "prerequisite",
        monkeypatch=monkeypatch,
        launch=_Completion(stdout=committed),
    )
    monkeypatch.setattr(
        backend,
        "runtime_prerequisites",
        _prerequisites_failed,
    )
    assert _metadata_answer(ports=ports) == {"version": 1, "status": "unavailable"}

    ports = _ports(
        tmp_path=tmp_path / "lock",
        monkeypatch=monkeypatch,
        launch=_Completion(stdout=committed),
    )
    unavailable_lock = _lock(tmp_path=tmp_path / "lock")
    unavailable_lock.path.parent.mkdir(parents=True)
    unavailable_lock.path.symlink_to("missing-lock-target")
    lock_failures = (
        _error_type(
            invoke=lambda: ports(
                request=_final_request(),
                destination=str(tmp_path / "ignored"),
                lock=unavailable_lock,
            )
        ),
        _error_type(
            invoke=lambda: ports.target_status(
                request=_status_request(),
                destination=str(tmp_path / "ignored"),
                lock=unavailable_lock,
            )
        ),
    )
    assert lock_failures == ("store-unavailable", "store-unavailable")

    answers = (
        _Completion(stdout=b"", started=False),
        _Completion(stdout=b"not-json"),
        _Completion(stdout=b'{"version":1,"status":"store-unavailable"}'),
        _Completion(stdout=b'{"version":1,"status":"in-progress","committed_at":null}'),
    )
    meanings: list[str] = []
    for index, answer in enumerate(answers):
        port = _ports(
            tmp_path=tmp_path / f"answer-{index}",
            monkeypatch=monkeypatch,
            launch=answer,
        )
        meanings.append(
            _error_type(
                invoke=lambda port=port, index=index: port(
                    request=_final_request(),
                    destination=str(tmp_path / "ignored"),
                    lock=_lock(tmp_path=tmp_path / f"answer-{index}"),
                )
            )
        )
    assert tuple(meanings) == (
        "store-unavailable",
        "retryable-exhaustion",
        "store-unavailable",
        "retryable-exhaustion",
    )


def test_target_status_refusals_retain_ambiguous_recovery_state(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = (
        _Completion(stdout=b"", started=False),
        _Completion(stdout=b'{"version":1,"status":"store-unavailable"}'),
    )
    cleanup_safety: list[bool] = []
    for index, answer in enumerate(answers):
        port = _ports(
            tmp_path=tmp_path / f"status-{index}",
            monkeypatch=monkeypatch,
            launch=answer,
        )
        result = port.target_status(
            request=_status_request(),
            destination=str(tmp_path / "ignored"),
            lock=_lock(tmp_path=tmp_path / f"status-{index}"),
        )
        assert isinstance(result, Failure)
        cleanup_safety.append(result.failure().cleanup_safe)

    assert tuple(cleanup_safety) == (False, False)
