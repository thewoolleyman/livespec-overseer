"""Provision composition selects metadata and recovers durable target effects."""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Protocol, cast

import pytest

from overseer._lpm_canonical import canonical_json_text
from overseer._lpm_config import ManagerConfig, default_config
from overseer._lpm_engine_context import EffectInputs
from overseer._lpm_onepassword import value_ref
from overseer._lpm_operation import OperationRecord
from overseer._lpm_provision_request import ProvisionRequest
from overseer._lpm_reports import FailureReport
from overseer._lpm_results import ManagerError, internal_bug, store_unavailable
from overseer._lpm_runtime_roles import FinalProvisioningRequest
from overseer._lpm_store import ConditionalSet, InMemorySecretStore, SecretStore
from overseer._lpm_target import COMMITTED, IN_PROGRESS, UNCOMMITTED, CommitOutcome, TargetLock
from overseer._lpm_target_evidence import (
    TargetEvidenceBinding,
    commit_with_evidence,
    target_status_with_evidence,
)
from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = []

_NOW = "2026-10-10T12:00:00Z"
_SECRET = b"credential-value-never-owned-by-the-selection-brain"
_RECORD = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"
_OPERATION_IDS = (
    "10000000-0000-4000-8000-000000000001",
    "20000000-0000-4000-8000-000000000002",
    "30000000-0000-4000-8000-000000000003",
    "40000000-0000-4000-8000-000000000004",
)


class _StatusRequest(Protocol):
    @property
    def target_ref(self) -> str: ...

    @property
    def consumer_run_id(self) -> str: ...

    @property
    def value_generation(self) -> str: ...


@dataclass(kw_only=True)
class _ProvisionTarget:
    owner_uid: int
    statuses: list[str] = field(default_factory=lambda: [COMMITTED])
    calls: list[str] = field(default_factory=list)

    def __call__(
        self,
        *,
        request: FinalProvisioningRequest,
        destination: str,
        lock: TargetLock,
    ) -> Result[CommitOutcome, ManagerError]:
        from overseer._lpm_target import commit_credential

        self.calls.append(request.target_ref)
        status = self.statuses.pop(0) if self.statuses else COMMITTED
        if status != COMMITTED:
            return Success(CommitOutcome(status=status, committed_at=None))
        return Success(
            commit_credential(
                destination=destination,
                value=_SECRET,
                owner_uid=self.owner_uid,
                fence_now=_NOW,
                lease_expires_at=request.lease_expires_at,
                lock=lock,
            )
        )


@dataclass(kw_only=True)
class _TargetStatus:
    statuses: list[str]
    calls: list[str] = field(default_factory=list)

    def __call__(
        self,
        *,
        request: _StatusRequest,
        destination: str,
        lock: TargetLock,
    ) -> Result[CommitOutcome, ManagerError]:
        del destination, lock
        self.calls.append(request.target_ref)
        status = self.statuses.pop(0)
        return Success(
            CommitOutcome(
                status=status,
                committed_at=_NOW if status == COMMITTED else None,
            )
        )


@dataclass(kw_only=True)
class _EvidenceTarget:
    state_dir: Path
    owner_uid: int
    writes: int = 0
    status_calls: int = 0

    def __call__(
        self,
        *,
        request: FinalProvisioningRequest,
        destination: str,
        lock: TargetLock,
    ) -> Result[CommitOutcome, ManagerError]:
        _ = lock
        self.writes += 1
        return Success(
            commit_with_evidence(
                binding=self._binding(request=request, destination=destination),
                value=_SECRET,
                lease_expires_at=request.lease_expires_at,
                sample_time=lambda: _NOW,
            )
        )

    def status(
        self,
        *,
        request: _StatusRequest,
        destination: str,
        lock: TargetLock,
    ) -> Result[CommitOutcome, ManagerError]:
        _ = lock
        self.status_calls += 1
        return target_status_with_evidence(
            binding=TargetEvidenceBinding(
                state_dir=self.state_dir,
                destination=destination,
                owner_uid=self.owner_uid,
                target_ref=request.target_ref,
                consumer_run_id=request.consumer_run_id,
                value_generation=request.value_generation,
            )
        )

    def _binding(
        self, *, request: FinalProvisioningRequest, destination: str
    ) -> TargetEvidenceBinding:
        return TargetEvidenceBinding(
            state_dir=self.state_dir,
            destination=destination,
            owner_uid=self.owner_uid,
            target_ref=request.target_ref,
            consumer_run_id=request.consumer_run_id,
            value_generation=request.value_generation,
        )


@dataclass(frozen=True, kw_only=True)
class _Host:
    state_dir: Path
    owner_uid: int
    config: ManagerConfig
    store: SecretStore
    provision_target: _ProvisionTarget
    target_status: _TargetStatus | None
    op_executable: str
    capture_time: Callable[[], str]
    new_operation_id: Callable[[], str]
    monotonic: Callable[[], float]
    sleep: Callable[[float], None]


