"""The engine's one crash window, injected for real and recovered from persisted state.

SPECIFICATION/contracts.md requires that each executor's postcondition inspection "MUST make
an effect commit followed by a crash before `completed_step` advancement replay as one
logical effect". The window between an effect committing and its checkpoint landing cannot be
closed — they are two different stores — so it is survived instead, and these tests are the
evidence that the PRESERVED engine core actually survives it.

THE CRASH IS INJECTED AT THE REAL CHECKPOINT WRITER, NOT SIMULATED AROUND IT.
`_lpm_engine.drive_phase` composes the real `checkpoint_step` over the real durable record,
and its own module docstring names a checkpoint refusal as this window: "When the record
cannot be advanced after its effect committed, `drive_phase` returns that refusal with the
durable record one position BEHIND the world." So the injection makes that refusal happen —
the durable record is left mode `0644`, which `_lpm_localstate` is contractually required to
refuse as "more broadly accessible" while NEITHER RESETTING NOR MUTATING it. The effect
commits, the checkpoint does not, the record's bytes stand exactly as the prior pass left
them, and `drive_phase` reports the refusal. That is the window, reached through the public
engine with real owner-only local files and a real `InMemorySecretStore`.

RECOVERY RESTARTS FROM THE PERSISTED RECORD, NEVER FROM A HELPER'S RETURN VALUE. Every
recovery below re-reads the durable record through the public `resume_phase` or
`pending_operation` — the same two entry points a fresh process has — so nothing a crashed
pass happened to still hold in memory can carry the proof. Re-driving a phase with the
record object the first pass was handed proves the driver settles; it cannot prove the
record on disk says what recovery needs, which is the whole question a crash asks.

THE DISPOSITIONS ARE THE PROOF, AND THEY MUST BE READ AS A PAIR. `skipped` names a position
whose postcondition was found ALREADY authoritative — the evidence that the crashed pass
committed it — and `performed` names one that actually ran. A recovery that reported every
position `performed` would have repeated a committed effect; one that reported every position
`skipped` would have lost an uncommitted one. Only the exact pair distinguishes recovery from
either failure.
"""

from __future__ import annotations

import importlib
import json
import os
import pathlib

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_TARGET_OPERATION_ID = "5f1c7a28-9b0d-4c6e-8a31-2d4b6e8a0c13"
_TARGET_KEY = "c" * 64
_TARGET_ACCEPTED_AT = "2026-10-02T09:15:00Z"
_TARGET_EXPIRES_AT = "2026-10-03T09:15:00Z"
_TARGET_RUN_ID = "run-crash-target"
_REFERENCE = "ref-crash-9d2e"
_ADAPTER = "isolated-run"

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


def _durable(*, path: pathlib.Path):
    stored = _module("_lpm_operation_store").read_operation(path=path, owner_uid=os.getuid())
    assert isinstance(stored, Success), stored
    return stored.unwrap()


def _read(*, path: pathlib.Path):
    stored = _module("_lpm_localstate").read_local_record(path=path, owner_uid=os.getuid())
    assert isinstance(stored, Success), stored
    return stored.unwrap()


def _lose_the_checkpoint(*, record_path: pathlib.Path) -> None:
    """Make the REAL checkpoint writer refuse, leaving the durable record exactly as found.

    `_lpm_localstate` must refuse a record that is more broadly accessible than owner-only
    and must neither reset nor mutate it, so a pass whose effect has already committed
    reaches its checkpoint and cannot advance — the crash window, produced by the shipped
    refusal path rather than by substituting a writer.
    """
    record_path.chmod(_BROADER_THAN_OWNER_MODE)


def _restart(*, record_path: pathlib.Path) -> None:
    """Hand the record back to a fresh pass, byte-for-byte as the crashed one left it."""
    record_path.chmod(_OWNER_ONLY_MODE)


def _target_operation():
    return _module("_lpm_operation").OperationRecord(
        operation_id=_TARGET_OPERATION_ID,
        command="target",
        phase="issue",
        idempotency_key=_TARGET_KEY,
        accepted_at=_TARGET_ACCEPTED_AT,
        normalized_input={
            "version": 1,
            "consumer_run_id": _TARGET_RUN_ID,
            "adapter": _ADAPTER,
        },
        terminal_result=None,
        ordered_effects=("issuance-create", "registration-remove"),
        completed_step=-1,
    )


