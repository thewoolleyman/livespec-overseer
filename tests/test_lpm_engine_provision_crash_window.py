"""Provision `start`, `postcommit` and `cleanup` across a really-lost checkpoint.

SPECIFICATION/contracts.md fixes all three arrays — "Provision `start` MUST contain exactly
`lease-create`, `prepared-assignment-create`, `target-write`; `postcommit` MUST contain
exactly `assignment-commit`, `selection-update`, `proof-update`", and "`cleanup` MUST contain
`prepared-assignment-discard` when prepared state exists and MUST always end with
`lease-release`" — and requires an effect commit followed by a crash before `completed_step`
advancement to "replay as one logical effect".

THE CRASH IS THE SAME INJECTION THE TARGET-ISSUE PROOFS USE, at the same real checkpoint
writer: the durable record is left more broadly accessible than owner-only, which
`_lpm_localstate` must refuse without resetting or mutating it, so the position's effect
commits and its checkpoint cannot land. Recovery re-reads the record through `resume_phase`
or `pending_operation` — never from the crashed pass's own return value.

THE MOVED FENCE IS WHAT MAKES THE `postcommit` PROOF WORTH ANYTHING. A recovered `postcommit`
is handed a DIFFERENT, LATER `fence_now` than the one `start` committed under, because a
fresh process genuinely would sample its clock again. Every instant it writes must still be
the ORIGINAL one: `assignment-commit` reads it back from the durable target-commit record
rather than re-sampling, and `selection-update` and `proof-update` take theirs from the
committed assignment. Handing the recovery the same fence twice would make a re-sampling
executor and a reading one indistinguishable — the lease window, the rollout-start minimum
and every later close time all hang off which of the two it is.

`cleanup` IS THE DELETE-SIDE WINDOW, and it settles on the opposite evidence. For a delete
effect the contract defines ABSENCE after its required predecessor as the committed
postcondition, so the recovery's proof that position 0 already ran is that the assignment is
gone — the one case where finding nothing is finding the answer.
"""

from __future__ import annotations

import importlib
import os
import pathlib

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_OPERATION_ID = "7a3d1e52-6c8b-4f0a-9d27-3e5c7b9f1a46"
_KEY = "e" * 64
_ACCEPTED_AT = "2026-10-02T11:00:00Z"
_FENCE_NOW = "2026-10-02T11:00:05Z"
_LATER_FENCE_NOW = "2026-10-02T11:42:17Z"
_RUN_ID = "run-crash-provision"
_TARGET_REF = "ref-crash-provision-5b1c"
_RECORD_ID = "8d4f2a60-5e91-43c7-b2a8-1f6c0d3e5b72"
_GENERATION = "9e5a3b71-6f02-44d8-a3b9-2c7d1e4f6a83"
_ACCOUNT = "acct-crash-primary"
_LEASE_SECONDS = 3600
_LEASE_EXPIRES_AT = "2026-10-02T12:00:00Z"
_VALUE = b"sk-ant-oat0-crash-window"

_START_EFFECTS = ("lease-create", "prepared-assignment-create", "target-write")
_POSTCOMMIT_EFFECTS = ("assignment-commit", "selection-update", "proof-update")
_CLEANUP_EFFECTS = ("prepared-assignment-discard", "lease-release")

_BROADER_THAN_OWNER_MODE = 0o644
_OWNER_ONLY_MODE = 0o600


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


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


def _inputs(*, tmp_path: pathlib.Path, fence_now: str = _FENCE_NOW):
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
            fence_now=fence_now,
        )
    )


def _family_path(
    *, state_dir: pathlib.Path, family: str, identity: tuple[str, ...]
) -> pathlib.Path:
    located = _module("_lpm_paths").local_record_path(
        state_dir=state_dir, family=family, identity=identity
    )
    assert isinstance(located, Success), located
    return located.unwrap()


def _persisted(*, state_dir: pathlib.Path, operation) -> pathlib.Path:
    store_module = _module("_lpm_operation_store")
    located = store_module.operation_path(
        state_dir=state_dir, command=operation.command, idempotency_key=operation.idempotency_key
    )
    assert isinstance(located, Success), located
    written = store_module.write_operation(
        path=located.unwrap(), operation=operation, owner_uid=os.getuid()
    )
    assert isinstance(written, Success), written
    return located.unwrap()


def _read(*, path: pathlib.Path):
    stored = _module("_lpm_localstate").read_local_record(path=path, owner_uid=os.getuid())
    assert isinstance(stored, Success), stored
    return stored.unwrap()


