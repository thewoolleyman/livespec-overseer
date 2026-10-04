"""A `provision` operation walks `start` → `postcommit` → removal through the engine.

SPECIFICATION/contracts.md fixes both arrays and the transition between them: "Provision
`start` MUST contain exactly `lease-create`, `prepared-assignment-create`, `target-write`;
`postcommit` MUST contain exactly `assignment-commit`, `selection-update`, `proof-update`",
"Provision `start` MUST transition to `postcommit` after a committed target", and
"`assignment-commit` MUST record the adapter-supplied target commit time and change `status`
to `committed`".

THE PHASE REPLACEMENT IS ASSERTED, NOT ASSUMED. After `start` the durable record must stand at
`postcommit` carrying THAT phase's complete array with `completed_step` back at `-1`, and the
five identity and input members — including `accepted_at` — must be byte-identical to the ones
`start` was accepted under. Those five are what make a retry resolve the same path and the
same tombstone times; a replacement that re-derived any of them would be a new operation
wearing an old one's name.

THE ADAPTER'S COMMIT INSTANT CROSSES THAT BOUNDARY ON DISK, which is the thing the slice
exists to make survivable. `target-write` persists it; `assignment-commit` runs in the NEXT
phase, reads it back, and writes it into the assignment. The test asserts the assignment's
`target_committed_at` equals the fence sample the caller handed `start` — not a fresh reading
— because a re-sampled instant would move the lease window, the rollout-start minimum and
every later close time with it.

`cleanup` IS DRIVEN ON ITS OWN BECAUSE IT IS THE OTHER TRANSITION. A pre-commit failure routes
`start` to `cleanup`, whose array depends on whether prepared state exists; the test drives the
two-effect form, asserts the prepared assignment is gone and the lease released, and asserts
the operation record is REMOVED rather than rewritten.
"""

from __future__ import annotations

import importlib
import os
import pathlib

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_OPERATION_ID = "2c5f39cb-3fb2-4e4c-b3f1-c5b2e3d4f506"
_KEY = "d" * 64
_ACCEPTED_AT = "2026-10-02T11:00:00Z"
_FENCE_NOW = "2026-10-02T11:00:05Z"
_RUN_ID = "run-provision-one"
_TARGET_REF = "ref-provision-3a9d"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_ACCOUNT = "acct-primary"
_LEASE_SECONDS = 3600
_LEASE_EXPIRES_AT = "2026-10-02T12:00:00Z"
_VALUE = b"sk-ant-oat0-exercise"


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _provision_input() -> dict[str, object]:
    return {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "consumer_run_id": _RUN_ID,
        "target_ref": _TARGET_REF,
        "strategy": "consume-first",
        "lease_seconds": _LEASE_SECONDS,
    }


def _operation(*, phase: str, effects: tuple[str, ...]):
    return _module("_lpm_operation").OperationRecord(
        operation_id=_OPERATION_ID,
        command="provision",
        phase=phase,
        idempotency_key=_KEY,
        accepted_at=_ACCEPTED_AT,
        normalized_input=_provision_input(),
        terminal_result=None,
        ordered_effects=effects,
        completed_step=-1,
    )


def _state(*, tmp_path: pathlib.Path) -> pathlib.Path:
    state_dir = tmp_path / "manager-state"
    state_dir.mkdir(mode=0o700)
    return state_dir


def _engine(*, state_dir: pathlib.Path):
    return _module("_lpm_engine_context").OperationEngine(
        state_dir=state_dir,
        owner_uid=os.getuid(),
        store=_module("_lpm_store").InMemorySecretStore(),
    )


def _inputs(*, tmp_path: pathlib.Path):
    context_module = _module("_lpm_engine_context")
    target_module = _module("_lpm_target")
    return context_module.EffectInputs(
        provision=context_module.ProvisionInputs(
            selected=context_module.SelectedCredential(
                account_id=_ACCOUNT,
                record_id=_RECORD_ID,
                value_generation=_GENERATION,
                value_ref=f"op://values/{_GENERATION}/credential",
                receipt={
                    "record_id": _RECORD_ID,
                    "account_id": _ACCOUNT,
                    "purpose": "factory",
                    "validated_at": "2026-10-02T10:00:00Z",
                    "lease_expires_at": _LEASE_EXPIRES_AT,
                },
            ),
            credential_value=_VALUE,
            destination=str(tmp_path / "target" / "credential"),
            lock=target_module.TargetLock(
                path=tmp_path / "target-lock",
                timeout_seconds=1.0,
                monotonic=lambda: 0.0,
                sleep=lambda _seconds: None,
            ),
            fence_now=_FENCE_NOW,
        )
    )


def _family_path(*, state_dir: pathlib.Path, family: str, identity: tuple[str, ...]):
    located = _module("_lpm_paths").local_record_path(
        state_dir=state_dir, family=family, identity=identity
    )
    assert isinstance(located, Success)
    return located.unwrap()


