"""A `target` command's `issue` phase runs through the PUBLIC engine, and only once.

SPECIFICATION/contracts.md states the array exactly — "Target `issue` MUST contain exactly
`issuance-create`, `registration-remove`" — and requires every executor to inspect that
POSITION'S authoritative postcondition before performing it, so that an already-satisfied
postcondition advances `completed_step` without repeating the effect.

THIS DRIVES THE PRODUCTION ENGINE, NOT A TEST-LOCAL REIMPLEMENTATION. `drive_phase` resolves
its executors from the one real effect registry and checkpoints through the real operation
store at the real deterministic path, against real owner-only local state under `tmp_path`.
A test that assembled its own executor table would prove the replay driver works and say
nothing about whether any effect is actually wired to it — which is the gap this slice exists
to close.

RE-DRIVING THE SAME PHASE IS THE IDEMPOTENCE PROOF. The second pass is given the SAME record
at the SAME stale checkpoint the first pass entered on, so every position it inspects has
already committed; it must report both positions `skipped` and leave the issuance's stored
bytes untouched. A name-keyed or write-through executor would either refuse the existing
record or rewrite it with a fresh `issued_at`.

`issued_at` IS ASSERTED AGAINST `accepted_at`, byte for byte. The record retains
`accepted_at` across every retry and phase replacement, so deriving the issuance's times from
it — rather than from a clock read inside the executor — is what keeps a recovered issue
expiring at the instant it first committed.
"""

from __future__ import annotations

import importlib
import os
import pathlib

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_OPERATION_ID = "1b4e28ba-2fa1-4d3b-a2e0-b4a1d2c3e4f5"
_KEY = "a" * 64
_ACCEPTED_AT = "2026-10-02T09:15:00Z"
_EXPIRES_AT = "2026-10-03T09:15:00Z"
_RUN_ID = "run-target-one"
_REFERENCE = "ref-opaque-7f1c"
_ADAPTER = "isolated-run"


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _operation():
    return _module("_lpm_operation").OperationRecord(
        operation_id=_OPERATION_ID,
        command="target",
        phase="issue",
        idempotency_key=_KEY,
        accepted_at=_ACCEPTED_AT,
        normalized_input={"version": 1, "consumer_run_id": _RUN_ID, "adapter": _ADAPTER},
        terminal_result=None,
        ordered_effects=("issuance-create", "registration-remove"),
        completed_step=-1,
    )


def _engine(*, state_dir: pathlib.Path):
    context_module = _module("_lpm_engine_context")
    return context_module.OperationEngine(
        state_dir=state_dir,
        owner_uid=os.getuid(),
        store=_module("_lpm_store").InMemorySecretStore(),
    )


def _inputs(*, destination: str):
    context_module = _module("_lpm_engine_context")
    return context_module.EffectInputs(
        target=context_module.TargetInputs(
            reference=_REFERENCE, adapter=_ADAPTER, destination=destination
        )
    )


def _state(*, tmp_path: pathlib.Path) -> pathlib.Path:
    state_dir = tmp_path / "manager-state"
    state_dir.mkdir(mode=0o700)
    return state_dir


def _family_path(*, state_dir: pathlib.Path, family: str, identity: str) -> pathlib.Path:
    located = _module("_lpm_paths").local_record_path(
        state_dir=state_dir, family=family, identity=(identity,)
    )
    assert isinstance(located, Success)
    return located.unwrap()


def _persisted(*, state_dir: pathlib.Path, operation) -> pathlib.Path:
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


def test_target_issue_performs_both_positions_from_the_operations_own_accepted_at(
    tmp_path: pathlib.Path,
) -> None:
    localstate = _module("_lpm_localstate")
    state_dir = _state(tmp_path=tmp_path)
    owner_uid = os.getuid()
    destination = str(tmp_path / "destination")
    operation = _operation()
    record_path = _persisted(state_dir=state_dir, operation=operation)
    registration = _family_path(state_dir=state_dir, family="run-registration", identity=_RUN_ID)
    seeded = localstate.write_local_record(
        path=registration, value={"version": 1, "consumer_run_id": _RUN_ID}, owner_uid=owner_uid
    )
    assert isinstance(seeded, Success), seeded

    driven = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_inputs(destination=destination),
    )

    assert isinstance(driven, Success), driven
    assert driven.unwrap().performed == (0, 1)
    assert driven.unwrap().skipped == ()
    stored_issuance = localstate.read_local_record(
        path=_family_path(state_dir=state_dir, family="issuance", identity=_REFERENCE),
        owner_uid=owner_uid,
    )
    assert isinstance(stored_issuance, Success)
    assert stored_issuance.unwrap() == {
        "version": 1,
        "reference": _REFERENCE,
        "consumer_run_id": _RUN_ID,
        "adapter": _ADAPTER,
        "destination": destination,
        "issued_at": _ACCEPTED_AT,
        "expires_at": _EXPIRES_AT,
    }
    assert not registration.exists()
    stored_record = _module("_lpm_operation_store").read_operation(
        path=record_path, owner_uid=owner_uid
    )
    assert isinstance(stored_record, Success)
    assert stored_record.unwrap().completed_step == 1


