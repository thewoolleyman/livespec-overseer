"""The concrete target runtime issues and recovers one durable target reference."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from overseer._lpm_config import ManagerConfig, default_config
from overseer._lpm_results import ManagerError, internal_bug, store_unavailable
from overseer._lpm_runtime_roles import FinalProvisioningRequest
from overseer._lpm_store import InMemorySecretStore, SecretStore
from overseer._lpm_target import CommitOutcome, TargetLock
from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = []

_NOW = "2026-10-10T12:00:00Z"
_LATER = "2026-10-12T12:00:00Z"
_OPERATION_IDS = (
    "10000000-0000-4000-8000-000000000001",
    "20000000-0000-4000-8000-000000000002",
    "30000000-0000-4000-8000-000000000003",
    "40000000-0000-4000-8000-000000000004",
    "50000000-0000-4000-8000-000000000005",
    "60000000-0000-4000-8000-000000000006",
)


class _UnusedProvision:
    def __call__(
        self,
        *,
        request: FinalProvisioningRequest,
        destination: str,
        lock: TargetLock,
    ) -> Result[CommitOutcome, ManagerError]:
        del request, destination, lock
        return Failure(internal_bug(message="provisioning was not expected"))


@dataclass(frozen=True, kw_only=True)
class _Host:
    state_dir: Path
    owner_uid: int
    config: ManagerConfig
    store: SecretStore
    provision_target: _UnusedProvision
    op_executable: str
    capture_time: Callable[[], str]
    new_operation_id: Callable[[], str]
    monotonic: Callable[[], float]
    sleep: Callable[[float], None]


def _host(*, state_dir: Path, now: str = _NOW) -> _Host:
    identifiers = iter(_OPERATION_IDS)
    return _Host(
        state_dir=state_dir,
        owner_uid=os.getuid(),
        config=default_config(),
        store=InMemorySecretStore(),
        provision_target=_UnusedProvision(),
        op_executable="/usr/bin/op",
        capture_time=lambda: now,
        new_operation_id=lambda: next(identifiers),
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )


def _request(*, run_id: str) -> dict[str, object]:
    return {
        "version": 1,
        "consumer_run_id": run_id,
        "adapter": "isolated-run",
    }


def _store_failure(**_kwargs: object) -> Failure[ManagerError]:
    return Failure(store_unavailable(message="injected refusal"))


def _none_success(**_kwargs: object) -> Success[None]:
    return Success(None)


def _assert_composed(*, tmp_path: Path) -> None:
    import overseer._lpm_runtime_target as target_runtime

    first = target_runtime.run_target(
        host=_host(state_dir=tmp_path / "fixture"),
        normalized_input=_request(run_id="run-fixture"),
    )
    assert isinstance(first, Success)
    assert first.unwrap()["target_ref"] == _OPERATION_IDS[0]


def test_target_runtime_issues_retries_and_recovers(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_composed(tmp_path=tmp_path)
    import overseer._lpm_runtime_target as target_runtime

    host = _host(state_dir=tmp_path / "happy")
    first = target_runtime.run_target(host=host, normalized_input=_request(run_id="run-a"))
    payload = first.unwrap()
    assert payload == {
        "operation": "target",
        "target_ref": _OPERATION_IDS[0],
        "expires_at": "2026-10-11T12:00:00Z",
    }
    assert (
        target_runtime.run_target(host=host, normalized_input=_request(run_id="run-a")).unwrap()
        == payload
    )
    interrupted = _host(state_dir=tmp_path / "interrupted")
    with monkeypatch.context() as context:
        context.setattr(
            target_runtime,
            "drive_operation",
            _store_failure,
        )
        assert isinstance(
            target_runtime.run_target(host=interrupted, normalized_input=_request(run_id="run-b")),
            Failure,
        )
    assert (
        target_runtime.run_target(
            host=interrupted, normalized_input=_request(run_id="run-b")
        ).unwrap()["target_ref"]
        == _OPERATION_IDS[0]
    )


def test_target_runtime_refuses_changed_and_expired_retries(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_composed(tmp_path=tmp_path)
    import overseer._lpm_runtime_target as target_runtime

    mismatch = _host(state_dir=tmp_path / "mismatch")
    with monkeypatch.context() as context:
        context.setattr(
            target_runtime,
            "drive_operation",
            _store_failure,
        )
        assert isinstance(
            target_runtime.run_target(host=mismatch, normalized_input=_request(run_id="run-c")),
            Failure,
        )
    changed = _request(run_id="run-c")
    changed["adapter"] = "different"
    assert isinstance(target_runtime.run_target(host=mismatch, normalized_input=changed), Failure)
    host = _host(state_dir=tmp_path / "issued")
    _ = target_runtime.run_target(host=host, normalized_input=_request(run_id="run-a")).unwrap()
    assert isinstance(target_runtime.run_target(host=host, normalized_input=changed), Failure)
    expired = target_runtime.run_target(
        host=replace(host, capture_time=lambda: _LATER),
        normalized_input=_request(run_id="run-a"),
    )
    assert isinstance(expired, Failure)
    assert expired.failure().error_type == "invalid-request"


def test_target_runtime_base_types_construction_and_lock_failures(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_composed(tmp_path=tmp_path)
    from overseer import _lpm_runtime_base as runtime_base
    from overseer._lpm_operation import OperationRecord
    from overseer._lpm_operation_plan import PlanContext

    host = _host(state_dir=tmp_path / "base")
    operation = OperationRecord(
        operation_id=_OPERATION_IDS[5],
        command="target",
        phase="issue",
        idempotency_key="a" * 64,
        accepted_at=_NOW,
        normalized_input=_request(run_id="run-errors"),
        terminal_result=None,
        ordered_effects=("issuance-create", "registration-remove"),
        completed_step=-1,
    )
    for name in ("idempotency_key_for", "ordered_effects_for"):
        with monkeypatch.context() as context:
            context.setattr(
                runtime_base,
                name,
                _store_failure,
            )
            assert isinstance(
                runtime_base.new_operation(
                    host=host,
                    command="target",
                    phase="issue",
                    normalized_input=_request(run_id="run-errors"),
                    context=PlanContext(),
                ),
                Failure,
            )
    with monkeypatch.context() as context:
        context.setattr(
            runtime_base,
            "operation_path",
            _store_failure,
        )
        assert isinstance(runtime_base.write_new_operation(host=host, operation=operation), Failure)
    blocked_root = tmp_path / "blocked-root"
    _ = blocked_root.write_text("not a directory", encoding="utf-8")
    assert isinstance(
        runtime_base.run_lock(
            host=replace(host, state_dir=blocked_root), consumer_run_id="run-errors"
        ),
        Failure,
    )


def test_target_runtime_reads_authoritative_issuances(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_composed(tmp_path=tmp_path)
    from overseer import _lpm_runtime_issuance as runtime_issuance
    from overseer._lpm_localstate import write_local_record
    from overseer._lpm_paths import local_record_path
    from overseer._lpm_target import TargetIssuance, issuance_object

    host = _host(state_dir=tmp_path / "issuances")
    issued = TargetIssuance(
        reference="reference-a",
        consumer_run_id="run-issuance",
        adapter="isolated-run",
        destination="destination-a",
        issued_at=_NOW,
        expires_at="2026-10-11T12:00:00Z",
    )
    assert runtime_issuance.read_runtime_issuance(host=host, reference="absent").unwrap() is None
    path = local_record_path(
        state_dir=host.state_dir, family="issuance", identity=(issued.reference,)
    ).unwrap()
    assert isinstance(
        write_local_record(
            path=path, value=issuance_object(issuance=issued), owner_uid=host.owner_uid
        ),
        Success,
    )
    loaded = runtime_issuance.read_runtime_issuance(host=host, reference=issued.reference).unwrap()
    assert loaded is not None
    assert loaded.reference == issued.reference
    for name in ("local_record_path", "read_local_record"):
        with monkeypatch.context() as context:
            context.setattr(runtime_issuance, name, _store_failure)
            assert isinstance(
                runtime_issuance.read_runtime_issuance(host=host, reference=issued.reference),
                Failure,
            )


def test_target_runtime_refuses_malformed_or_ambiguous_issuances(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_composed(tmp_path=tmp_path)
    from overseer import _lpm_runtime_issuance as runtime_issuance
    from overseer._lpm_localstate import write_local_record
    from overseer._lpm_paths import local_record_path
    from overseer._lpm_target import TargetIssuance, issuance_object

    host = _host(state_dir=tmp_path / "scan")
    assert runtime_issuance.issuance_for_run(host=host, consumer_run_id="absent").unwrap() is None
    directory = host.state_dir / "issuances"
    directory.mkdir(parents=True)
    directory.chmod(0o700)
    malformed = directory / "malformed.json"
    _ = malformed.write_text("{}", encoding="utf-8")
    malformed.chmod(0o600)
    assert isinstance(
        runtime_issuance.issuance_for_run(host=host, consumer_run_id="run-a"), Failure
    )
    malformed.unlink()
    for suffix, run_id in (("a", "run-a"), ("b", "run-a"), ("c", "run-other")):
        issued = TargetIssuance(
            reference=f"reference-{suffix}",
            consumer_run_id=run_id,
            adapter="isolated-run",
            destination=f"destination-{suffix}",
            issued_at=_NOW,
            expires_at="2026-10-11T12:00:00Z",
        )
        path = local_record_path(
            state_dir=host.state_dir, family="issuance", identity=(issued.reference,)
        ).unwrap()
        _ = write_local_record(
            path=path, value=issuance_object(issuance=issued), owner_uid=host.owner_uid
        ).unwrap()
    assert isinstance(
        runtime_issuance.issuance_for_run(host=host, consumer_run_id="run-a"), Failure
    )
    with monkeypatch.context() as context:
        context.setattr(Path, "iterdir", Mock(side_effect=OSError()))
        assert isinstance(
            runtime_issuance.issuance_for_run(host=host, consumer_run_id="run-a"), Failure
        )
    with monkeypatch.context() as context:
        context.setattr(
            runtime_issuance,
            "read_local_record",
            _store_failure,
        )
        assert isinstance(
            runtime_issuance.issuance_for_run(host=host, consumer_run_id="run-a"), Failure
        )
    with monkeypatch.context() as context:
        context.setattr(runtime_issuance, "read_local_record", _none_success)
        assert (
            runtime_issuance.issuance_for_run(host=host, consumer_run_id="run-a").unwrap() is None
        )


def test_target_runtime_propagates_every_composition_failure(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _assert_composed(tmp_path=tmp_path)
    import overseer._lpm_runtime_target as target_runtime

    failure_vectors = (
        "run_lock",
        "idempotency_key_for",
        "pending_operation",
        "issuance_for_run",
        "new_operation",
        "write_new_operation",
        "drive_operation",
    )
    for name in failure_vectors:
        with monkeypatch.context() as context:
            context.setattr(target_runtime, name, _store_failure)
            assert isinstance(
                target_runtime.run_target(
                    host=_host(state_dir=tmp_path / f"failure-{name}"),
                    normalized_input=_request(run_id=f"run-{name}"),
                ),
                Failure,
            )
    for label, replacement in (("failure", _store_failure), ("missing", _none_success)):
        with monkeypatch.context() as context:
            context.setattr(target_runtime, "read_runtime_issuance", replacement)
            outcome = target_runtime.run_target(
                host=_host(state_dir=tmp_path / f"read-{label}"),
                normalized_input=_request(run_id=f"run-read-{label}"),
            )
            assert isinstance(outcome, Failure)