def _persisted(*, state_dir: pathlib.Path, operation):
    store_module = _module("_lpm_operation_store")
    located = store_module.operation_path(
        state_dir=state_dir, command=operation.command, idempotency_key=operation.idempotency_key
    )
    assert isinstance(located, Success)
    written = store_module.write_operation(
        path=located.unwrap(), operation=operation, owner_uid=os.getuid()
    )
    assert isinstance(written, Success), written
    return located.unwrap()


def _read(*, path: pathlib.Path):
    stored = _module("_lpm_localstate").read_local_record(path=path, owner_uid=os.getuid())
    assert isinstance(stored, Success), stored
    return stored.unwrap()


def _started(*, tmp_path: pathlib.Path, state_dir: pathlib.Path):
    plan = _module("_lpm_operation_plan")
    operation = _operation(
        phase="start", effects=("lease-create", "prepared-assignment-create", "target-write")
    )
    _ = _persisted(state_dir=state_dir, operation=operation)
    return _module("_lpm_engine").drive_operation(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_inputs(tmp_path=tmp_path),
        condition="target-committed",
        context=plan.PlanContext(),
        terminal_result=None,
    )


def test_a_committed_start_phase_becomes_postcommit_with_the_same_identity(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)

    replaced = _started(tmp_path=tmp_path, state_dir=state_dir)

    assert isinstance(replaced, Success), replaced
    following = replaced.unwrap()
    assert following is not None
    assert following.phase == "postcommit"
    assert following.ordered_effects == ("assignment-commit", "selection-update", "proof-update")
    assert following.completed_step == -1
    assert following.operation_id == _OPERATION_ID
    assert following.accepted_at == _ACCEPTED_AT
    assert following.idempotency_key == _KEY
    assert following.normalized_input == _provision_input()


def test_the_start_phase_leases_prepares_and_commits_the_target_once(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)

    replaced = _started(tmp_path=tmp_path, state_dir=state_dir)

    assert isinstance(replaced, Success), replaced
    assert _read(
        path=_family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT))
    ) == {
        "version": 1,
        "provider": "anthropic",
        "account_id": _ACCOUNT,
        "record_id": _RECORD_ID,
        "consumer_run_id": _RUN_ID,
        "lease_started_at": _ACCEPTED_AT,
        "lease_expires_at": _LEASE_EXPIRES_AT,
    }
    assert _read(
        path=_family_path(state_dir=state_dir, family="target-commit", identity=(_TARGET_REF,))
    ) == {
        "version": 1,
        "target_ref": _TARGET_REF,
        "consumer_run_id": _RUN_ID,
        "record_id": _RECORD_ID,
        "value_generation": _GENERATION,
        "committed_at": _FENCE_NOW,
    }
    assert pathlib.Path(str(tmp_path / "target" / "credential")).read_bytes() == _VALUE
    prepared = _read(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    )
    assert isinstance(prepared, dict)
    assert prepared["status"] == "prepared"
    assert prepared["target_committed_at"] is None


def test_the_postcommit_phase_commits_the_assignment_and_merges_both_shared_records(
    tmp_path: pathlib.Path,
) -> None:
    paths = _module("_lpm_paths")
    state_dir = _state(tmp_path=tmp_path)
    started = _started(tmp_path=tmp_path, state_dir=state_dir)
    assert isinstance(started, Success), started
    following = started.unwrap()
    assert following is not None

    finished = _module("_lpm_engine").drive_operation(
        engine=_engine(state_dir=state_dir),
        operation=following,
        inputs=_inputs(tmp_path=tmp_path),
        condition="every-effect-committed",
        context=_module("_lpm_operation_plan").PlanContext(),
        terminal_result=None,
    )

    assert isinstance(finished, Success), finished
    assert finished.unwrap() is None
    assert not _family_path(
        state_dir=state_dir, family="operation", identity=("provision", _KEY)
    ).exists()
    committed = _read(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    )
    assert isinstance(committed, dict)
    assert committed["status"] == "committed"
    assert committed["target_committed_at"] == _FENCE_NOW
    assert _read(path=state_dir / paths.SELECTION_STATE_NAME) == {
        "version": 1,
        "incumbents": [
            {
                "provider": "anthropic",
                "kind": "claude-code-oauth",
                "purpose": "factory",
                "record_id": _RECORD_ID,
                "target_committed_at": _FENCE_NOW,
            }
        ],
        "last_assignments": [{"record_id": _RECORD_ID, "assigned_at": _FENCE_NOW}],
    }
    proof = _read(path=state_dir / paths.PROOF_RECORD_NAME)
    assert isinstance(proof, dict)
    assert proof["rollout_started_at"] == _FENCE_NOW


