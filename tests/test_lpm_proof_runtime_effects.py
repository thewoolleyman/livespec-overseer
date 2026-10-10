"""Runtime proof effects retain concurrent and replayed coexistence evidence.

These tests drive the public durable-operation engine with synthetic assignments, reports and
completions.  They do not represent production observation or deprecation-readiness evidence.
"""

from __future__ import annotations

import fcntl
import importlib
import os
import pathlib
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_RECORD_A = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_RECORD_B = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_RECORD_C = "9b2c4d6e-8f10-4a3b-9c5d-7e1f2a3b4c5d"
_RECORD_EARLY = "1b2c3d4e-5f60-4789-8abc-def012345678"
_RECORD_OLD = "12345678-1234-4abc-8def-1234567890ab"
_RECORD_PREPARED = "87654321-4321-4cba-8fed-ba0987654321"
_GENERATION = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"
_COMPLETE_EFFECTS = (
    "proof-update",
    "completion-update",
    "assignment-end-update",
    "lease-release",
    "tombstone-create",
    "assignment-close",
)
_PROVISION_EFFECTS = ("assignment-commit", "selection-update", "proof-update")


@dataclass(frozen=True, kw_only=True)
class _Binding:
    run_id: str
    record_id: str
    account_id: str
    committed_at: str
    strategy: str = "spread"


_BINDINGS = (
    _Binding(
        run_id="run-a",
        record_id=_RECORD_A,
        account_id="account-a",
        committed_at="2026-10-01T10:01:00Z",
    ),
    _Binding(
        run_id="run-b",
        record_id=_RECORD_B,
        account_id="account-b",
        committed_at="2026-10-01T10:02:00Z",
    ),
    _Binding(
        run_id="run-c",
        record_id=_RECORD_C,
        account_id="account-c",
        committed_at="2026-10-01T10:02:00Z",
    ),
    _Binding(
        run_id="run-early",
        record_id=_RECORD_EARLY,
        account_id="account-early",
        committed_at="2026-10-01T09:59:00Z",
        strategy="consume-first",
    ),
)


def _module(*, name: str):
    return importlib.import_module(name)


def _state(*, tmp_path: pathlib.Path) -> pathlib.Path:
    state_dir = tmp_path / "manager-state"
    state_dir.mkdir(mode=0o700, parents=True)
    return state_dir


def _path(*, state_dir: pathlib.Path, family: str, identity: tuple[str, ...]) -> pathlib.Path:
    return (
        _module(name="_lpm_paths")
        .local_record_path(state_dir=state_dir, family=family, identity=identity)
        .unwrap()
    )


def _seed(*, path: pathlib.Path, value: object) -> None:
    written = _module(name="_lpm_localstate").write_local_record(
        path=path, value=value, owner_uid=os.getuid()
    )
    assert isinstance(written, Success), written


def _request(
    *, run_id: str, strategy: str = "spread", target_ref: str | None = None
) -> dict[str, object]:
    return {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "consumer_run_id": run_id,
        "target_ref": target_ref or f"ref-{run_id}",
        "strategy": strategy,
        "lease_seconds": 7200,
    }


def _assignment(
    *,
    binding: _Binding,
    lease_started_at: str = "2026-10-01T09:00:00Z",
    lease_expires_at: str = "2026-10-08T09:00:00Z",
    completion: dict[str, object] | None = None,
) -> dict[str, object]:
    request = _request(run_id=binding.run_id, strategy=binding.strategy)
    return {
        "version": 1,
        "status": "committed",
        "request": request,
        "target_ref": request["target_ref"],
        "account_id": binding.account_id,
        "value_generation": _GENERATION,
        "value_ref": f"op://tokens/{binding.record_id}/credential",
        "record_id": binding.record_id,
        "receipt": {
            "record_id": binding.record_id,
            "account_id": binding.account_id,
            "purpose": "factory",
            "validated_at": "2026-10-01T08:30:00Z",
            "lease_expires_at": lease_expires_at,
        },
        "lease_started_at": lease_started_at,
        "lease_expires_at": lease_expires_at,
        "target_committed_at": binding.committed_at,
        "actual_lease_ended_at": None,
        "report_markers": [],
        "completion": completion,
    }


def _prepared(*, binding: _Binding) -> dict[str, object]:
    return {
        **_assignment(binding=binding),
        "status": "prepared",
        "target_committed_at": None,
    }


