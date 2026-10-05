"""A `complete` operation records its completion before the tombstone that closes the run.

SPECIFICATION/contracts.md states the array exactly: "Complete `apply` against a live assignment
MUST contain exactly `proof-update`, `completion-update`, `assignment-end-update`,
`lease-release`, `tombstone-create`, `assignment-close`; against a tombstone with null completion
it MUST contain exactly the first two." It further requires that "Tombstone creation MUST commit
before assignment removal; while both files survive that crash window, the tombstone is
authoritative and reuse remains refused", and that a tombstone's nullable `completion` carry "the
exact completion-input shape".

THE ORDER IS PROVEN BY OBSTRUCTING THE TOMBSTONE'S OWN WRITE, not by reading the array back. A
test that asserted the ordered names would only restate the plan table; the thing that matters is
what is on disk when the phase cannot finish. So one exercise redirects the `tombstones/` family
directory at nothing, which makes the creation's atomic replacement refuse while leaving its READ
answering plain absence — and the live assignment must then already carry both the completion and
the lease end, and must still be there, because `assignment-close` was never reached. An
implementation that closed first, or that wrote the completion only into the tombstone, fails
exactly there.

SEEDING A RIVAL TOMBSTONE WOULD NOT HAVE PROVEN IT, and that is worth recording. A standing
tombstone is AUTHORITATIVE for its run, so the earlier positions would legitimately have written
their completion and lease end into THAT record instead — the phase would refuse at the same
place for the same reason while proving nothing about the live assignment. The obstruction has to
break the write, not the binding.

THE DURABLE-CLOSURE INTERLOCK IS ASSERTED FROM BOTH SIDES. A completed phase leaves the
tombstone carrying the completion and the normalized lease end with the assignment gone; a phase
whose tombstone is missing leaves the assignment untouched. Only the pair rules out an engine
that removes a live binding on the strength of its own progress rather than on durable evidence.

A DISAGREEING STORED COMPLETION REFUSES. A completion is the consumer's own account of a finished
run, so a second, different one means two commands claim the same `consumer_run_id`; whichever
survived an overwrite would be a record nobody filed.
"""

from __future__ import annotations

import importlib
import os
import pathlib

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_OPERATION_ID = "7a3e9c05-4b18-4f6d-9e21-5c8b0d7a3f42"
_KEY = "f" * 64
_ACCEPTED_AT = "2026-10-05T14:00:00Z"
_RUN_ID = "run-complete-one"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_TARGET_REF = "ref-complete-7c40"
_ACCOUNT = "acct-primary"
_VALUE_REF = "op://llm-provider-manager-token-values/3f2504e0-gen/credential"
_LEASE_STARTED_AT = "2026-10-05T11:00:00Z"
_LEASE_EXPIRES_AT = "2026-10-05T13:00:00Z"
_COMMITTED_AT = "2026-10-05T11:00:05Z"
_NORMALIZED_CLOSE_AT = "2026-10-05T13:00:00Z"
_COMPLETED_AT = "2026-10-05T12:30:00Z"

_COMPLETE_APPLY = (
    "proof-update",
    "completion-update",
    "assignment-end-update",
    "lease-release",
    "tombstone-create",
    "assignment-close",
)
_TOMBSTONE_APPLY = _COMPLETE_APPLY[:2]


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _provision_request() -> dict[str, object]:
    return {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "consumer_run_id": _RUN_ID,
        "target_ref": _TARGET_REF,
        "strategy": "consume-first",
        "lease_seconds": 7200,
    }


def _completion_input(**changes: object) -> dict[str, object]:
    source: dict[str, object] = {
        "version": 1,
        "consumer_run_id": _RUN_ID,
        "record_id": _RECORD_ID,
        "completed_at": _COMPLETED_AT,
        "consumer_class": "production",
        "provider_authenticated": True,
        "alternate_credential_used": False,
        "legacy_pool_absent": False,
    }
    source.update(changes)
    return source


