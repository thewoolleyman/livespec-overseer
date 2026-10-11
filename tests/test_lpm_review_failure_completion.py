"""Negative-path completion for the accepted runtime review findings."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

import overseer._lpm_runtime_provision_recovery as provision_recovery
import overseer._lpm_runtime_selection as runtime_selection
import overseer._lpm_target_evidence as target_evidence
from overseer._lpm_assignment import Assignment
from overseer._lpm_attention import attention_items
from overseer._lpm_canonical import canonical_json_text
from overseer._lpm_config import ManagerConfig, default_config
from overseer._lpm_engine_context import EffectInputs, SelectedCredential
from overseer._lpm_leases import AccountLease, lease_object
from overseer._lpm_localstate import write_local_bytes, write_local_record
from overseer._lpm_operation import OperationRecord
from overseer._lpm_paths import local_record_path
from overseer._lpm_provision_request import ProvisionRequest
from overseer._lpm_record import CredentialRecord
from overseer._lpm_results import ManagerError, store_unavailable
from overseer._lpm_runtime_roles import FinalProvisioningRequest
from overseer._lpm_store import ConditionalSet, InMemorySecretStore, SecretStore
from overseer._lpm_target import COMMITTED, IN_PROGRESS, CommitOutcome, TargetLock
from overseer._lpm_target_evidence import (
    TargetEvidenceBinding,
    commit_with_evidence,
    target_evidence_from_object,
    target_status_with_evidence,
)
from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = []

_NOW = "2026-10-10T20:00:00Z"
_COMMITTED_AT = "2026-10-10T20:00:01Z"
_EXPIRES = "2026-10-10T21:00:00Z"
_OPERATION = "10000000-0000-4000-8000-000000000001"
_RECORD_A = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_RECORD_B = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_GENERATION = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"
_SECRET = b"negative-path-secret"


def _store_failure(**_kwargs: object) -> Failure[ManagerError]:
    return Failure(store_unavailable(message="injected unavailable"))


def _binding(*, tmp_path: Path, suffix: str) -> TargetEvidenceBinding:
    return TargetEvidenceBinding(
        state_dir=tmp_path / suffix / "state",
        destination=str(tmp_path / suffix / "target" / "credential"),
        owner_uid=os.getuid(),
        target_ref=f"target-{suffix}",
        consumer_run_id=f"run-{suffix}",
        value_generation=_GENERATION,
    )


def _evidence_path(*, binding: TargetEvidenceBinding) -> Path:
    return local_record_path(
        state_dir=binding.state_dir,
        family="target-commit",
        identity=(binding.target_ref,),
    ).unwrap()


def _evidence_object(
    *, binding: TargetEvidenceBinding, status: str, committed_at: str | None
) -> dict[str, object]:
    return {
        "version": 1,
        "status": status,
        "target_ref": binding.target_ref,
        "consumer_run_id": binding.consumer_run_id,
        "value_generation": binding.value_generation,
        "target_sha256": hashlib.sha256(_SECRET).hexdigest(),
        "prepared_at": _NOW,
        "committed_at": committed_at,
    }


def _seed_evidence(
    *, binding: TargetEvidenceBinding, status: str, committed_at: str | None
) -> None:
    write_local_record(
        path=_evidence_path(binding=binding),
        value=_evidence_object(binding=binding, status=status, committed_at=committed_at),
        owner_uid=binding.owner_uid,
    ).unwrap()


def _safe_target(*, binding: TargetEvidenceBinding) -> None:
    destination = Path(binding.destination)
    destination.parent.mkdir(mode=0o700, parents=True)
    _ = destination.write_bytes(_SECRET)
    destination.chmod(0o600)


def _assert_target_read_failure(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
    method: str,
) -> None:
    binding = _binding(tmp_path=tmp_path, suffix=suffix)
    _safe_target(binding=binding)
    _seed_evidence(binding=binding, status="armed", committed_at=_COMMITTED_AT)
    destination = Path(binding.destination)
    original = getattr(Path, method)

    def fail_destination(self: Path, *args: object, **kwargs: object) -> object:
        if self == destination:
            raise OSError("injected target read failure")
        return original(self, *args, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(Path, method, fail_destination)
        assert isinstance(target_status_with_evidence(binding=binding), Failure)


def test_attention_refuses_unreadable_nonobject_and_wrong_shape_artifacts(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unreadable = tmp_path / "unreadable"
    write_local_record(
        path=unreadable / "attention" / "one.json",
        value={"placeholder": True},
        owner_uid=os.getuid(),
    ).unwrap()
    monkeypatch.setattr("overseer._lpm_attention.read_local_record", _store_failure)
    refused = attention_items(state_dir=unreadable, owner_uid=os.getuid())
    assert isinstance(refused, Failure)
    monkeypatch.undo()

    nonobject = tmp_path / "nonobject"
    write_local_bytes(
        path=nonobject / "attention" / "one.json",
        payload=b"[]",
        owner_uid=os.getuid(),
    ).unwrap()
    assert isinstance(attention_items(state_dir=nonobject, owner_uid=os.getuid()), Failure)

    wrong_shape = tmp_path / "wrong-shape"
    write_local_record(
        path=wrong_shape / "attention" / "one.json",
        value={"version": 1},
        owner_uid=os.getuid(),
    ).unwrap()
    assert isinstance(attention_items(state_dir=wrong_shape, owner_uid=os.getuid()), Failure)


def test_target_evidence_returns_typed_failures_for_local_record_operations(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unreadable = _binding(tmp_path=tmp_path, suffix="unreadable")
    monkeypatch.setattr(target_evidence, "read_local_record", _store_failure)
    assert isinstance(target_status_with_evidence(binding=unreadable), Failure)
    monkeypatch.undo()

    prepared = _binding(tmp_path=tmp_path, suffix="prepared-cleanup")
    _seed_evidence(binding=prepared, status="prepared", committed_at=None)
    monkeypatch.setattr(target_evidence, "_discard_attempt", _store_failure)
    assert isinstance(target_status_with_evidence(binding=prepared), Failure)
    monkeypatch.undo()

    armed_absent = _binding(tmp_path=tmp_path, suffix="armed-remove")
    _seed_evidence(binding=armed_absent, status="armed", committed_at=_COMMITTED_AT)
    monkeypatch.setattr(target_evidence, "remove_local_record", _store_failure)
    assert isinstance(target_status_with_evidence(binding=armed_absent), Failure)
    monkeypatch.undo()

    armed_present = _binding(tmp_path=tmp_path, suffix="armed-persist")
    _safe_target(binding=armed_present)
    _seed_evidence(binding=armed_present, status="armed", committed_at=_COMMITTED_AT)
    monkeypatch.setattr(target_evidence, "write_target_evidence", _store_failure)
    assert isinstance(target_status_with_evidence(binding=armed_present), Failure)


def test_target_evidence_maps_filesystem_exceptions_without_losing_ambiguity(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replacement = _binding(tmp_path=tmp_path, suffix="replacement")
    real_replace = Path.replace
    staged_name = ".credential.lpm-prepared"

    def fail_staged_replace(self: Path, target: Path) -> Path:
        if self.name == staged_name:
            raise OSError("injected replacement failure")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_staged_replace)
    ambiguous = commit_with_evidence(
        binding=replacement,
        value=_SECRET,
        lease_expires_at=_EXPIRES,
        sample_time=iter((_NOW, _COMMITTED_AT)).__next__,
    )
    assert ambiguous.status == IN_PROGRESS
    monkeypatch.undo()

    unlinking = _binding(tmp_path=tmp_path, suffix="unlink")
    _seed_evidence(binding=unlinking, status="prepared", committed_at=None)
    real_unlink = Path.unlink

    def fail_staged_unlink(self: Path, *, missing_ok: bool = False) -> None:
        if self.name == ".credential.lpm-prepared":
            raise OSError("injected unlink failure")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_staged_unlink)
    assert isinstance(target_status_with_evidence(binding=unlinking), Failure)
    monkeypatch.undo()

    for suffix, method in (("lstat", "lstat"), ("read", "read_bytes")):
        _assert_target_read_failure(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            suffix=suffix,
            method=method,
        )


def test_prepared_evidence_rejects_a_commit_timestamp() -> None:
    binding = TargetEvidenceBinding(
        state_dir=Path("/unused"),
        destination="/unused/credential",
        owner_uid=os.getuid(),
        target_ref="target-a",
        consumer_run_id="run-a",
        value_generation=_GENERATION,
    )
    parsed = _evidence_object(binding=binding, status="prepared", committed_at=_COMMITTED_AT)
    assert isinstance(target_evidence_from_object(parsed=parsed), Failure)


@dataclass(frozen=True, kw_only=True)
class _UnusedTarget:
    def __call__(
        self,
        *,
        request: FinalProvisioningRequest,
        destination: str,
        lock: TargetLock,
    ) -> Result[CommitOutcome, ManagerError]:
        _ = (request, destination, lock)
        return _store_failure()


@dataclass(frozen=True, kw_only=True)
class _Host:
    state_dir: Path
    owner_uid: int
    config: ManagerConfig
    store: SecretStore
    op_executable: str | None
    capture_time: Callable[[], str]
    new_operation_id: Callable[[], str]
    monotonic: Callable[[], float]
    sleep: Callable[[float], None]
    provision_target: _UnusedTarget
    target_status: None


def _host(*, tmp_path: Path, store: SecretStore) -> _Host:
    return _Host(
        state_dir=tmp_path / "state",
        owner_uid=os.getuid(),
        config=default_config(),
        store=store,
        op_executable=None,
        capture_time=lambda: _NOW,
        new_operation_id=lambda: _OPERATION,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
        provision_target=_UnusedTarget(),
        target_status=None,
    )


def _request(*, run_id: str = "run-recovery") -> ProvisionRequest:
    return ProvisionRequest(
        provider="anthropic",
        kind="claude-code-oauth",
        purpose="factory",
        consumer_run_id=run_id,
        target_ref="target-recovery",
        strategy="consume-first",
        lease_seconds=3600,
    )


def _record(*, record_id: str, account_id: str, provider: str = "anthropic") -> dict[str, object]:
    return {
        "version": 1,
        "record_id": record_id,
        "provider": provider,
        "account_id": account_id,
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": _NOW,
        "expires_at": None,
        "last_validated": _NOW,
        "value_generation": _GENERATION,
        "value_ref": f"op://values/{record_id}/credential",
        "previous_value_ref": None,
    }


def _seed_record(
    *, store: InMemorySecretStore, record_id: str, account_id: str, provider: str = "anthropic"
) -> None:
    outcome = store.credential_conditional_set(
        request=ConditionalSet(
            record_id=record_id,
            effect_id=hashlib.sha256(record_id.encode()).hexdigest(),
            expected_record=None,
            desired_record=canonical_json_text(
                value=_record(record_id=record_id, account_id=account_id, provider=provider)
            ).unwrap(),
        )
    )
    assert outcome["status"] == COMMITTED


def _lease(
    *, host: _Host, request: ProvisionRequest, record_id: str, account_id: str
) -> AccountLease:
    lease = AccountLease(
        provider=request.provider,
        account_id=account_id,
        record_id=record_id,
        consumer_run_id=request.consumer_run_id,
        lease_started_at=_NOW,
        lease_expires_at=_EXPIRES,
    )
    path = local_record_path(
        state_dir=host.state_dir,
        family="lease",
        identity=(request.provider, account_id),
    ).unwrap()
    write_local_record(
        path=path, value=lease_object(lease=lease), owner_uid=host.owner_uid
    ).unwrap()
    return lease


def test_selection_recovery_refuses_absent_ambiguous_and_unsafe_authority(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unavailable = _host(tmp_path=tmp_path / "unavailable", store=InMemorySecretStore())
    monkeypatch.setattr(unavailable.store, "metadata_list", lambda: {"status": "unavailable"})
    assert isinstance(
        runtime_selection.selected_for_recovery(
            host=unavailable, request=_request(), lease_started_at=_NOW
        ),
        Failure,
    )
    monkeypatch.undo()

    absent_store = InMemorySecretStore()
    _seed_record(store=absent_store, record_id=_RECORD_A, account_id="account-a")
    absent = _host(tmp_path=tmp_path / "absent", store=absent_store)
    assert isinstance(
        runtime_selection.selected_for_recovery(
            host=absent, request=_request(), lease_started_at=_NOW
        ),
        Failure,
    )

    ambiguous_store = InMemorySecretStore()
    _seed_record(store=ambiguous_store, record_id=_RECORD_A, account_id="account-a")
    _seed_record(store=ambiguous_store, record_id=_RECORD_B, account_id="account-b")
    ambiguous = _host(tmp_path=tmp_path / "ambiguous", store=ambiguous_store)
    request = _request()
    _ = _lease(host=ambiguous, request=request, record_id=_RECORD_A, account_id="account-a")
    _ = _lease(host=ambiguous, request=request, record_id=_RECORD_B, account_id="account-b")
    assert isinstance(
        runtime_selection.selected_for_recovery(
            host=ambiguous, request=request, lease_started_at=_NOW
        ),
        Failure,
    )

    one_store = InMemorySecretStore()
    _seed_record(store=one_store, record_id=_RECORD_A, account_id="account-a")
    one = _host(tmp_path=tmp_path / "one", store=one_store)
    _ = _lease(host=one, request=request, record_id=_RECORD_A, account_id="account-a")
    with monkeypatch.context() as context:
        context.setattr(runtime_selection, "local_record_path", _store_failure)
        assert isinstance(
            runtime_selection.selected_for_recovery(
                host=one, request=request, lease_started_at=_NOW
            ),
            Failure,
        )
    with monkeypatch.context() as context:
        context.setattr(runtime_selection, "read_lease", _store_failure)
        assert isinstance(
            runtime_selection.selected_for_recovery(
                host=one, request=request, lease_started_at=_NOW
            ),
            Failure,
        )


def test_selection_recovery_ignores_other_metadata_and_refuses_incomplete_binding(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = InMemorySecretStore()
    _seed_record(store=store, record_id=_RECORD_B, account_id="other", provider="other-provider")
    _seed_record(store=store, record_id=_RECORD_A, account_id="account-a")
    host = _host(tmp_path=tmp_path, store=store)
    request = _request()
    lease = _lease(host=host, request=request, record_id=_RECORD_A, account_id="account-a")
    selected = runtime_selection.selected_for_recovery(
        host=host, request=request, lease_started_at=_NOW
    ).unwrap()
    assert selected.record_id == _RECORD_A

    incomplete = CredentialRecord(
        record_id=_RECORD_A,
        provider="anthropic",
        account_id="account-a",
        kind="claude-code-oauth",
        purpose="factory",
        status="dead",
        acquired_at=_NOW,
        expires_at=None,
        last_validated=None,
        value_generation=None,
        value_ref=None,
        previous_value_ref=None,
    )

    def incomplete_records(**_kwargs: object) -> Success[tuple[CredentialRecord, ...]]:
        return Success((incomplete,))

    def retained_lease(**_kwargs: object) -> Success[AccountLease]:
        return Success(lease)

    with monkeypatch.context() as context:
        context.setattr(runtime_selection, "_metadata_records", incomplete_records)
        context.setattr(runtime_selection, "_lease_for_record", retained_lease)
        assert isinstance(
            runtime_selection.selected_for_recovery(
                host=host, request=request, lease_started_at=_NOW
            ),
            Failure,
        )


def _assignment(*, request: ProvisionRequest) -> Assignment:
    return Assignment(
        status="committed",
        request={
            "version": 1,
            "provider": request.provider,
            "kind": request.kind,
            "purpose": request.purpose,
            "consumer_run_id": request.consumer_run_id,
            "target_ref": request.target_ref,
            "strategy": request.strategy,
            "lease_seconds": request.lease_seconds,
        },
        target_ref=request.target_ref,
        account_id="account-a",
        value_generation=_GENERATION,
        value_ref=f"op://values/{_GENERATION}/credential",
        record_id=_RECORD_A,
        receipt={
            "record_id": _RECORD_A,
            "account_id": "account-a",
            "purpose": request.purpose,
            "validated_at": _NOW,
            "lease_expires_at": _EXPIRES,
        },
        lease_started_at=_NOW,
        lease_expires_at=_EXPIRES,
        target_committed_at=_COMMITTED_AT,
        actual_lease_ended_at=None,
        report_markers=(),
        completion=None,
    )


def _cleanup_operation(*, request: ProvisionRequest) -> OperationRecord:
    return OperationRecord(
        operation_id=_OPERATION,
        command="provision",
        phase="cleanup",
        idempotency_key="e" * 64,
        accepted_at=_NOW,
        normalized_input=dict(_assignment(request=request).request),
        terminal_result=None,
        ordered_effects=("prepared-assignment-discard", "lease-release"),
        completed_step=-1,
    )


def test_cleanup_recovery_prefers_retained_assignment_or_exact_lease(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = InMemorySecretStore()
    _seed_record(store=store, record_id=_RECORD_A, account_id="account-a")
    host = _host(tmp_path=tmp_path, store=store)
    request = _request()
    _ = _lease(host=host, request=request, record_id=_RECORD_A, account_id="account-a")
    seen: list[str] = []

    def inputs(**kwargs: object) -> Success[EffectInputs]:
        seen.append(cast("SelectedCredential", kwargs["selected"]).record_id)
        return Success(EffectInputs())

    def finished(**_kwargs: object) -> Success[None]:
        return Success(None)

    monkeypatch.setattr(provision_recovery, "selected_for_request", _store_failure)
    monkeypatch.setattr(provision_recovery, "provision_effect_inputs", inputs)
    monkeypatch.setattr(provision_recovery, "finish_provision_cleanup", finished)
    operation = _cleanup_operation(request=request)
    assert isinstance(
        provision_recovery.resume_provision(
            host=host, request=request, operation=operation, assignment=None
        ),
        Success,
    )
    assert isinstance(
        provision_recovery.resume_provision(
            host=host,
            request=request,
            operation=operation,
            assignment=_assignment(request=request),
        ),
        Success,
    )
    assert seen == [_RECORD_A, _RECORD_A]