def _tombstone(*, binding: _Binding) -> dict[str, object]:
    source = _assignment(binding=binding)
    del source["status"]
    del source["receipt"]
    source["actual_lease_ended_at"] = "2026-10-07T12:00:00Z"
    source["closed_at"] = "2026-10-07T12:00:00Z"
    return source


def _lease(*, run_id: str, record_id: str, account_id: str) -> dict[str, object]:
    return {
        "version": 1,
        "provider": "anthropic",
        "account_id": account_id,
        "record_id": record_id,
        "consumer_run_id": run_id,
        "lease_started_at": "2026-10-01T09:00:00Z",
        "lease_expires_at": "2026-10-08T09:00:00Z",
    }


def _completion(*, run_id: str, record_id: str, completed_at: str) -> dict[str, object]:
    return {
        "version": 1,
        "consumer_run_id": run_id,
        "record_id": record_id,
        "completed_at": completed_at,
        "consumer_class": "production",
        "provider_authenticated": True,
        "alternate_credential_used": False,
        "legacy_pool_absent": False,
    }


def _operation(
    *,
    ordinal: int,
    command: str,
    normalized_input: dict[str, object],
    effects: tuple[str, ...],
    completed_step: int,
) -> object:
    return _module(name="_lpm_operation").OperationRecord(
        operation_id=f"00000000-0000-4000-8000-{ordinal:012d}",
        command=command,
        phase="postcommit" if command == "provision" else "apply",
        idempotency_key=f"{ordinal:064x}",
        accepted_at="2026-10-07T13:00:00Z",
        normalized_input=normalized_input,
        terminal_result=None,
        ordered_effects=effects,
        completed_step=completed_step,
    )


def _persist_operation(*, state_dir: pathlib.Path, operation: object) -> None:
    store = _module(name="_lpm_operation_store")
    path = store.operation_path(
        state_dir=state_dir,
        command=operation.command,
        idempotency_key=operation.idempotency_key,
    ).unwrap()
    written = store.write_operation(path=path, operation=operation, owner_uid=os.getuid())
    assert isinstance(written, Success), written


def _engine(*, state_dir: pathlib.Path, lock_timeout_seconds: float = 30.0) -> object:
    return _module(name="_lpm_engine_context").OperationEngine(
        state_dir=state_dir,
        owner_uid=os.getuid(),
        store=_module(name="_lpm_store").InMemorySecretStore(),
        lock_timeout_seconds=lock_timeout_seconds,
    )


def _drive(*, state_dir: pathlib.Path, operation: object) -> object:
    return _module(name="_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_module(name="_lpm_engine_context").EffectInputs(),
    )


def _proof(*, state_dir: pathlib.Path) -> object:
    return (
        _module(name="_lpm_proof")
        .read_proof_record(path=state_dir / "coexistence-proof.json", owner_uid=os.getuid())
        .unwrap()
    )


def _seed_binding(*, state_dir: pathlib.Path, binding: _Binding) -> None:
    _seed(
        path=_path(state_dir=state_dir, family="assignment", identity=(binding.run_id,)),
        value=_assignment(binding=binding),
    )
    _seed(
        path=_path(
            state_dir=state_dir,
            family="lease",
            identity=("anthropic", binding.account_id),
        ),
        value=_lease(
            run_id=binding.run_id,
            record_id=binding.record_id,
            account_id=binding.account_id,
        ),
    )


def _establish_rollout_and_pair(*, state_dir: pathlib.Path) -> None:
    for binding in _BINDINGS:
        _seed_binding(state_dir=state_dir, binding=binding)
    peer = _BINDINGS[1]
    _seed(
        path=_path(state_dir=state_dir, family="tombstone", identity=(peer.run_id,)),
        value=_tombstone(binding=peer),
    )
    prepared = _Binding(
        run_id="run-prepared",
        record_id=_RECORD_PREPARED,
        account_id="account-prepared",
        committed_at="2026-10-01T10:00:30Z",
    )
    old = _Binding(
        run_id="run-old",
        record_id=_RECORD_OLD,
        account_id="account-old",
        committed_at="2026-10-01T10:00:00Z",
    )
    _seed(
        path=_path(state_dir=state_dir, family="assignment", identity=(prepared.run_id,)),
        value=_prepared(binding=prepared),
    )
    _seed_binding(state_dir=state_dir, binding=old)
    operations = (
        _operation(
            ordinal=1,
            command="provision",
            normalized_input=_request(run_id="run-a"),
            effects=_PROVISION_EFFECTS,
            completed_step=1,
        ),
        _operation(
            ordinal=2,
            command="provision",
            normalized_input=_request(run_id="run-early", strategy="consume-first"),
            effects=_PROVISION_EFFECTS,
            completed_step=1,
        ),
    )
    for operation in operations:
        _persist_operation(state_dir=state_dir, operation=operation)
        assert isinstance(_drive(state_dir=state_dir, operation=operation), Success)