def _durable(*, state_dir: pathlib.Path):
    pending = _module("_lpm_engine").pending_operation(
        engine=_engine(state_dir=state_dir), command="provision", idempotency_key=_KEY
    )
    assert isinstance(pending, Success), pending
    return pending.unwrap()


def _lose_the_checkpoint(*, record_path: pathlib.Path) -> None:
    """Make the REAL checkpoint writer refuse, leaving the durable record exactly as found."""
    record_path.chmod(_BROADER_THAN_OWNER_MODE)


def _restart(*, record_path: pathlib.Path) -> None:
    """Hand the record back to a fresh pass, byte-for-byte as the crashed one left it."""
    record_path.chmod(_OWNER_ONLY_MODE)


def _crashed_start(*, tmp_path: pathlib.Path, state_dir: pathlib.Path) -> pathlib.Path:
    """Commit `start` position 0 and lose its checkpoint; return the durable record's path."""
    record_path = _persisted(
        state_dir=state_dir, operation=_operation(phase="start", effects=_START_EFFECTS)
    )
    _lose_the_checkpoint(record_path=record_path)
    crashed = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=_operation(phase="start", effects=_START_EFFECTS),
        inputs=_inputs(tmp_path=tmp_path),
    )
    assert isinstance(crashed, Failure), crashed
    assert crashed.failure().error_type == "store-unavailable"
    assert "more broadly accessible" in crashed.failure().message
    _restart(record_path=record_path)
    return record_path


def _recovered_postcommit(*, tmp_path: pathlib.Path, state_dir: pathlib.Path):
    """Finish a crashed `start` from the durable record and take its ratified transition."""
    _ = _crashed_start(tmp_path=tmp_path, state_dir=state_dir)
    standing = _durable(state_dir=state_dir)
    assert standing is not None
    replaced = _module("_lpm_engine").drive_operation(
        engine=_engine(state_dir=state_dir),
        operation=standing,
        inputs=_inputs(tmp_path=tmp_path),
        condition="target-committed",
        context=_module("_lpm_operation_plan").PlanContext(),
        terminal_result=None,
    )
    assert isinstance(replaced, Success), replaced
    following = replaced.unwrap()
    assert following is not None
    return following


def test_a_lost_start_checkpoint_settles_its_lease_and_commits_the_rest_once(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    lease_path = _family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT))
    record_path = _crashed_start(tmp_path=tmp_path, state_dir=state_dir)
    leased_bytes = lease_path.read_bytes()
    standing = _durable(state_dir=state_dir)
    assert standing is not None
    assert standing.completed_step == -1
    assert standing.phase == "start"

    recovered = _module("_lpm_engine").resume_phase(
        engine=_engine(state_dir=state_dir),
        command="provision",
        idempotency_key=_KEY,
        inputs=_inputs(tmp_path=tmp_path),
    )

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().skipped == (0,)
    assert recovered.unwrap().performed == (1, 2)
    assert lease_path.read_bytes() == leased_bytes
    assert _read(path=lease_path) == {
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
    prepared = _read(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    )
    assert isinstance(prepared, dict)
    assert prepared["status"] == "prepared"
    assert prepared["target_committed_at"] is None
    assert pathlib.Path(str(tmp_path / "target" / "credential")).read_bytes() == _VALUE
    recovered_record = _durable(state_dir=state_dir)
    assert recovered_record is not None
    assert recovered_record.completed_step == 2
    assert recovered_record.ordered_effects == _START_EFFECTS
    assert record_path.exists()


def test_a_start_recovered_from_disk_is_replaced_by_postcommit_under_the_same_identity(
    tmp_path: pathlib.Path,
) -> None:
    identity_module = _module("_lpm_operation_identity")
    state_dir = _state(tmp_path=tmp_path)

    following = _recovered_postcommit(tmp_path=tmp_path, state_dir=state_dir)

    assert following.phase == "postcommit"
    assert following.ordered_effects == _POSTCOMMIT_EFFECTS
    assert following.completed_step == -1
    assert following.operation_id == _OPERATION_ID
    assert following.command == "provision"
    assert following.idempotency_key == _KEY
    assert following.accepted_at == _ACCEPTED_AT
    assert following.normalized_input == _provision_input()
    stored = _durable(state_dir=state_dir)
    assert stored == following
    started = identity_module.effect_positions(
        operation=_operation(phase="start", effects=_START_EFFECTS)
    )
    replaced = identity_module.effect_positions(operation=following)
    assert {position.effect_id for position in replaced}.isdisjoint(
        {position.effect_id for position in started}
    )


def test_a_lost_postcommit_checkpoint_keeps_every_instant_the_commit_already_fixed(
    tmp_path: pathlib.Path,
) -> None:
    paths = _module("_lpm_paths")
    state_dir = _state(tmp_path=tmp_path)
    following = _recovered_postcommit(tmp_path=tmp_path, state_dir=state_dir)
    record_path = _family_path(
        state_dir=state_dir, family="operation", identity=("provision", _KEY)
    )
    assignment_path = _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    _lose_the_checkpoint(record_path=record_path)
    crashed = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir), operation=following, inputs=_inputs(tmp_path=tmp_path)
    )
    assert isinstance(crashed, Failure), crashed
    committed_bytes = assignment_path.read_bytes()
    _restart(record_path=record_path)
    standing = _durable(state_dir=state_dir)
    assert standing is not None
    assert standing.completed_step == -1
    assert standing.phase == "postcommit"

    recovered = _module("_lpm_engine").resume_phase(
        engine=_engine(state_dir=state_dir),
        command="provision",
        idempotency_key=_KEY,
        inputs=_inputs(tmp_path=tmp_path, fence_now=_LATER_FENCE_NOW),
    )

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().skipped == (0,)
    assert recovered.unwrap().performed == (1, 2)
    assert assignment_path.read_bytes() == committed_bytes
    committed = _read(path=assignment_path)
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