def test_re_driving_a_committed_issue_phase_skips_every_position(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    destination = str(tmp_path / "destination")
    operation = _operation()
    _ = _persisted(state_dir=state_dir, operation=operation)
    engine_module = _module("_lpm_engine")
    first = engine_module.drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_inputs(destination=destination),
    )
    assert isinstance(first, Success), first
    issuance_path = _family_path(state_dir=state_dir, family="issuance", identity=_REFERENCE)
    committed = issuance_path.read_bytes()

    replay = engine_module.drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_inputs(destination=destination),
    )

    assert isinstance(replay, Success), replay
    assert replay.unwrap().performed == ()
    assert replay.unwrap().skipped == (0, 1)
    assert issuance_path.read_bytes() == committed


def test_a_different_issuance_at_the_same_reference_is_left_exactly_as_found(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    operation = _operation()
    _ = _persisted(state_dir=state_dir, operation=operation)
    issuance_path = _family_path(state_dir=state_dir, family="issuance", identity=_REFERENCE)
    seeded = _module("_lpm_localstate").write_local_record(
        path=issuance_path,
        value={
            "version": 1,
            "reference": _REFERENCE,
            "consumer_run_id": "another-run",
            "adapter": _ADAPTER,
            "destination": str(tmp_path / "elsewhere"),
            "issued_at": _ACCEPTED_AT,
            "expires_at": _EXPIRES_AT,
        },
        owner_uid=os.getuid(),
    )
    assert isinstance(seeded, Success), seeded
    untouched = issuance_path.read_bytes()

    driven = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_inputs(destination=str(tmp_path / "destination")),
    )

    assert isinstance(driven, Failure)
    assert driven.failure().error_type == "store-unavailable"
    assert issuance_path.read_bytes() == untouched


def test_an_effect_name_the_registry_does_not_carry_refuses_rather_than_advancing(
    tmp_path: pathlib.Path,
) -> None:
    registry = _module("_lpm_effect_registry")
    context_module = _module("_lpm_engine_context")
    identity = _module("_lpm_operation_identity")
    engine = _engine(state_dir=_state(tmp_path=tmp_path))
    operation = _operation()

    for effect, fragment in (
        ("secret-value-set", "worker-lifecycle engine"),
        ("no-such-effect", "no registered effect executor"),
    ):
        refused = registry.execute_effect(
            context=context_module.EffectContext(
                engine=engine,
                operation=operation,
                inputs=context_module.EffectInputs(),
                position=identity.EffectPosition(index=0, effect=effect, effect_id="b" * 64),
            )
        )
        assert isinstance(refused, Failure), effect
        assert refused.failure().error_type == "internal-bug"
        assert fragment in refused.failure().message


def test_an_issue_phase_composed_without_its_target_inputs_reports_a_bug(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    operation = _operation()
    _ = _persisted(state_dir=state_dir, operation=operation)

    driven = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_module("_lpm_engine_context").EffectInputs(),
    )

    assert isinstance(driven, Failure)
    assert driven.failure().error_type == "internal-bug"
    assert "target inputs" in driven.failure().message


def test_resuming_a_command_with_no_durable_record_refuses(tmp_path: pathlib.Path) -> None:
    resumed = _module("_lpm_engine").resume_phase(
        engine=_engine(state_dir=_state(tmp_path=tmp_path)),
        command="target",
        idempotency_key=_KEY,
        inputs=_module("_lpm_engine_context").EffectInputs(),
    )

    assert isinstance(resumed, Failure)
    assert resumed.failure().error_type == "store-unavailable"
    assert "no pending target operation" in resumed.failure().message


def test_a_durable_issue_record_resumes_through_the_engine(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    operation = _operation()
    _ = _persisted(state_dir=state_dir, operation=operation)

    resumed = _module("_lpm_engine").resume_phase(
        engine=_engine(state_dir=state_dir),
        command="target",
        idempotency_key=_KEY,
        inputs=_inputs(destination=str(tmp_path / "destination")),
    )

    # No registration was seeded, so position 1's delete postcondition is ALREADY the
    # committed one and settles rather than running — the contract's conditional no-op.
    assert isinstance(resumed, Success), resumed
    assert resumed.unwrap().performed == (0,)
    assert resumed.unwrap().skipped == (1,)