def _completion_operations(*, state_dir: pathlib.Path) -> tuple[object, object]:
    operations = (
        _operation(
            ordinal=3,
            command="complete",
            normalized_input=_completion(
                run_id="run-a", record_id=_RECORD_A, completed_at="2026-10-03T12:00:00Z"
            ),
            effects=_COMPLETE_EFFECTS,
            completed_step=-1,
        ),
        _operation(
            ordinal=4,
            command="complete",
            normalized_input=_completion(
                run_id="run-c", record_id=_RECORD_C, completed_at="2026-10-02T12:00:00Z"
            ),
            effects=_COMPLETE_EFFECTS,
            completed_step=-1,
        ),
    )
    for operation in operations:
        _persist_operation(state_dir=state_dir, operation=operation)
    return operations


def _synchronized_reader(*, proof_effect: object, state_dir: pathlib.Path):
    read_barrier = threading.Barrier(2)
    original_read = proof_effect.read_proof_record
    lock_path = state_dir / "locks" / "coexistence-proof.lock"

    def synchronized_read(*, path: pathlib.Path, owner_uid: int):
        if path != state_dir / "coexistence-proof.json":
            return original_read(path=path, owner_uid=owner_uid)
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        product_lock_is_held = False
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                product_lock_is_held = True
            else:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
        if not product_lock_is_held:
            read_barrier.wait(timeout=2)
        return original_read(path=path, owner_uid=owner_uid)

    return synchronized_read


def _assert_shared_proof(*, state_dir: pathlib.Path) -> None:
    proof = _proof(state_dir=state_dir)
    assert proof.rollout_started_at == "2026-10-01T09:59:00Z"
    assert proof.simultaneous_spread == {
        "first_consumer_run_id": "run-a",
        "first_account_id": "account-a",
        "second_consumer_run_id": "run-b",
        "second_account_id": "account-b",
        "overlap_started_at": "2026-10-01T09:00:00Z",
        "overlap_ended_at": "2026-10-01T10:02:00Z",
    }
    assert [
        (marker.consumer_run_id, marker.record_id, marker.completed_at)
        for marker in proof.completion_markers
    ] == [
        ("run-c", _RECORD_C, "2026-10-02T12:00:00Z"),
        ("run-a", _RECORD_A, "2026-10-03T12:00:00Z"),
    ]


def _assert_single_spread_has_no_pair(*, tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path / "single")
    binding = _Binding(
        run_id="run-single",
        record_id=_RECORD_A,
        account_id="account-single",
        committed_at="2026-10-01T10:01:00Z",
    )
    _seed_binding(state_dir=state_dir, binding=binding)
    operation = _operation(
        ordinal=11,
        command="provision",
        normalized_input=_request(run_id=binding.run_id),
        effects=_PROVISION_EFFECTS,
        completed_step=1,
    )
    _persist_operation(state_dir=state_dir, operation=operation)

    outcome = _drive(state_dir=state_dir, operation=operation)

    assert isinstance(outcome, Success), outcome
    assert _proof(state_dir=state_dir).simultaneous_spread is None

    consume_state = _state(tmp_path=tmp_path / "consume-first")
    consume_binding = _Binding(
        run_id="run-consume-first",
        record_id=_RECORD_B,
        account_id="account-consume-first",
        committed_at="2026-10-01T10:02:00Z",
        strategy="consume-first",
    )
    _seed_binding(state_dir=consume_state, binding=consume_binding)
    consume_operation = _operation(
        ordinal=12,
        command="provision",
        normalized_input=_request(run_id=consume_binding.run_id, strategy="consume-first"),
        effects=_PROVISION_EFFECTS,
        completed_step=1,
    )
    _persist_operation(state_dir=consume_state, operation=consume_operation)

    consume_outcome = _drive(state_dir=consume_state, operation=consume_operation)

    assert isinstance(consume_outcome, Success), consume_outcome
    assert _proof(state_dir=consume_state).simultaneous_spread is None