def _assignment(**changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "version": 1,
        "status": "committed",
        "request": _provision_request(),
        "target_ref": _TARGET_REF,
        "account_id": _ACCOUNT,
        "value_generation": _GENERATION,
        "value_ref": _VALUE_REF,
        "record_id": _RECORD_ID,
        "receipt": {
            "record_id": _RECORD_ID,
            "account_id": _ACCOUNT,
            "purpose": "factory",
            "validated_at": "2026-10-05T10:30:00Z",
            "lease_expires_at": _LEASE_EXPIRES_AT,
        },
        "lease_started_at": _LEASE_STARTED_AT,
        "lease_expires_at": _LEASE_EXPIRES_AT,
        "target_committed_at": _COMMITTED_AT,
        "actual_lease_ended_at": None,
        "report_markers": [],
        "completion": None,
    }
    record.update(changes)
    return record


def _tombstone(**changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "version": 1,
        "request": _provision_request(),
        "target_ref": _TARGET_REF,
        "account_id": _ACCOUNT,
        "value_generation": _GENERATION,
        "value_ref": _VALUE_REF,
        "record_id": _RECORD_ID,
        "lease_started_at": _LEASE_STARTED_AT,
        "lease_expires_at": _LEASE_EXPIRES_AT,
        "target_committed_at": _COMMITTED_AT,
        "actual_lease_ended_at": _NORMALIZED_CLOSE_AT,
        "closed_at": _ACCEPTED_AT,
        "report_markers": [],
        "completion": None,
    }
    record.update(changes)
    return record


def _lease() -> dict[str, object]:
    return {
        "version": 1,
        "provider": "anthropic",
        "account_id": _ACCOUNT,
        "record_id": _RECORD_ID,
        "consumer_run_id": _RUN_ID,
        "lease_started_at": _LEASE_STARTED_AT,
        "lease_expires_at": _LEASE_EXPIRES_AT,
    }


def _state(*, tmp_path: pathlib.Path) -> pathlib.Path:
    state_dir = tmp_path / "manager-state"
    state_dir.mkdir(mode=0o700)
    return state_dir


def _family_path(*, state_dir: pathlib.Path, family: str, identity: tuple[str, ...]):
    located = _module("_lpm_paths").local_record_path(
        state_dir=state_dir, family=family, identity=identity
    )
    assert isinstance(located, Success)
    return located.unwrap()


def _seed(*, path: pathlib.Path, value: object) -> None:
    written = _module("_lpm_localstate").write_local_record(
        path=path, value=value, owner_uid=os.getuid()
    )
    assert isinstance(written, Success), written


def _read(*, path: pathlib.Path):
    stored = _module("_lpm_localstate").read_local_record(path=path, owner_uid=os.getuid())
    assert isinstance(stored, Success), stored
    return stored.unwrap()


def _engine(*, state_dir: pathlib.Path):
    return _module("_lpm_engine_context").OperationEngine(
        state_dir=state_dir,
        owner_uid=os.getuid(),
        store=_module("_lpm_store").InMemorySecretStore(),
    )


def _operation(*, effects: tuple[str, ...]):
    return _module("_lpm_operation").OperationRecord(
        operation_id=_OPERATION_ID,
        command="complete",
        phase="apply",
        idempotency_key=_KEY,
        accepted_at=_ACCEPTED_AT,
        normalized_input=_completion_input(),
        terminal_result=None,
        ordered_effects=effects,
        completed_step=-1,
    )


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


def _live_complete(*, tmp_path: pathlib.Path):
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )
    _seed(
        path=_family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT)),
        value=_lease(),
    )
    operation = _operation(effects=_COMPLETE_APPLY)
    _persisted(state_dir=state_dir, operation=operation)
    return state_dir, operation