def _target_inputs(*, destination: str):
    context_module = _module("_lpm_engine_context")
    return context_module.EffectInputs(
        target=context_module.TargetInputs(
            reference=_REFERENCE, adapter=_ADAPTER, destination=destination
        )
    )


def test_a_lost_issue_checkpoint_replays_as_one_logical_effect_from_the_durable_record(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    owner_uid = os.getuid()
    destination = str(tmp_path / "destination")
    operation = _target_operation()
    record_path = _persisted(state_dir=state_dir, operation=operation)
    registration = _family_path(
        state_dir=state_dir, family="run-registration", identity=(_TARGET_RUN_ID,)
    )
    seeded = _module("_lpm_localstate").write_local_record(
        path=registration,
        value={"version": 1, "consumer_run_id": _TARGET_RUN_ID},
        owner_uid=owner_uid,
    )
    assert isinstance(seeded, Success), seeded
    issuance_path = _family_path(state_dir=state_dir, family="issuance", identity=(_REFERENCE,))
    _lose_the_checkpoint(record_path=record_path)

    crashed = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_target_inputs(destination=destination),
    )

    assert isinstance(crashed, Failure), crashed
    assert crashed.failure().error_type == "store-unavailable"
    assert "more broadly accessible" in crashed.failure().message
    committed_bytes = issuance_path.read_bytes()
    _restart(record_path=record_path)
    assert _durable(path=record_path).completed_step == -1
    assert registration.exists()

    recovered = _module("_lpm_engine").resume_phase(
        engine=_engine(state_dir=state_dir),
        command="target",
        idempotency_key=_TARGET_KEY,
        inputs=_target_inputs(destination=destination),
    )

    assert isinstance(recovered, Success), recovered
    assert recovered.unwrap().skipped == (0,)
    assert recovered.unwrap().performed == (1,)
    assert issuance_path.read_bytes() == committed_bytes
    assert _read(path=issuance_path) == {
        "version": 1,
        "reference": _REFERENCE,
        "consumer_run_id": _TARGET_RUN_ID,
        "adapter": _ADAPTER,
        "destination": destination,
        "issued_at": _TARGET_ACCEPTED_AT,
        "expires_at": _TARGET_EXPIRES_AT,
    }
    assert not registration.exists()
    assert _durable(path=record_path).completed_step == 1


def test_the_durable_record_a_crash_leaves_behind_is_still_exactly_ten_members(
    tmp_path: pathlib.Path,
) -> None:
    operation_module = _module("_lpm_operation")
    state_dir = _state(tmp_path=tmp_path)
    operation = _target_operation()
    record_path = _persisted(state_dir=state_dir, operation=operation)
    _lose_the_checkpoint(record_path=record_path)

    crashed = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_target_inputs(destination=str(tmp_path / "destination")),
    )

    assert isinstance(crashed, Failure), crashed
    _restart(record_path=record_path)
    parsed = json.loads(record_path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    assert tuple(sorted(parsed)) == tuple(sorted(operation_module.OPERATION_MEMBERS))
    assert len(operation_module.OPERATION_MEMBERS) == 10
    assert parsed["completed_step"] == -1
    assert parsed["accepted_at"] == _TARGET_ACCEPTED_AT


def test_every_position_keeps_its_identity_across_a_lost_checkpoint(
    tmp_path: pathlib.Path,
) -> None:
    identity_module = _module("_lpm_operation_identity")
    state_dir = _state(tmp_path=tmp_path)
    operation = _target_operation()
    record_path = _persisted(state_dir=state_dir, operation=operation)
    before = identity_module.effect_positions(operation=operation)
    _lose_the_checkpoint(record_path=record_path)

    crashed = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_target_inputs(destination=str(tmp_path / "destination")),
    )

    assert isinstance(crashed, Failure), crashed
    _restart(record_path=record_path)
    pending = _module("_lpm_engine").pending_operation(
        engine=_engine(state_dir=state_dir), command="target", idempotency_key=_TARGET_KEY
    )
    assert isinstance(pending, Success), pending
    durable = pending.unwrap()
    assert durable is not None
    after = identity_module.effect_positions(operation=durable)
    assert after == before
    assert len({position.effect_id for position in after}) == len(after)