def _peer_defect(*, state_dir: pathlib.Path, mode: str) -> None:
    if mode == "directory":
        (state_dir / "assignments").chmod(0o755)
        return
    peer = _Binding(
        run_id=f"run-{mode}-peer",
        record_id=_RECORD_B,
        account_id=f"account-{mode}-peer",
        committed_at="2026-10-01T10:02:00Z",
    )
    path = state_dir / "assignments" / f"{mode}.json"
    _seed(path=path, value={"version": 1} if mode == "malformed" else _assignment(binding=peer))
    if mode == "permissions":
        path.chmod(0o644)


def _assert_unsafe_peers_refuse(*, tmp_path: pathlib.Path) -> None:
    for ordinal, mode in enumerate(("directory", "permissions", "malformed"), start=13):
        state_dir = _state(tmp_path=tmp_path / mode)
        binding = _Binding(
            run_id=f"run-{mode}-current",
            record_id=_RECORD_A,
            account_id=f"account-{mode}-current",
            committed_at="2026-10-01T10:01:00Z",
        )
        _seed_binding(state_dir=state_dir, binding=binding)
        _peer_defect(state_dir=state_dir, mode=mode)
        operation = _operation(
            ordinal=ordinal,
            command="provision",
            normalized_input=_request(run_id=binding.run_id),
            effects=_PROVISION_EFFECTS,
            completed_step=1,
        )
        _persist_operation(state_dir=state_dir, operation=operation)

        refused = _drive(state_dir=state_dir, operation=operation)

        assert isinstance(refused, Failure), refused
        assert refused.failure().error_type == "store-unavailable"
        assert not (state_dir / "coexistence-proof.json").exists()


def _assert_unsafe_binding_refuses(*, tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path / "unsafe-binding")
    binding = _Binding(
        run_id="run-unsafe-binding",
        record_id=_RECORD_A,
        account_id="account-unsafe-binding",
        committed_at="2026-10-01T10:01:00Z",
    )
    _seed_binding(state_dir=state_dir, binding=binding)
    _path(state_dir=state_dir, family="assignment", identity=(binding.run_id,)).chmod(0o644)
    operation = _operation(
        ordinal=16,
        command="provision",
        normalized_input=_request(run_id=binding.run_id),
        effects=_PROVISION_EFFECTS,
        completed_step=1,
    )
    _persist_operation(state_dir=state_dir, operation=operation)

    refused = _drive(state_dir=state_dir, operation=operation)

    assert isinstance(refused, Failure), refused
    assert refused.failure().error_type == "store-unavailable"
    assert not (state_dir / "coexistence-proof.json").exists()


def _assert_lock_timeout_preserves_state(*, tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path / "contended")
    binding = _Binding(
        run_id="run-contended",
        record_id=_RECORD_A,
        account_id="account-contended",
        committed_at="2026-10-01T10:01:00Z",
    )
    _seed_binding(state_dir=state_dir, binding=binding)
    operation = _operation(
        ordinal=17,
        command="provision",
        normalized_input=_request(run_id=binding.run_id),
        effects=_PROVISION_EFFECTS,
        completed_step=1,
    )
    _persist_operation(state_dir=state_dir, operation=operation)
    locks = _module(name="_lpm_locks")
    held = locks.take_lock(
        path=state_dir / "locks" / "coexistence-proof.lock",
        owner_uid=os.getuid(),
        timeout_seconds=1.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    ).unwrap()
    try:
        refused = _module(name="_lpm_engine").drive_phase(
            engine=_engine(state_dir=state_dir, lock_timeout_seconds=0.0),
            operation=operation,
            inputs=_module(name="_lpm_engine_context").EffectInputs(),
        )
    finally:
        locks.release_lock(held=held)

    assert isinstance(refused, Failure), refused
    assert "held past the wait budget" in refused.failure().message
    assert not (state_dir / "coexistence-proof.json").exists()