def test_re_driving_postcommit_settles_every_position_without_rewriting_a_record(
    tmp_path: pathlib.Path,
) -> None:
    paths = _module("_lpm_paths")
    engine_module = _module("_lpm_engine")
    state_dir = _state(tmp_path=tmp_path)
    started = _started(tmp_path=tmp_path, state_dir=state_dir)
    assert isinstance(started, Success), started
    following = started.unwrap()
    assert following is not None
    first = engine_module.drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=following,
        inputs=_inputs(tmp_path=tmp_path),
    )
    assert isinstance(first, Success), first
    assert first.unwrap().performed == (0, 1, 2)
    selection_bytes = (state_dir / paths.SELECTION_STATE_NAME).read_bytes()
    proof_bytes = (state_dir / paths.PROOF_RECORD_NAME).read_bytes()

    replay = engine_module.drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=following,
        inputs=_inputs(tmp_path=tmp_path),
    )

    assert isinstance(replay, Success), replay
    assert replay.unwrap().performed == ()
    assert replay.unwrap().skipped == (0, 1, 2)
    assert (state_dir / paths.SELECTION_STATE_NAME).read_bytes() == selection_bytes
    assert (state_dir / paths.PROOF_RECORD_NAME).read_bytes() == proof_bytes


def test_cleanup_discards_the_prepared_assignment_and_releases_the_lease(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    engine_module = _module("_lpm_engine")
    start = _operation(
        phase="start", effects=("lease-create", "prepared-assignment-create", "target-write")
    )
    _ = _persisted(state_dir=state_dir, operation=start)
    driven = engine_module.drive_phase(
        engine=_engine(state_dir=state_dir), operation=start, inputs=_inputs(tmp_path=tmp_path)
    )
    assert isinstance(driven, Success), driven
    cleanup = _operation(phase="cleanup", effects=("prepared-assignment-discard", "lease-release"))
    _ = _persisted(state_dir=state_dir, operation=cleanup)

    finished = engine_module.drive_operation(
        engine=_engine(state_dir=state_dir),
        operation=cleanup,
        inputs=_inputs(tmp_path=tmp_path),
        condition="every-effect-committed",
        context=_module("_lpm_operation_plan").PlanContext(prepared_state_exists=True),
        terminal_result=None,
    )

    assert isinstance(finished, Success), finished
    assert finished.unwrap() is None
    assert not _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)).exists()
    assert not _family_path(
        state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT)
    ).exists()


def test_a_second_runs_live_lease_on_the_same_account_is_retryable_exhaustion(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    lease_path = _family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT))
    seeded = _module("_lpm_localstate").write_local_record(
        path=lease_path,
        value={
            "version": 1,
            "provider": "anthropic",
            "account_id": _ACCOUNT,
            "record_id": _RECORD_ID,
            "consumer_run_id": "run-somebody-else",
            "lease_started_at": _ACCEPTED_AT,
            "lease_expires_at": _LEASE_EXPIRES_AT,
        },
        owner_uid=os.getuid(),
    )
    assert isinstance(seeded, Success), seeded
    untouched = lease_path.read_bytes()
    start = _operation(
        phase="start", effects=("lease-create", "prepared-assignment-create", "target-write")
    )
    _ = _persisted(state_dir=state_dir, operation=start)

    driven = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir), operation=start, inputs=_inputs(tmp_path=tmp_path)
    )

    assert isinstance(driven, Failure)
    assert driven.failure().error_type == "retryable-exhaustion"
    assert lease_path.read_bytes() == untouched


def test_an_expired_lease_from_a_crashed_run_is_replaced(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    lease_path = _family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT))
    seeded = _module("_lpm_localstate").write_local_record(
        path=lease_path,
        value={
            "version": 1,
            "provider": "anthropic",
            "account_id": _ACCOUNT,
            "record_id": _RECORD_ID,
            "consumer_run_id": "run-crashed",
            "lease_started_at": "2026-10-01T00:00:00Z",
            "lease_expires_at": "2026-10-01T01:00:00Z",
        },
        owner_uid=os.getuid(),
    )
    assert isinstance(seeded, Success), seeded
    start = _operation(
        phase="start", effects=("lease-create", "prepared-assignment-create", "target-write")
    )
    _ = _persisted(state_dir=state_dir, operation=start)

    driven = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir), operation=start, inputs=_inputs(tmp_path=tmp_path)
    )

    assert isinstance(driven, Success), driven
    standing = _read(path=lease_path)
    assert isinstance(standing, dict)
    assert standing["consumer_run_id"] == _RUN_ID
    assert standing["lease_started_at"] == _ACCEPTED_AT


def test_cleanup_never_discards_a_committed_assignment(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    started = _started(tmp_path=tmp_path, state_dir=state_dir)
    assert isinstance(started, Success), started
    following = started.unwrap()
    assert following is not None
    committed = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=following,
        inputs=_inputs(tmp_path=tmp_path),
    )
    assert isinstance(committed, Success), committed
    cleanup = _operation(phase="cleanup", effects=("prepared-assignment-discard", "lease-release"))
    _ = _persisted(state_dir=state_dir, operation=cleanup)
    assignment_path = _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    untouched = assignment_path.read_bytes()

    driven = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir), operation=cleanup, inputs=_inputs(tmp_path=tmp_path)
    )

    assert isinstance(driven, Failure)
    assert driven.failure().error_type == "store-unavailable"
    assert "never discarded by cleanup" in driven.failure().message
    assert assignment_path.read_bytes() == untouched