def _seed_store() -> InMemorySecretStore:
    store = InMemorySecretStore()
    record = _record_object()
    desired = canonical_json_text(value=record).unwrap()
    outcome = store.credential_conditional_set(
        request=ConditionalSet(
            record_id=_RECORD,
            effect_id="a" * 64,
            expected_record=None,
            desired_record=desired,
        )
    )
    assert outcome["status"] == COMMITTED
    return store


def _record_object() -> dict[str, object]:
    return {
        "version": 1,
        "record_id": _RECORD,
        "provider": "anthropic",
        "account_id": "account-a",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": _NOW,
        "expires_at": None,
        "last_validated": _NOW,
        "value_generation": _GENERATION,
        "value_ref": value_ref(record_id=_RECORD, value_generation=_GENERATION),
        "previous_value_ref": None,
    }


def _host(
    *, state_dir: Path, target: _ProvisionTarget, target_status: _TargetStatus | None = None
) -> _Host:
    identifiers = iter(_OPERATION_IDS)
    return _Host(
        state_dir=state_dir,
        owner_uid=os.getuid(),
        config=default_config(),
        store=_seed_store(),
        provision_target=target,
        target_status=target_status,
        op_executable="/usr/bin/op",
        capture_time=lambda: _NOW,
        new_operation_id=lambda: next(identifiers),
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )


def _issue(*, host: _Host, run_id: str) -> str:
    from overseer._lpm_runtime_target import run_target

    issued = run_target(
        host=host,
        normalized_input={
            "version": 1,
            "consumer_run_id": run_id,
            "adapter": "isolated-run",
        },
    ).unwrap()
    return str(issued["target_ref"])


def _request(*, run_id: str, target_ref: str) -> ProvisionRequest:
    return ProvisionRequest(
        provider="anthropic",
        kind="claude-code-oauth",
        purpose="factory",
        consumer_run_id=run_id,
        target_ref=target_ref,
        strategy="consume-first",
        lease_seconds=3600,
    )


def _normalized(*, request: ProvisionRequest) -> dict[str, object]:
    return {
        "version": 1,
        "provider": request.provider,
        "kind": request.kind,
        "purpose": request.purpose,
        "consumer_run_id": request.consumer_run_id,
        "target_ref": request.target_ref,
        "strategy": request.strategy,
        "lease_seconds": request.lease_seconds,
    }


def _operation(*, request: ProvisionRequest, phase: str = "start") -> OperationRecord:
    effects = (
        ("lease-create", "prepared-assignment-create", "target-write")
        if phase == "start"
        else ("assignment-commit", "selection-update", "proof-update")
    )
    return OperationRecord(
        operation_id=_OPERATION_IDS[-1],
        command="provision",
        phase=phase,
        idempotency_key="f" * 64,
        accepted_at=_NOW,
        normalized_input=_normalized(request=request),
        terminal_result=None,
        ordered_effects=effects,
        completed_step=-1,
    )


def _assert_composed(*, tmp_path: Path) -> None:
    import overseer._lpm_runtime_provision as provision_runtime

    target = _ProvisionTarget(owner_uid=os.getuid())
    host = _host(state_dir=tmp_path / "fixture", target=target)
    request = _request(run_id="fixture", target_ref=_issue(host=host, run_id="fixture"))
    result = provision_runtime.run_provision(host=host, request=request)
    assert isinstance(result, Success)
    receipt = cast("dict[str, object]", result.unwrap()["receipt"])
    assert receipt["record_id"] == _RECORD


def _store_failure(**_kwargs: object) -> Failure[ManagerError]:
    return Failure(store_unavailable(message="injected interruption"))


def _success_none(**_kwargs: object) -> Success[None]:
    return Success(None)


def _internal_failure(**_kwargs: object) -> Failure[ManagerError]:
    return Failure(internal_bug(message="injected drive refusal"))


def _assert_prepared_state(*, host: _Host, request: ProvisionRequest) -> None:
    from overseer._lpm_assignment import PREPARED_STATUS
    from overseer._lpm_leases import read_lease
    from overseer._lpm_paths import local_record_path
    from overseer._lpm_runtime_bindings import read_runtime_assignment

    assignment = read_runtime_assignment(
        host=host, consumer_run_id=request.consumer_run_id
    ).unwrap()
    assert assignment is not None
    assert assignment.status == PREPARED_STATUS
    lease_path = local_record_path(
        state_dir=host.state_dir,
        family="lease",
        identity=(request.provider, assignment.account_id),
    ).unwrap()
    lease = read_lease(path=lease_path, owner_uid=host.owner_uid).unwrap()
    assert lease is not None
    assert lease.consumer_run_id == request.consumer_run_id


