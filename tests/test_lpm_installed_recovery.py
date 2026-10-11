"""Installed subprocess retries settle durable LPM interruption evidence."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Protocol

__all__: list[str] = []

_ROOT = Path(__file__).resolve().parents[1]
_SUPPORT = _ROOT / "overseer" / "test_lpm_installed_sandbox.py"
_SECRET = b"sk-ant-oat01-installed-recovery"


class _Result(Protocol):
    exit_status: int
    body: dict[str, object]


class _Credential(Protocol):
    record_id: str
    account_id: str


class _ReportSnapshot(Protocol):
    status: str
    lease_exists: bool
    assignment_exists: bool
    tombstone_exists: bool


class _Sandbox(Protocol):
    def register_target(self, *, consumer_run_id: str) -> Path: ...

    def run(self, *, surface: str, arguments: tuple[str, ...], input_text: str = "") -> _Result: ...

    def bind_target_lock(self, *, target_ref: str) -> None: ...

    def seed_credential(self, *, value: bytes) -> _Credential: ...

    def interrupt_provision_after_target_commit(self, *, consumer_run_id: str) -> None: ...

    def interrupt_next_metadata_create(self) -> None: ...

    def target_committed_at(self, *, consumer_run_id: str) -> str: ...

    def report_snapshot(
        self, *, consumer_run_id: str, record_id: str, account_id: str
    ) -> _ReportSnapshot: ...

    def write_registered_target(self, *, destination: Path, value: bytes) -> None: ...


def _support() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lpm_installed_recovery_sandbox", _SUPPORT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _request(*, run_id: str, target_ref: str) -> dict[str, object]:
    return {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "consumer_run_id": run_id,
        "target_ref": target_ref,
        "strategy": "consume-first",
        "lease_seconds": 3600,
    }


def _issued(*, sandbox: _Sandbox, run_id: str) -> tuple[Path, str, dict[str, object]]:
    destination = sandbox.register_target(consumer_run_id=run_id)
    target = sandbox.run(
        surface="console",
        arguments=("target", "--target-json", "-"),
        input_text=json.dumps({"version": 1, "consumer_run_id": run_id, "adapter": "isolated-run"}),
    )
    assert target.exit_status == 0
    target_ref = target.body["target_ref"]
    assert isinstance(target_ref, str)
    sandbox.bind_target_lock(target_ref=target_ref)
    return destination, target_ref, _request(run_id=run_id, target_ref=target_ref)


def _prove_provision_recovery(*, sandbox: _Sandbox) -> tuple[_Credential, str]:
    credential = sandbox.seed_credential(value=_SECRET)
    run_id = "installed-recovery-run"
    destination, _, request = _issued(sandbox=sandbox, run_id=run_id)
    first = sandbox.run(
        surface="console",
        arguments=("provision", "--request-json", "-"),
        input_text=json.dumps(request),
    )
    assert first.exit_status == 0
    target_identity = (destination.stat().st_ino, destination.stat().st_mtime_ns)
    sandbox.interrupt_provision_after_target_commit(consumer_run_id=run_id)
    recovered = sandbox.run(
        surface="plugin",
        arguments=("provision", "--request-json", "-"),
        input_text=json.dumps(request),
    )
    assert recovered.exit_status == 0
    assert recovered.body["operation"] == "provision"
    assert destination.read_bytes() == _SECRET
    assert (destination.stat().st_ino, destination.stat().st_mtime_ns) == target_identity
    return credential, run_id


def _prove_report_recovery(*, sandbox: _Sandbox, credential: _Credential, run_id: str) -> None:
    report_object = {
        "version": 1,
        "consumer_run_id": run_id,
        "record_id": credential.record_id,
        "occurred_at": sandbox.target_committed_at(consumer_run_id=run_id),
        "classification": "authentication",
    }
    sandbox.interrupt_next_metadata_create()
    interrupted = sandbox.run(
        surface="plugin",
        arguments=("report", "--report-json", "-"),
        input_text=json.dumps(report_object),
    )
    partial = sandbox.report_snapshot(
        consumer_run_id=run_id,
        record_id=credential.record_id,
        account_id=credential.account_id,
    )
    retried = sandbox.run(
        surface="plugin",
        arguments=("report", "--report-json", "-"),
        input_text=json.dumps(report_object),
    )
    duplicate = sandbox.run(
        surface="plugin",
        arguments=("report", "--report-json", "-"),
        input_text=json.dumps(report_object),
    )
    completed = sandbox.report_snapshot(
        consumer_run_id=run_id,
        record_id=credential.record_id,
        account_id=credential.account_id,
    )
    assert interrupted.exit_status == 4
    assert interrupted.body["error_type"] == "store-unavailable"
    assert (partial.status, partial.lease_exists) == ("suspect", True)
    assert (partial.assignment_exists, partial.tombstone_exists) == (True, False)
    assert retried.exit_status == 0
    assert retried.body["duplicate"] is False
    assert (completed.lease_exists, completed.assignment_exists) == (False, False)
    assert completed.tombstone_exists is True
    assert duplicate.exit_status == 0
    assert duplicate.body["duplicate"] is True


def _prove_failed_write(*, support: ModuleType, root: Path) -> None:
    sandbox = support.InstalledManagerSandbox.create(root=root, repository=_ROOT)
    _ = sandbox.seed_credential(value=b"sk-ant-oat01-never-written")
    destination, _, request = _issued(sandbox=sandbox, run_id="installed-failed-write-run")
    prior = b"byte-identical-existing-target"
    sandbox.write_registered_target(destination=destination, value=prior)
    destination.parent.chmod(0o500)
    try:
        refused = sandbox.run(
            surface="console",
            arguments=("provision", "--request-json", "-"),
            input_text=json.dumps(request),
        )
    finally:
        destination.parent.chmod(0o700)
    assert refused.exit_status == 5
    assert refused.body["error_type"] == "provisioning-failed"
    assert destination.read_bytes() == prior


def test_installed_retries_recover_interruptions_and_failed_write_preserves_target(
    tmp_path: Path,
) -> None:
    support = _support()
    sandbox = support.InstalledManagerSandbox.create(root=tmp_path, repository=_ROOT)
    assert hasattr(
        sandbox, "interrupt_provision_after_target_commit"
    ), "the installed sandbox must expose a durable target-commit interruption"
    credential, run_id = _prove_provision_recovery(sandbox=sandbox)
    _prove_report_recovery(sandbox=sandbox, credential=credential, run_id=run_id)
    _prove_failed_write(support=support, root=tmp_path / "failed-write")