def _driven(*, state_dir: pathlib.Path, operation):
    return _module("_lpm_engine").drive_operation(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_module("_lpm_engine_context").EffectInputs(),
        condition="every-effect-committed",
        context=_module("_lpm_operation_plan").PlanContext(
            against_tombstone=len(operation.ordered_effects) == len(_TOMBSTONE_APPLY)
        ),
        terminal_result=None,
    )


def test_a_live_completion_closes_the_run_through_a_durable_tombstone(
    tmp_path: pathlib.Path,
) -> None:
    state_dir, operation = _live_complete(tmp_path=tmp_path)

    finished = _driven(state_dir=state_dir, operation=operation)

    assert isinstance(finished, Success), finished
    assert finished.unwrap() is None
    assert _read(
        path=_family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,))
    ) == _tombstone(completion=_completion_input())
    assert not _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)).exists()
    assert not _family_path(
        state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT)
    ).exists()


def test_the_completion_and_lease_end_are_durable_before_the_tombstone_is_created(
    tmp_path: pathlib.Path,
) -> None:
    state_dir, operation = _live_complete(tmp_path=tmp_path)
    (state_dir / "tombstones").symlink_to(tmp_path / "nowhere")
    assignment_path = _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,))

    refused = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_module("_lpm_engine_context").EffectInputs(),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "is a symlink" in refused.failure().message
    standing = _read(path=assignment_path)
    assert isinstance(standing, dict)
    assert standing["completion"] == _completion_input()
    assert standing["actual_lease_ended_at"] == _NORMALIZED_CLOSE_AT
    assert assignment_path.exists(), "the live assignment outlives a closure that never committed"


def test_a_completion_against_a_retained_tombstone_applies_only_its_first_two_effects(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    tombstone_path = _family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,))
    _seed(path=tombstone_path, value=_tombstone())
    operation = _operation(effects=_TOMBSTONE_APPLY)
    _persisted(state_dir=state_dir, operation=operation)

    finished = _driven(state_dir=state_dir, operation=operation)

    assert isinstance(finished, Success), finished
    assert finished.unwrap() is None
    assert _read(path=tombstone_path) == _tombstone(completion=_completion_input())
    assert not _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)).exists()


def test_a_different_stored_completion_refuses_rather_than_being_overwritten(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    tombstone_path = _family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,))
    _seed(
        path=tombstone_path,
        value=_tombstone(completion=_completion_input(consumer_class="test")),
    )
    untouched = tombstone_path.read_bytes()
    operation = _operation(effects=_TOMBSTONE_APPLY)
    _persisted(state_dir=state_dir, operation=operation)

    refused = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_module("_lpm_engine_context").EffectInputs(),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "a different completion already closes this run" in refused.failure().message
    assert tombstone_path.read_bytes() == untouched


def test_a_completion_with_no_binding_record_at_all_refuses(tmp_path: pathlib.Path) -> None:
    state_dir = _state(tmp_path=tmp_path)
    operation = _operation(effects=_TOMBSTONE_APPLY)

    refused = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_module("_lpm_engine_context").EffectInputs(),
    )

    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "store-unavailable"
    assert "no live assignment or tombstone stands" in refused.failure().message


def test_re_driving_a_finished_completion_phase_rewrites_nothing(
    tmp_path: pathlib.Path,
) -> None:
    state_dir, operation = _live_complete(tmp_path=tmp_path)
    first = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_module("_lpm_engine_context").EffectInputs(),
    )
    assert isinstance(first, Success), first
    assert first.unwrap().performed == (1, 2, 3, 4, 5)
    assert first.unwrap().skipped == (0,)
    tombstone_bytes = _family_path(
        state_dir=state_dir, family="tombstone", identity=(_RUN_ID,)
    ).read_bytes()

    replay = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir),
        operation=operation,
        inputs=_module("_lpm_engine_context").EffectInputs(),
    )

    assert isinstance(replay, Success), replay
    assert replay.unwrap().performed == ()
    assert replay.unwrap().skipped == (0, 1, 2, 3, 4, 5)
    assert (
        _family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,)).read_bytes()
        == tombstone_bytes
    )