def test_a_lost_cleanup_checkpoint_settles_on_the_absence_its_own_effect_created(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    engine_module = _module("_lpm_engine")
    start = _operation(phase="start", effects=_START_EFFECTS)
    _ = _persisted(state_dir=state_dir, operation=start)
    prepared = engine_module.drive_phase(
        engine=_engine(state_dir=state_dir), operation=start, inputs=_inputs(tmp_path=tmp_path)
    )
    assert isinstance(prepared, Success), prepared
    assignment_path = _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))
    lease_path = _family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT))
    record_path = _persisted(
        state_dir=state_dir, operation=_operation(phase="cleanup", effects=_CLEANUP_EFFECTS)
    )
    _lose_the_checkpoint(record_path=record_path)
    crashed = engine_module.drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=_operation(phase="cleanup", effects=_CLEANUP_EFFECTS),
        inputs=_inputs(tmp_path=tmp_path),
    )
    assert isinstance(crashed, Failure), crashed
    assert not assignment_path.exists()
    assert lease_path.exists()
    _restart(record_path=record_path)
    standing = _durable(state_dir=state_dir)
    assert standing is not None
    assert standing.completed_step == -1

    recovered = engine_module.resume_phase(
        engine=_engine(state_dir=state_dir),
        command="provision",
        idempotency_key=_KEY,
        inputs=_inputs(tmp_path=tmp_path),
    )

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().skipped == (0,)
    assert recovered.unwrap().performed == (1,)
    assert not assignment_path.exists()
    assert not lease_path.exists()


def test_a_cleanup_recovered_from_disk_removes_its_own_operation_record(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    engine_module = _module("_lpm_engine")
    start = _operation(phase="start", effects=_START_EFFECTS)
    _ = _persisted(state_dir=state_dir, operation=start)
    prepared = engine_module.drive_phase(
        engine=_engine(state_dir=state_dir), operation=start, inputs=_inputs(tmp_path=tmp_path)
    )
    assert isinstance(prepared, Success), prepared
    record_path = _persisted(
        state_dir=state_dir, operation=_operation(phase="cleanup", effects=_CLEANUP_EFFECTS)
    )
    _lose_the_checkpoint(record_path=record_path)
    crashed = engine_module.drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=_operation(phase="cleanup", effects=_CLEANUP_EFFECTS),
        inputs=_inputs(tmp_path=tmp_path),
    )
    assert isinstance(crashed, Failure), crashed
    _restart(record_path=record_path)
    standing = _durable(state_dir=state_dir)
    assert standing is not None

    finished = engine_module.drive_operation(
        engine=_engine(state_dir=state_dir),
        operation=standing,
        inputs=_inputs(tmp_path=tmp_path),
        condition="every-effect-committed",
        context=_module("_lpm_operation_plan").PlanContext(prepared_state_exists=True),
        terminal_result=None,
    )

    assert isinstance(finished, Success), finished
    assert finished.unwrap() is None
    assert not record_path.exists()
    assert _durable(state_dir=state_dir) is None
