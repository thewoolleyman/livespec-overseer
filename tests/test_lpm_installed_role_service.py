"""Installed credential roles reach real stores and confine the provisioned value."""

from __future__ import annotations

import importlib
import io
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

import pytest

from overseer._lpm_localstate import write_local_record
from overseer._lpm_locks import release_lock, take_lock
from overseer._lpm_onepassword import (
    NAMESPACE_ITEM_TITLE,
    VALUES_VAULT,
    namespace_item_fields,
    value_ref,
    values_item_title,
)
from overseer._lpm_paths import local_record_path, manager_state_dir
from overseer._lpm_role_child import ChildProcessOS, ClosedRoleInput, LauncherRefusal
from overseer._lpm_role_runner import subprocess_role_launch
from overseer._lpm_roles import PackagedCompanion
from overseer._lpm_runtime_base import target_lock_path
from overseer._lpm_target import issuance_object, new_issuance
from overseer._vendor.returns.result import Success

__all__: list[str] = []

_RUN = "installed-role-run"
_REFERENCE = "10000000-0000-4000-8000-000000000001"
_RECORD = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"
_NOW = "2026-10-10T20:00:00Z"
_EXPIRES = "2099-10-10T21:00:00Z"
_SECRET = "credential-visible-only-inside-final-role"
_MACHINE = "d" * 64


class _OpFixture(Protocol):
    executable: str

    def seed(
        self,
        *,
        items: list[dict[str, object]],
        refuse: tuple[str, ...] = (),
        garble: tuple[str, ...] = (),
    ) -> None: ...

    def calls(self) -> list[dict[str, object]]: ...


def _namespace(*, vault: str, fields: dict[str, str]) -> dict[str, object]:
    return {
        "id": f"namespace-{vault}",
        "title": NAMESPACE_ITEM_TITLE,
        "vault": vault,
        "fields": fields,
    }


def _seed_backend(*, op_fixture: _OpFixture, fields: dict[str, str]) -> None:
    op_fixture.seed(
        items=[
            _namespace(vault=VALUES_VAULT, fields=fields),
            {
                "id": "credential-generation-1",
                "title": values_item_title(record_id=_RECORD, value_generation=_GENERATION),
                "vault": VALUES_VAULT,
                "fields": {"credential": _SECRET},
            },
        ]
    )


def _write_issuance(*, state_dir: Path, destination: Path) -> None:
    issuance = new_issuance(
        reference=_REFERENCE,
        consumer_run_id=_RUN,
        adapter="isolated-run",
        destination=str(destination),
        now=_NOW,
    ).unwrap()
    path = local_record_path(
        state_dir=state_dir, family="issuance", identity=(_REFERENCE,)
    ).unwrap()
    write_local_record(
        path=path, value=issuance_object(issuance=issuance), owner_uid=os.getuid()
    ).unwrap()


def _final_request(*, op_executable: str) -> dict[str, object]:
    return {
        "version": 1,
        "target_ref": _REFERENCE,
        "consumer_run_id": _RUN,
        "record_id": _RECORD,
        "value_generation": _GENERATION,
        "value_ref": value_ref(record_id=_RECORD, value_generation=_GENERATION),
        "lease_expires_at": _EXPIRES,
        "external_call_timeout_seconds": 30,
        "op_executable": op_executable,
    }


def _run_clean_status_child(*, root: Path) -> None:
    request = json.dumps(
        {
            "version": 1,
            "target_ref": _REFERENCE,
            "consumer_run_id": _RUN,
            "value_generation": _GENERATION,
        },
        separators=(",", ":"),
    )
    completed = subprocess_role_launch(
        argv=(
            sys.executable,
            "-I",
            "-S",
            str(root / "overseer" / "_lpm_companion.py"),
            "--credential-role",
            "target-status",
        ),
        environ={"PATH": os.environ.get("PATH", "")},
        request_bytes=request.encode("utf-8"),
        timeout_seconds=10.0,
        inherited_fds=(),
    )
    assert completed.exit_status == 0
    assert not completed.timed_out
    assert completed.stdout == b'{"status":"store-unavailable","version":1}\n'