def _assert_failed_atomic_write_preserves_state(
    *, tmp_path: pathlib.Path, monkeypatch, proof_effect: object
) -> None:
    state_dir = _state(tmp_path=tmp_path / "write-failure")
    binding = _Binding(
        run_id="run-write-failure",
        record_id=_RECORD_A,
        account_id="account-write-failure",
        committed_at="2026-10-01T10:01:00Z",
    )
    _seed_binding(state_dir=state_dir, binding=binding)
    operation = _operation(
        ordinal=18,
        command="provision",
        normalized_input=_request(run_id=binding.run_id),
        effects=_PROVISION_EFFECTS,
        completed_step=1,
    )
    _persist_operation(state_dir=state_dir, operation=operation)
    error = _module(name="_lpm_results").store_unavailable(message="injected write refusal")
    monkeypatch.setattr(
        proof_effect,
        "write_local_record",
        lambda **_kwargs: Failure(error),
    )

    refused = _drive(state_dir=state_dir, operation=operation)

    assert isinstance(refused, Failure), refused
    assert refused.failure() == error
    assert not (state_dir / "coexistence-proof.json").exists()


def _assert_downstream_completion_refusals(*, tmp_path: pathlib.Path) -> None:
    missing_state = _state(tmp_path=tmp_path / "missing-completion-binding")
    missing = _operation(
        ordinal=19,
        command="complete",
        normalized_input=_completion(
            run_id="run-missing", record_id=_RECORD_A, completed_at="2026-10-03T12:00:00Z"
        ),
        effects=_COMPLETE_EFFECTS,
        completed_step=0,
    )
    _persist_operation(state_dir=missing_state, operation=missing)

    missing_refusal = _drive(state_dir=missing_state, operation=missing)

    assert isinstance(missing_refusal, Failure), missing_refusal

    conflict_state = _state(tmp_path=tmp_path / "conflicting-completion")
    binding = _Binding(
        run_id="run-conflicting-completion",
        record_id=_RECORD_B,
        account_id="account-conflicting-completion",
        committed_at="2026-10-01T10:02:00Z",
    )
    existing = _completion(
        run_id=binding.run_id,
        record_id=binding.record_id,
        completed_at="2026-10-02T12:00:00Z",
    )
    _seed(
        path=_path(state_dir=conflict_state, family="assignment", identity=(binding.run_id,)),
        value=_assignment(binding=binding, completion=existing),
    )
    conflict = _operation(
        ordinal=20,
        command="complete",
        normalized_input=_completion(
            run_id=binding.run_id,
            record_id=binding.record_id,
            completed_at="2026-10-03T12:00:00Z",
        ),
        effects=_COMPLETE_EFFECTS,
        completed_step=0,
    )
    _persist_operation(state_dir=conflict_state, operation=conflict)

    conflict_refusal = _drive(state_dir=conflict_state, operation=conflict)

    assert isinstance(conflict_refusal, Failure), conflict_refusal
    assert "different completion" in conflict_refusal.failure().message


def test_concurrent_public_engine_contributions_retain_the_complete_shared_proof(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_proof_effect.py"
    assert module_path.is_file(), "overseer/_lpm_proof_effect.py must exist"
    proof_effect = importlib.import_module("_lpm_proof_effect")
    state_dir = _state(tmp_path=tmp_path)
    _establish_rollout_and_pair(state_dir=state_dir)
    complete_a, complete_c = _completion_operations(state_dir=state_dir)
    monkeypatch.setattr(
        proof_effect,
        "read_proof_record",
        _synchronized_reader(proof_effect=proof_effect, state_dir=state_dir),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(
            executor.map(
                lambda operation: _drive(state_dir=state_dir, operation=operation),
                (complete_a, complete_c),
            )
        )

    assert all(isinstance(outcome, Success) for outcome in outcomes), outcomes
    _assert_shared_proof(state_dir=state_dir)
    _assert_single_spread_has_no_pair(tmp_path=tmp_path)
    _assert_unsafe_peers_refuse(tmp_path=tmp_path)
    _assert_unsafe_binding_refuses(tmp_path=tmp_path)
    _assert_lock_timeout_preserves_state(tmp_path=tmp_path)
    _assert_failed_atomic_write_preserves_state(
        tmp_path=tmp_path, monkeypatch=monkeypatch, proof_effect=proof_effect
    )
    _assert_downstream_completion_refusals(tmp_path=tmp_path)
