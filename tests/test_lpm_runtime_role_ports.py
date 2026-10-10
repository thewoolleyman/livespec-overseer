"""Installed runtime ports launch closed credential roles and preserve ambiguity."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import overseer._lpm_runtime_backend as backend
from overseer._lpm_config import default_config
from overseer._lpm_prereq import RuntimePrerequisites
from overseer._lpm_role_runner import RoleCompletion
from overseer._lpm_runtime_backend import RolePorts
from overseer._lpm_runtime_roles import FinalProvisioningRequest, TargetStatusRequest
from overseer._lpm_store import ConditionalSet
from overseer._lpm_target import COMMITTED, TargetLock
from overseer._vendor.returns.result import Success

__all__: list[str] = []

_COMMITTED_AT = "2026-10-10T20:30:00Z"


@dataclass(kw_only=True)
class _RoleScript:
    final_answers: list[bytes] = field(
        default_factory=lambda: [
            (b'{"version":1,"status":"committed",' b'"committed_at":"2026-10-10T20:30:00Z"}'),
            (b'{"version":1,"status":"committed",' b'"committed_at":"2026-10-10T20:30:00Z"}'),
        ]
    )
    calls: list[tuple[str, dict[str, object], tuple[int, ...]]] = field(default_factory=list)

    def __call__(
        self,
        *,
        argv: tuple[str, ...],
        environ: Mapping[str, str],
        request_bytes: bytes,
        timeout_seconds: float,
        inherited_fds: tuple[int, ...],
    ) -> RoleCompletion:
        _ = (environ, timeout_seconds)
        role = argv[-1]
        request = json.loads(request_bytes)
        self.calls.append((role, request, inherited_fds))
        if role == "metadata-reader":
            stdout = (
                b'{"version":1,"status":"ok","item":null}'
                if request["mode"] == "get"
                else b'{"version":1,"status":"ok","items":[],"invalid":[]}'
            )
        elif role == "report-writer":
            stdout = b'{"version":1,"status":"committed"}'
        else:
            stdout = self.final_answers.pop(0)
        return RoleCompletion(stdout=stdout, exit_status=0, timed_out=False)


def _ports(*, tmp_path: Path, script: _RoleScript, monkeypatch: pytest.MonkeyPatch) -> RolePorts:
    assert hasattr(
        backend, "runtime_prerequisites"
    ), "production role ports must resolve prerequisites"
    monkeypatch.setattr(
        backend,
        "runtime_prerequisites",
        lambda **_kwargs: Success(
            RuntimePrerequisites(machine_id_sha256="a" * 64, op_executable="/usr/bin/op")
        ),
    )
    return RolePorts(
        config=default_config(),
        owner_uid=os.getuid(),
        state_dir=tmp_path / "state",
        environ={"PATH": "/usr/bin:/bin", "FORBIDDEN_SECRET": "must-not-cross"},
        launch=script,
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


def _exercise_store(*, ports: RolePorts) -> None:
    assert ports.metadata_get(record_id="record-a") == {
        "version": 1,
        "status": "ok",
        "item": None,
    }
    assert ports.metadata_list() == {
        "version": 1,
        "status": "ok",
        "items": [],
        "invalid": [],
    }
    assert ports.credential_conditional_set(
        request=ConditionalSet(
            record_id="record-a",
            effect_id="effect-a",
            expected_record=None,
            desired_record='{"version":1}',
        )
    ) == {"version": 1, "status": "committed"}


def _assert_ambiguous_mapping(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ambiguous = _ports(
        tmp_path=tmp_path / "ambiguous",
        script=_RoleScript(final_answers=[b"not-json"]),
        monkeypatch=monkeypatch,
    )
    result = ambiguous(
        request=_final_request(),
        destination=str(tmp_path / "ignored"),
        lock=_lock(tmp_path=tmp_path / "ambiguous"),
    )
    assert result.failure().error_type == "retryable-exhaustion"

    unavailable = _ports(
        tmp_path=tmp_path / "unavailable",
        script=_RoleScript(final_answers=[b'{"version":1,"status":"store-unavailable"}']),
        monkeypatch=monkeypatch,
    )
    result = unavailable(
        request=_final_request(),
        destination=str(tmp_path / "ignored"),
        lock=_lock(tmp_path=tmp_path / "unavailable"),
    )
    assert result.failure().error_type == "store-unavailable"


def test_runtime_role_ports_launch_secret_free_store_and_target_operations(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _RoleScript()
    ports = _ports(tmp_path=tmp_path, script=script, monkeypatch=monkeypatch)
    _exercise_store(ports=ports)

    committed = ports(
        request=_final_request(),
        destination=str(tmp_path / "ignored"),
        lock=_lock(tmp_path=tmp_path),
    ).unwrap()
    status = ports.target_status(
        request=TargetStatusRequest(
            target_ref="target-a",
            consumer_run_id="run-a",
            value_generation="6ba7b810-9dad-41d1-80b4-00c04fd430c8",
        ),
        destination=str(tmp_path / "ignored"),
        lock=_lock(tmp_path=tmp_path),
    ).unwrap()

    assert committed.status == status.status == COMMITTED
    assert committed.committed_at == status.committed_at == _COMMITTED_AT
    assert [call[0] for call in script.calls] == [
        "metadata-reader",
        "metadata-reader",
        "report-writer",
        "final-provisioning",
        "target-status",
    ]
    assert all("must-not-cross" not in json.dumps(call) for call in script.calls)
    assert script.calls[-1][1] == {
        "version": 1,
        "target_ref": "target-a",
        "consumer_run_id": "run-a",
        "value_generation": "6ba7b810-9dad-41d1-80b4-00c04fd430c8",
    }
    assert script.calls[-1][2]
    _assert_ambiguous_mapping(tmp_path=tmp_path, monkeypatch=monkeypatch)