def _exercise_companion_dispatch(
    *,
    root: Path,
    request: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    companion_module = importlib.import_module("_lpm_companion")
    role_child = importlib.import_module("_lpm_role_child")

    def refuse_launch(
        *,
        role_input: ClosedRoleInput,
        companion: PackagedCompanion,
        environ: Mapping[str, str],
        process_os: ChildProcessOS,
    ) -> LauncherRefusal:
        _ = (role_input, companion, environ, process_os)
        return LauncherRefusal(
            failure_object={"version": 1, "status": "store-unavailable"},
            reason="injected pre-exec refusal",
        )

    monkeypatch.delenv("LIVESPEC_LPM_EXECUTED_ROLE", raising=False)
    monkeypatch.setattr(role_child, "launch_credential_role", refuse_launch)
    monkeypatch.setattr(sys, "stdin", io.StringIO(request))
    assert (
        companion_module.run(
            arguments=("--credential-role", "target-status"), root=root / "overseer"
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "store-unavailable"

    monkeypatch.setenv("LIVESPEC_LPM_EXECUTED_ROLE", "target-status")
    monkeypatch.setattr(sys, "stdin", io.StringIO(request))
    assert (
        companion_module.run(
            arguments=("--credential-role", "target-status"), root=root / "overseer"
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "store-unavailable"


def test_installed_roles_execute_real_store_and_target_boundaries(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    op_fixture: _OpFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    service = importlib.import_module("_lpm_role_service")
    assert hasattr(service, "role_result"), "the installed companion must dispatch role work"
    context = importlib.import_module("_lpm_role_context")

    def account_home(*, uid: int) -> Path:
        _ = uid
        return tmp_path

    def machine_digest(*, path: Path) -> Success[str]:
        _ = path
        return Success(_MACHINE)

    monkeypatch.setattr(context, "account_database_home", account_home)
    monkeypatch.setattr(context, "machine_id_defect", machine_digest)

    state_dir = manager_state_dir(home=tmp_path)
    destination = state_dir / "targets" / "installed" / "credential"
    _write_issuance(state_dir=state_dir, destination=destination)
    fields = namespace_item_fields(
        machine_id_sha256=_MACHINE,
        effective_uid=os.getuid(),
        manager_state=str(state_dir),
    )
    _seed_backend(op_fixture=op_fixture, fields=fields)
    value_reader = {"PATH": "/usr/bin:/bin", "LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN": "v"}

    held = take_lock(
        path=target_lock_path(state_dir=state_dir, target_ref=_REFERENCE),
        owner_uid=os.getuid(),
        timeout_seconds=1.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    ).unwrap()
    try:
        committed = service.role_result(
            role_name="final-provisioning",
            request=_final_request(op_executable=op_fixture.executable),
            environ=value_reader,
            lock_descriptor=held.descriptor,
        )
        status = service.role_result(
            role_name="target-status",
            request={
                "version": 1,
                "target_ref": _REFERENCE,
                "consumer_run_id": _RUN,
                "value_generation": _GENERATION,
            },
            environ={"PATH": "/usr/bin:/bin"},
            lock_descriptor=held.descriptor,
        )
    finally:
        release_lock(held=held)

    assert committed["status"] == status["status"] == "committed"
    assert committed["committed_at"] == status["committed_at"]
    assert destination.read_text(encoding="utf-8") == _SECRET
    assert _SECRET not in json.dumps((committed, status, op_fixture.calls()))
    root = Path(__file__).parents[1]
    status_request = json.dumps(
        {
            "version": 1,
            "target_ref": _REFERENCE,
            "consumer_run_id": _RUN,
            "value_generation": _GENERATION,
        },
        separators=(",", ":"),
    )
    _exercise_companion_dispatch(
        root=root, request=status_request, monkeypatch=monkeypatch, capsys=capsys
    )
    _run_clean_status_child(root=root)