def _assert_runtime_dispatch(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import overseer._lpm_runtime as runtime_module
    from overseer._lpm_commands import ManagerInvocation
    from overseer._lpm_runtime import ConcreteManagerRuntime

    target = _ProvisionTarget(owner_uid=os.getuid())
    host = _host(state_dir=tmp_path / "concrete-runtime", target=target)
    run_id = "run-concrete-runtime"
    target_ref = _OPERATION_IDS[0]
    report_object = {
        "version": 1,
        "consumer_run_id": run_id,
        "record_id": _RECORD,
        "occurred_at": _NOW,
        "classification": "unknown",
    }
    report_text = canonical_json_text(value=report_object).unwrap()
    inputs = iter(
        (
            canonical_json_text(
                value={
                    "version": 1,
                    "consumer_run_id": run_id,
                    "adapter": "isolated-run",
                }
            ).unwrap(),
            canonical_json_text(
                value=_normalized(request=_request(run_id=run_id, target_ref=target_ref))
            ).unwrap(),
            report_text,
            report_text,
        )
    )
    runtime = ConcreteManagerRuntime(
        state_dir=host.state_dir,
        owner_uid=host.owner_uid,
        config=host.config,
        read_input=lambda: next(inputs),
    )
    for name in (
        "store",
        "provision_target",
        "target_status",
        "op_executable",
        "capture_time",
        "new_operation_id",
        "monotonic",
        "sleep",
    ):
        object.__setattr__(runtime, name, getattr(host, name))

    target_result = runtime.run(invocation=ManagerInvocation(command="target", source="-"))
    provision_result = runtime.run(invocation=ManagerInvocation(command="provision", source="-"))
    report_result = runtime.run(invocation=ManagerInvocation(command="report", source="-"))
    duplicate_result = runtime.run(invocation=ManagerInvocation(command="report", source="-"))

    assert target_result.body == {
        "version": 1,
        "status": "ok",
        "operation": "target",
        "target_ref": target_ref,
        "expires_at": "2026-10-11T12:00:00Z",
    }
    assert provision_result.exit_status == 0
    assert provision_result.body["operation"] == "provision"
    assert _SECRET.decode() not in str(provision_result.body)
    assert report_result.body == {
        "version": 1,
        "status": "ok",
        "operation": "report",
        "duplicate": False,
    }
    assert duplicate_result.body == {
        "version": 1,
        "status": "ok",
        "operation": "report",
        "duplicate": True,
    }
    assert target.calls == [target_ref]
    target_text = canonical_json_text(
        value={"version": 1, "consumer_run_id": "another-run", "adapter": "isolated-run"}
    ).unwrap()
    disabled = replace(
        runtime,
        config=replace(runtime.config, enabled_target_adapters=()),
        read_input=lambda: target_text,
    )
    assert (
        disabled.run(invocation=ManagerInvocation(command="target", source="-")).body["error_type"]
        == "invalid-request"
    )
    with monkeypatch.context() as context:
        context.setattr(runtime_module, "run_target", _store_failure)
        object.__setattr__(runtime, "read_input", lambda: target_text)
        assert (
            runtime.run(invocation=ManagerInvocation(command="target", source="-")).body[
                "error_type"
            ]
            == "store-unavailable"
        )


def _report_fixture(*, tmp_path: Path) -> tuple[_Host, FailureReport, str]:
    from overseer._lpm_runtime_provision import run_provision

    target = _ProvisionTarget(owner_uid=os.getuid())
    host = _host(state_dir=tmp_path / "report-failures", target=target)
    run_id = "run-report-failures"
    reference = _issue(host=host, run_id=run_id)
    assert isinstance(
        run_provision(host=host, request=_request(run_id=run_id, target_ref=reference)),
        Success,
    )
    return (
        host,
        FailureReport(
            consumer_run_id=run_id,
            record_id=_RECORD,
            occurred_at=_NOW,
            classification="authentication",
        ),
        reference,
    )


def _assert_report_dependency_failures(
    *, host: _Host, report: FailureReport, monkeypatch: pytest.MonkeyPatch
) -> None:
    from overseer import _lpm_runtime_report as report_runtime

    for name in (
        "run_lock",
        "idempotency_key_for",
        "pending_operation",
        "report_binding",
        "new_operation",
        "write_new_operation",
    ):
        with monkeypatch.context() as context:
            context.setattr(report_runtime, name, _store_failure)
            assert isinstance(report_runtime.run_report(host=host, report=report), Failure)


def _assert_report_refusals_and_recovery(
    *,
    host: _Host,
    report: FailureReport,
    target_ref: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from overseer import _lpm_runtime_report as report_runtime

    mismatch = _operation(request=_request(run_id=report.consumer_run_id, target_ref=target_ref))
    with monkeypatch.context() as context:
        context.setattr(report_runtime, "pending_operation", lambda **_kwargs: Success(mismatch))
        refused = report_runtime.run_report(host=host, report=report)
        assert isinstance(refused, Failure)
        assert refused.failure().error_type == "invalid-report"
    assert isinstance(
        report_runtime.run_report(
            host=host,
            report=FailureReport(
                consumer_run_id=report.consumer_run_id,
                record_id="another-record",
                occurred_at=_NOW,
                classification="authentication",
            ),
        ),
        Failure,
    )
    assert isinstance(
        report_runtime.run_report(
            host=host,
            report=FailureReport(
                consumer_run_id=report.consumer_run_id,
                record_id=_RECORD,
                occurred_at="2026-10-11T12:00:01Z",
                classification="authentication",
            ),
        ),
        Failure,
    )
    with monkeypatch.context() as context:
        context.setattr(report_runtime, "drive_operation", _store_failure)
        assert isinstance(report_runtime.run_report(host=host, report=report), Failure)
        assert isinstance(report_runtime.run_report(host=host, report=report), Failure)
    recovered = report_runtime.run_report(host=host, report=report)
    assert recovered.unwrap() == {"operation": "report", "duplicate": False}
    assert report_runtime.run_report(host=host, report=report).unwrap() == {
        "operation": "report",
        "duplicate": True,
    }


def _assert_report_binding_refusals(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from overseer import _lpm_runtime_bindings as bindings
    from overseer._lpm_localstate import write_local_record
    from overseer._lpm_paths import local_record_path
    from overseer._lpm_runtime_provision import run_provision

    empty = _host(
        state_dir=tmp_path / "empty-report-binding",
        target=_ProvisionTarget(owner_uid=os.getuid()),
    )
    assert isinstance(bindings.report_binding(host=empty, consumer_run_id="absent"), Failure)
    for name in ("local_record_path", "read_runtime_assignment"):
        with monkeypatch.context() as context:
            context.setattr(bindings, name, _store_failure)
            assert isinstance(
                bindings.report_binding(host=empty, consumer_run_id="absent"), Failure
            )
    prepared_target = _ProvisionTarget(owner_uid=os.getuid(), statuses=[IN_PROGRESS])
    prepared = _host(state_dir=tmp_path / "prepared-report-binding", target=prepared_target)
    run_id = "run-prepared-report-binding"
    reference = _issue(host=prepared, run_id=run_id)
    assert isinstance(
        run_provision(host=prepared, request=_request(run_id=run_id, target_ref=reference)),
        Failure,
    )
    assert isinstance(bindings.report_binding(host=prepared, consumer_run_id=run_id), Failure)
    malformed_path = local_record_path(
        state_dir=empty.state_dir,
        family="tombstone",
        identity=("malformed-tombstone",),
    ).unwrap()
    assert isinstance(
        write_local_record(path=malformed_path, value={}, owner_uid=empty.owner_uid), Success
    )
    assert isinstance(
        bindings.report_binding(host=empty, consumer_run_id="malformed-tombstone"), Failure
    )


def test_concrete_runtime_drives_target_provision_and_report(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_runtime_dispatch(tmp_path=tmp_path, monkeypatch=monkeypatch)
    host, report, target_ref = _report_fixture(tmp_path=tmp_path)
    _assert_report_dependency_failures(host=host, report=report, monkeypatch=monkeypatch)
    _assert_report_refusals_and_recovery(
        host=host,
        report=report,
        target_ref=target_ref,
        monkeypatch=monkeypatch,
    )
    _assert_report_binding_refusals(tmp_path=tmp_path, monkeypatch=monkeypatch)


def test_provision_is_idempotent_and_selection_never_reads_a_raw_value(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_composed(tmp_path=tmp_path)
    import overseer._lpm_runtime_provision as provision_runtime

    target = _ProvisionTarget(owner_uid=os.getuid())
    host = _host(state_dir=tmp_path / "happy", target=target)
    monkeypatch.setattr(host.store, "credential_value_get", pytest.fail, raising=False)
    request = _request(run_id="run-a", target_ref=_issue(host=host, run_id="run-a"))
    first = provision_runtime.run_provision(host=host, request=request).unwrap()
    receipt = cast("dict[str, object]", first["receipt"])
    assert set(receipt) == {
        "record_id",
        "account_id",
        "purpose",
        "validated_at",
        "lease_expires_at",
    }
    assert provision_runtime.run_provision(host=host, request=request).unwrap() == first
    assert target.calls == [request.target_ref]
    assert _SECRET.decode() not in str(first)


def test_committed_target_effect_recovers_without_duplicate_write(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_composed(tmp_path=tmp_path)
    import overseer._lpm_effects_commit as commit_effect
    import overseer._lpm_runtime_provision as provision_runtime

    target = _ProvisionTarget(owner_uid=os.getuid())
    status = _TargetStatus(statuses=[COMMITTED])
    host = _host(state_dir=tmp_path / "committed", target=target, target_status=status)
    request = _request(run_id="run-b", target_ref=_issue(host=host, run_id="run-b"))
    with monkeypatch.context() as context:
        context.setattr(commit_effect, "write_local_record", _store_failure)
        interrupted = provision_runtime.run_provision(host=host, request=request)
    assert isinstance(interrupted, Failure)
    assert interrupted.failure().error_type == "store-unavailable"
    _assert_prepared_state(host=host, request=request)
    assert isinstance(provision_runtime.run_provision(host=host, request=request), Success)
    assert target.calls == [request.target_ref]
    assert status.calls == [request.target_ref]


def test_exact_target_evidence_survives_checkpoint_failure_without_duplicate_write(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import overseer._lpm_runtime_provision as provision_runtime
    from overseer._lpm_localstate import read_local_record
    from overseer._lpm_operation_store import checkpoint_step
    from overseer._lpm_paths import local_record_path
    from overseer._lpm_runtime_bindings import read_runtime_assignment

    engine = importlib.import_module("_lpm_engine")
    state_dir = tmp_path / "exact-evidence"
    target = _EvidenceTarget(state_dir=state_dir, owner_uid=os.getuid())
    host = _host(
        state_dir=state_dir,
        target=cast("_ProvisionTarget", target),
        target_status=cast("_TargetStatus", target.status),
    )
    request = _request(
        run_id="run-exact-evidence",
        target_ref=_issue(host=host, run_id="run-exact-evidence"),
    )

    def fail_target_checkpoint(
        *, path: Path, operation: OperationRecord, step: int, owner_uid: int
    ) -> Result[OperationRecord, ManagerError]:
        if step == 2:
            return Failure(store_unavailable(message="target checkpoint interrupted"))
        return checkpoint_step(
            path=path,
            operation=operation,
            step=step,
            owner_uid=owner_uid,
        )

    with monkeypatch.context() as context:
        context.setattr(engine, "checkpoint_step", fail_target_checkpoint)
        interrupted = provision_runtime.run_provision(host=host, request=request)
    assert isinstance(interrupted, Failure)
    assert interrupted.failure().error_type == "store-unavailable"
    _assert_prepared_state(host=host, request=request)

    recovered = provision_runtime.run_provision(host=host, request=request)
    assignment = read_runtime_assignment(
        host=host, consumer_run_id=request.consumer_run_id
    ).unwrap()
    evidence_path = local_record_path(
        state_dir=state_dir,
        family="target-commit",
        identity=(request.target_ref,),
    ).unwrap()
    evidence = read_local_record(path=evidence_path, owner_uid=host.owner_uid).unwrap()

    assert isinstance(recovered, Success)
    assert assignment is not None and assignment.status == COMMITTED
    assert target.writes == 1
    assert target.status_calls == 1
    assert isinstance(evidence, dict)
    assert set(cast("dict[str, object]", evidence)) == {
        "version",
        "status",
        "target_ref",
        "consumer_run_id",
        "value_generation",
        "target_sha256",
        "prepared_at",
        "committed_at",
    }


def test_ambiguous_target_effect_retains_state_until_status_is_definitive(
    *, tmp_path: Path
) -> None:
    _assert_composed(tmp_path=tmp_path)
    import overseer._lpm_runtime_provision as provision_runtime

    target = _ProvisionTarget(owner_uid=os.getuid(), statuses=[IN_PROGRESS, COMMITTED])
    status = _TargetStatus(statuses=[IN_PROGRESS, UNCOMMITTED])
    host = _host(state_dir=tmp_path / "ambiguous", target=target, target_status=status)
    request = _request(run_id="run-ambiguous", target_ref=_issue(host=host, run_id="run-ambiguous"))
    first = provision_runtime.run_provision(host=host, request=request)
    assert isinstance(first, Failure)
    assert first.failure().error_type == "retryable-exhaustion"
    _assert_prepared_state(host=host, request=request)
    second = provision_runtime.run_provision(host=host, request=request)
    assert isinstance(second, Failure)
    assert second.failure().error_type == "retryable-exhaustion"
    _assert_prepared_state(host=host, request=request)
    assert isinstance(provision_runtime.run_provision(host=host, request=request), Success)
    assert target.calls == [request.target_ref, request.target_ref]
    assert status.calls == [request.target_ref, request.target_ref]


def test_uncommitted_preparation_is_discarded_before_retry(*, tmp_path: Path) -> None:
    _assert_composed(tmp_path=tmp_path)
    import overseer._lpm_runtime_provision as provision_runtime

    target = _ProvisionTarget(owner_uid=os.getuid(), statuses=[UNCOMMITTED, COMMITTED])
    host = _host(state_dir=tmp_path / "uncommitted", target=target)
    request = _request(run_id="run-c", target_ref=_issue(host=host, run_id="run-c"))
    first = provision_runtime.run_provision(host=host, request=request)
    assert isinstance(first, Failure)
    assert first.failure().error_type == "provisioning-failed"
    assert isinstance(provision_runtime.run_provision(host=host, request=request), Success)
    assert target.calls == [request.target_ref, request.target_ref]


def test_provision_propagates_lock_and_selection_failures(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_composed(tmp_path=tmp_path)
    import overseer._lpm_runtime_provision as provision_runtime

    target = _ProvisionTarget(owner_uid=os.getuid())
    host = _host(state_dir=tmp_path / "failures", target=target)
    request = _request(run_id="run-d", target_ref=_issue(host=host, run_id="run-d"))
    for name in ("run_lock", "idempotency_key_for", "pending_operation"):
        with monkeypatch.context() as context:
            context.setattr(provision_runtime, name, _store_failure)
            assert isinstance(provision_runtime.run_provision(host=host, request=request), Failure)
    empty = _Host(
        state_dir=tmp_path / "empty",
        owner_uid=host.owner_uid,
        config=host.config,
        store=InMemorySecretStore(),
        provision_target=target,
        target_status=None,
        op_executable=host.op_executable,
        capture_time=host.capture_time,
        new_operation_id=host.new_operation_id,
        monotonic=host.monotonic,
        sleep=host.sleep,
    )
    assert isinstance(provision_runtime.run_provision(host=empty, request=request), Failure)


def test_provision_refuses_pending_or_assigned_request_mismatches(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_composed(tmp_path=tmp_path)
    import overseer._lpm_runtime_provision as provision_runtime

    host = _host(state_dir=tmp_path / "mismatches", target=_ProvisionTarget(owner_uid=os.getuid()))
    request = _request(run_id="run-mismatch", target_ref=_issue(host=host, run_id="run-mismatch"))
    changed = replace(request, strategy="spread")
    with monkeypatch.context() as context:
        context.setattr(
            provision_runtime,
            "pending_operation",
            lambda **_kwargs: Success(_operation(request=request)),
        )
        assert isinstance(provision_runtime.run_provision(host=host, request=changed), Failure)
    assert isinstance(provision_runtime.run_provision(host=host, request=request), Success)
    assert isinstance(provision_runtime.run_provision(host=host, request=changed), Failure)


def test_metadata_selection_skips_malformed_rows_and_keeps_typed_failures(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_runtime_selection.py"
    assert module_path.is_file()
    import overseer._lpm_runtime_selection as selection

    target = _ProvisionTarget(owner_uid=os.getuid())
    host = _host(state_dir=tmp_path / "selection", target=target)
    request = _request(run_id="run-selection", target_ref="target-selection")
    assert isinstance(selection.selected_for_request(host=host, request=request, now=_NOW), Success)
    for result in (
        {"status": "unavailable"},
        {"status": "ok", "items": "not-an-array"},
    ):
        with monkeypatch.context() as context:
            context.setattr(host.store, "metadata_list", lambda result=result: result)
            assert isinstance(
                selection.selected_for_request(host=host, request=request, now=_NOW), Failure
            )
    mixed = {
        "status": "ok",
        "items": [
            None,
            {"record": "{"},
            {"record": {}},
            {"record": _record_object()},
        ],
    }
    with monkeypatch.context() as context:
        context.setattr(host.store, "metadata_list", lambda: mixed)
        assert isinstance(
            selection.selected_for_request(host=host, request=request, now=_NOW), Success
        )


def test_selection_and_authoritative_reads_keep_typed_failure_rails(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_runtime_selection.py"
    assert module_path.is_file()
    import overseer._lpm_runtime_bindings as bindings
    import overseer._lpm_runtime_issuance as issuance
    import overseer._lpm_runtime_selection as selection

    host = _host(
        state_dir=tmp_path / "selection-failures",
        target=_ProvisionTarget(owner_uid=os.getuid()),
    )
    request = _request(run_id="run-selection", target_ref="target-selection")
    for name in ("local_record_path", "read_lease", "read_selection_state", "select_record"):
        with monkeypatch.context() as context:
            context.setattr(selection, name, _store_failure)
            assert isinstance(
                selection.selected_for_request(host=host, request=request, now=_NOW), Failure
            )
    with monkeypatch.context() as context:
        context.setattr(selection, "add_seconds", lambda **_kwargs: None)
        assert isinstance(
            selection.selected_for_request(host=host, request=request, now=_NOW), Failure
        )
    for name in ("assignment_path", "read_local_record"):
        with monkeypatch.context() as context:
            context.setattr(bindings, name, _store_failure)
            assert isinstance(
                bindings.read_runtime_assignment(host=host, consumer_run_id="run-selection"),
                Failure,
            )
    with monkeypatch.context() as context:
        context.setattr(issuance, "read_runtime_issuance", _store_failure)
        assert isinstance(
            issuance.resolved_runtime_issuance(host=host, request=request, bound=False), Failure
        )
    assert isinstance(
        issuance.resolved_runtime_issuance(host=host, request=request, bound=False), Failure
    )
    with monkeypatch.context() as context:
        context.setattr(issuance, "resolve_issuance", _store_failure)
        issued_request = replace(
            request,
            target_ref=_issue(host=host, run_id=request.consumer_run_id),
        )
        assert isinstance(
            issuance.resolved_runtime_issuance(host=host, request=issued_request, bound=False),
            Failure,
        )


def test_provision_coordinator_propagates_typed_failures(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_runtime_provision_recovery.py"
    assert module_path.is_file()
    import overseer._lpm_runtime_provision as provision_runtime

    host = _host(
        state_dir=tmp_path / "coordinator-failures",
        target=_ProvisionTarget(owner_uid=os.getuid()),
    )
    request = _request(
        run_id="run-coordinator", target_ref=_issue(host=host, run_id="run-coordinator")
    )
    for name in ("read_runtime_assignment", "fresh_provision"):
        with monkeypatch.context() as context:
            context.setattr(provision_runtime, name, _store_failure)
            assert isinstance(provision_runtime.run_provision(host=host, request=request), Failure)


def test_fresh_and_resumed_provision_propagate_typed_dependencies(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_runtime_provision_recovery.py"
    assert module_path.is_file()
    import overseer._lpm_runtime_provision_recovery as recovery

    host = _host(
        state_dir=tmp_path / "dependency-failures",
        target=_ProvisionTarget(owner_uid=os.getuid()),
    )
    request = _request(
        run_id="run-dependencies", target_ref=_issue(host=host, run_id="run-dependencies")
    )
    for name in (
        "resolved_runtime_issuance",
        "selected_for_request",
        "new_operation",
        "write_new_operation",
        "provision_effect_inputs",
        "drive_provision",
    ):
        with monkeypatch.context() as context:
            context.setattr(recovery, name, _store_failure)
            assert isinstance(
                recovery.fresh_provision(
                    host=host, request=request, normalized=_normalized(request=request)
                ),
                Failure,
            )
    for name in ("selected_for_request", "provision_effect_inputs", "drive_provision"):
        with monkeypatch.context() as context:
            context.setattr(recovery, name, _store_failure)
            assert isinstance(
                recovery.resume_provision(
                    host=host,
                    request=request,
                    operation=_operation(request=request),
                    assignment=None,
                ),
                Failure,
            )


def test_provision_phase_driver_propagates_typed_failures(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_runtime_provision_recovery.py"
    assert module_path.is_file()
    import overseer._lpm_runtime_provision_recovery as recovery

    host = _host(
        state_dir=tmp_path / "driver-failures", target=_ProvisionTarget(owner_uid=os.getuid())
    )
    request = _request(run_id="run-driver", target_ref=_issue(host=host, run_id="run-driver"))
    start = _operation(request=request)
    postcommit = _operation(request=request, phase="postcommit")
    assert isinstance(
        recovery.drive_provision(
            host=host, request=request, operation=start, inputs=EffectInputs(), drive=_success_none
        ),
        Failure,
    )
    for replacement in (_store_failure, lambda **_kwargs: Success(None)):
        with monkeypatch.context() as context:
            context.setattr(recovery, "read_runtime_assignment", replacement)
            assert isinstance(
                recovery.drive_provision(
                    host=host,
                    request=request,
                    operation=postcommit,
                    inputs=EffectInputs(),
                    drive=_success_none,
                ),
                Failure,
            )
    for operation in (start, postcommit):
        assert isinstance(
            recovery.drive_provision(
                host=host,
                request=request,
                operation=operation,
                inputs=EffectInputs(),
                drive=_internal_failure,
            ),
            Failure,
        )


def test_cleanup_recovery_and_reselection_keep_typed_failures(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_runtime_provision_recovery.py"
    assert module_path.is_file()
    import overseer._lpm_runtime_provision_recovery as recovery

    host = _host(
        state_dir=tmp_path / "cleanup-failures", target=_ProvisionTarget(owner_uid=os.getuid())
    )
    request = _request(run_id="run-cleanup", target_ref=_issue(host=host, run_id="run-cleanup"))
    cleanup = replace(
        _operation(request=request),
        phase="cleanup",
        ordered_effects=("prepared-assignment-discard", "lease-release"),
    )
    for name in ("selected_for_request", "provision_effect_inputs", "finish_provision_cleanup"):
        with monkeypatch.context() as context:
            context.setattr(recovery, name, _store_failure)
            assert isinstance(
                recovery.resume_provision(
                    host=host, request=request, operation=cleanup, assignment=None
                ),
                Failure,
            )
    with monkeypatch.context() as context:
        context.setattr(recovery, "finish_provision_cleanup", _success_none)
        assert (
            recovery.resume_provision(
                host=host, request=request, operation=cleanup, assignment=None
            ).unwrap()
            is None
        )
    moving_host = replace(host, capture_time=iter((_NOW, "2026-10-10T12:00:01Z")).__next__)
    with monkeypatch.context() as context:
        context.setattr(recovery, "write_new_operation", _store_failure)
        assert isinstance(
            recovery.fresh_provision(
                host=moving_host, request=request, normalized=_normalized(request=request)
            ),
            Failure,
        )


def test_reselection_and_cleanup_effects_keep_typed_failures(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_runtime_provision_recovery.py"
    assert module_path.is_file()
    import overseer._lpm_runtime_provision_effects as effects
    import overseer._lpm_runtime_provision_recovery as recovery

    host = _host(
        state_dir=tmp_path / "effect-failures", target=_ProvisionTarget(owner_uid=os.getuid())
    )
    request = _request(run_id="run-effects", target_ref=_issue(host=host, run_id="run-effects"))
    operation = _operation(request=request)
    selected = recovery.selected_for_request(host=host, request=request, now=_NOW).unwrap()
    selections: list[Result[object, ManagerError]] = [
        Success(selected),
        Failure(store_unavailable(message="injected reselection refusal")),
    ]
    moving_host = replace(host, capture_time=iter((_NOW, "2026-10-10T12:00:01Z")).__next__)
    with monkeypatch.context() as context:
        context.setattr(recovery, "selected_for_request", lambda **_kwargs: selections.pop(0))
        assert isinstance(
            recovery.fresh_provision(
                host=moving_host, request=request, normalized=_normalized(request=request)
            ),
            Failure,
        )
    for name in ("pending_operation", "operation_path", "transition_operation"):
        with monkeypatch.context() as context:
            if name != "pending_operation":
                context.setattr(
                    effects,
                    "pending_operation",
                    lambda **_kwargs: Success(operation),
                )
            context.setattr(effects, name, _store_failure)
            assert isinstance(
                effects.cleanup_failed_start(host=host, operation=operation, inputs=EffectInputs()),
                Failure,
            )


def test_cleanup_effect_edge_cases_remain_typed(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_runtime_provision_recovery.py"
    assert module_path.is_file()
    import overseer._lpm_runtime_provision_effects as effects
    import overseer._lpm_runtime_provision_recovery as recovery

    host = _host(
        state_dir=tmp_path / "cleanup-edges", target=_ProvisionTarget(owner_uid=os.getuid())
    )
    request = _request(
        run_id="run-cleanup-edges", target_ref=_issue(host=host, run_id="run-cleanup-edges")
    )
    operation = _operation(request=request)
    with monkeypatch.context() as context:
        context.setattr(effects, "pending_operation", _success_none)
        assert isinstance(
            effects.cleanup_failed_start(host=host, operation=operation, inputs=EffectInputs()),
            Failure,
        )
    with monkeypatch.context() as context:
        context.setattr(effects, "pending_operation", lambda **_kwargs: Success(operation))
        context.setattr(effects, "transition_operation", _success_none)
        assert isinstance(
            effects.cleanup_failed_start(host=host, operation=operation, inputs=EffectInputs()),
            Failure,
        )
    with monkeypatch.context() as context:
        context.setattr(effects, "drive_operation", _store_failure)
        assert isinstance(
            effects.finish_provision_cleanup(
                host=host, operation=operation, inputs=EffectInputs(), prepared=True
            ),
            Failure,
        )
    selected = recovery.selected_for_request(host=host, request=request, now=_NOW).unwrap()
    with monkeypatch.context() as context:
        context.setattr(effects, "resolved_runtime_issuance", _store_failure)
        assert isinstance(
            effects.provision_effect_inputs(host=host, request=request, selected=selected), Failure
        )


def test_final_target_callback_and_direct_adapter_failures_remain_typed(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_runtime_provision_effects.py"
    assert module_path.is_file()
    import overseer._lpm_effects_commit as commit_effect
    import overseer._lpm_runtime_provision as provision_runtime

    target = _ProvisionTarget(owner_uid=os.getuid())
    host = _host(state_dir=tmp_path / "target-failures", target=target)
    request = _request(
        run_id="run-target-failures", target_ref=_issue(host=host, run_id="run-target-failures")
    )
    failing_host = replace(host, provision_target=cast("_ProvisionTarget", _store_failure))
    assert isinstance(provision_runtime.run_provision(host=failing_host, request=request), Failure)
    in_progress = _ProvisionTarget(owner_uid=os.getuid(), statuses=[IN_PROGRESS])
    in_progress_host = replace(host, provision_target=in_progress)
    assert isinstance(
        provision_runtime.run_provision(host=in_progress_host, request=request), Failure
    )
    from overseer._lpm_engine_context import ProvisionInputs, SelectedCredential

    refused = commit_effect._local_target_write(
        context=cast("object", None),
        inputs=ProvisionInputs(
            selected=SelectedCredential(
                account_id="account-a",
                record_id=_RECORD,
                value_generation=_GENERATION,
                value_ref="op://value",
                receipt={},
            ),
            credential_value=None,
            destination=str(tmp_path / "never-written"),
            lock=TargetLock(
                path=tmp_path / "target.lock",
                timeout_seconds=1.0,
                monotonic=lambda: 0.0,
                sleep=lambda _seconds: None,
            ),
            fence_now=_NOW,
        ),
        lease_expires_at="2026-10-10T13:00:00Z",
    )
    assert isinstance(refused, Failure)
