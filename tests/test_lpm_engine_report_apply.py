"""A `report` operation's `apply` phase runs through the engine against both bindings.

SPECIFICATION/contracts.md fixes the arrays literally: "Report `apply` against a live
assignment MUST contain exactly `audit-append`, `credential-conditional-set`, `proof-update`,
`report-marker-update`, `assignment-end-update`, `lease-release`, `tombstone-create`,
`assignment-close`; against a tombstone it MUST contain exactly the first four." It further
requires `report-marker-update` to "insert the new unique marker in the assignment or
tombstone's declared canonical order", the lifecycle transition to be "a compare-and-set
conditioned on the matching assignment or tombstone's stored `value_generation` still equaling
the record's current `value_generation`", and tombstone creation to "commit before assignment
removal".

THE EIGHT POSITIONS ARE DRIVEN THROUGH THE PUBLIC ENGINE, not called one at a time. The
scenario "An interrupted report resumes before duplicate acknowledgement" is about a phase that
already committed some of its effects, so the only exercise that can prove it is one that drives
the WHOLE array and then drives it again from an unstarted checkpoint. A per-effect unit test
cannot see the thing that goes wrong — a second logical report — because duplication is a
property of the SEQUENCE.

THE REPLAY ASSERTS THE AUDIT LINE COUNT AND THE REVISION COUNT, not merely that the second pass
succeeded. Those two are where a duplicate would actually land: the audit log is append-only, so
a repeated append is permanent, and the credential's revision chain would carry a second
`suspect` revision whose effect id nobody can relate to a report. Both are counted before and
after.

`closed_at` AND `actual_lease_ended_at` ARE DELIBERATELY DIFFERENT HERE. The fixture accepts the
report AFTER its lease expired, which is the contract's "Run closure clamps a lease that expires
during global recovery" case: the normalized close time clamps to `lease_expires_at` while
`closed_at` keeps the later stored `accepted_at`. A fixture whose accepted time sat inside the
lease window would make the two values equal and the clamp invisible.
"""

from __future__ import annotations

import importlib
import os
import pathlib

from overseer._vendor.returns.result import Success

__all__: list[str] = []

_OPERATION_ID = "9d1a4f2c-6b7e-4a51-8c3d-2f0e5b7a9c14"
_KEY = "a" * 64
_ACCEPTED_AT = "2026-10-03T14:00:00Z"
# The caller's first-adapter-attempt clock sample, which the audit line dates itself from. It is
# DELIBERATELY later than `_ACCEPTED_AT`: the two are different instants, and a fixture that made
# them equal could not tell a line dated at the attempt from one dated at the acceptance. The
# delayed-attempt and replay-preservation properties themselves are driven by
# `tests/test_lpm_audit_attempt_time.py`.
_ATTEMPT_AT = "2026-10-03T14:00:09Z"
_RUN_ID = "run-report-one"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_TARGET_REF = "ref-report-9f21"
_ACCOUNT = "acct-primary"
_VALUE_REF = "op://llm-provider-manager-token-values/3f2504e0-gen/credential"
_LEASE_STARTED_AT = "2026-10-03T11:00:00Z"
_LEASE_EXPIRES_AT = "2026-10-03T13:00:00Z"
_COMMITTED_AT = "2026-10-03T11:00:05Z"
_NORMALIZED_CLOSE_AT = "2026-10-03T13:00:00Z"
_OCCURRED_AT = "2026-10-03T11:30:00Z"
_EARLIER_OCCURRED_AT = "2026-10-03T11:10:00Z"
_SEED_EFFECT_ID = "b" * 64

_LIVE_APPLY = (
    "audit-append",
    "credential-conditional-set",
    "proof-update",
    "report-marker-update",
    "assignment-end-update",
    "lease-release",
    "tombstone-create",
    "assignment-close",
)
_TOMBSTONE_APPLY = _LIVE_APPLY[:4]


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


def _report_input() -> dict[str, object]:
    return {
        "version": 1,
        "consumer_run_id": _RUN_ID,
        "record_id": _RECORD_ID,
        "occurred_at": _OCCURRED_AT,
        "classification": "authentication",
    }


def _credential(**changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "version": 1,
        "record_id": _RECORD_ID,
        "provider": "anthropic",
        "account_id": _ACCOUNT,
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": "2026-10-03T10:00:00Z",
        "expires_at": None,
        "last_validated": "2026-10-03T10:30:00Z",
        "value_generation": _GENERATION,
        "value_ref": _VALUE_REF,
        "previous_value_ref": None,
    }
    record.update(changes)
    return record


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
            "validated_at": "2026-10-03T10:30:00Z",
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


def _marker(*, occurred_at: str, classification: str) -> dict[str, str]:
    return {"occurred_at": occurred_at, "classification": classification}


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


def _seeded_store(*, record: dict[str, object] | None = None):
    store_module = _module("_lpm_store")
    store = store_module.InMemorySecretStore()
    desired = _module("_lpm_canonical").canonical_json_text(
        value=_credential() if record is None else record
    )
    assert isinstance(desired, Success), desired
    committed = store.credential_conditional_set(
        request=store_module.ConditionalSet(
            record_id=_RECORD_ID,
            effect_id=_SEED_EFFECT_ID,
            expected_record=None,
            desired_record=desired.unwrap(),
        )
    )
    assert committed["status"] == "committed", committed
    return store


def _engine(*, state_dir: pathlib.Path, store):
    return _module("_lpm_engine_context").OperationEngine(
        state_dir=state_dir, owner_uid=os.getuid(), store=store
    )


def _operation(*, effects: tuple[str, ...]):
    return _module("_lpm_operation").OperationRecord(
        operation_id=_OPERATION_ID,
        command="report",
        phase="apply",
        idempotency_key=_KEY,
        accepted_at=_ACCEPTED_AT,
        normalized_input=_report_input(),
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
    return located.unwrap()


def _audit_entries(*, state_dir: pathlib.Path) -> tuple[object, ...]:
    log = _module("_lpm_audit").read_audit_log(
        path=state_dir / _module("_lpm_paths").AUDIT_LOG_NAME, owner_uid=os.getuid()
    )
    assert isinstance(log, Success), log
    return log.unwrap()


def _current_record(*, store) -> object:
    result = store.metadata_get(record_id=_RECORD_ID)
    assert result["status"] == "ok", result
    item = result["item"]
    assert isinstance(item, dict)
    parsed = _module("_lpm_canonical").parse_canonical_json(text=item["record"])
    assert isinstance(parsed, Success), parsed
    return parsed.unwrap()


def _effect_id(*, operation, index: int) -> str:
    derived = _module("_lpm_operation_identity").effect_id(operation=operation, index=index)
    assert isinstance(derived, Success), derived
    return derived.unwrap()


def _inputs():
    context_module = _module("_lpm_engine_context")
    return context_module.EffectInputs(audit=context_module.AuditInputs(attempt_now=_ATTEMPT_AT))


def _driven(*, state_dir: pathlib.Path, store, operation):
    return _module("_lpm_engine").drive_operation(
        engine=_engine(state_dir=state_dir, store=store),
        operation=operation,
        inputs=_inputs(),
        condition="every-effect-committed",
        context=_module("_lpm_operation_plan").PlanContext(
            against_tombstone=len(operation.ordered_effects) == len(_TOMBSTONE_APPLY)
        ),
        terminal_result=None,
    )


def _live_report(*, tmp_path: pathlib.Path):
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )
    _seed(
        path=_family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT)),
        value=_lease(),
    )
    store = _seeded_store()
    operation = _operation(effects=_LIVE_APPLY)
    _ = _persisted(state_dir=state_dir, operation=operation)
    return state_dir, store, operation


def test_a_live_assignment_report_applies_every_ordered_effect_and_closes_the_run(
    tmp_path: pathlib.Path,
) -> None:
    state_dir, store, operation = _live_report(tmp_path=tmp_path)

    finished = _driven(state_dir=state_dir, store=store, operation=operation)

    assert isinstance(finished, Success), finished
    assert finished.unwrap() is None
    assert _audit_entries(state_dir=state_dir) == (
        _module("_lpm_audit").AuditEntry(
            record_id=_RECORD_ID,
            effect_id=_effect_id(operation=operation, index=0),
            actor="report-writer",
            operation="credential-conditional-set",
            attempted_at=_ATTEMPT_AT,
        ),
    )
    assert _current_record(store=store) == _credential(status="suspect")
    assert len(store.items[_RECORD_ID]) == 2
    assert not _family_path(
        state_dir=state_dir, family="pending-metadata-effect", identity=(_RECORD_ID,)
    ).exists()
    assert _read(
        path=_family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,))
    ) == _tombstone(
        report_markers=[_marker(occurred_at=_OCCURRED_AT, classification="authentication")]
    )
    assert not _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)).exists()
    assert not _family_path(
        state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT)
    ).exists()
    assert not _family_path(
        state_dir=state_dir, family="operation", identity=("report", _KEY)
    ).exists()


def test_a_report_against_an_authoritative_tombstone_applies_only_its_first_four_effects(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    tombstone_path = _family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,))
    _seed(
        path=tombstone_path,
        value=_tombstone(
            report_markers=[_marker(occurred_at=_OCCURRED_AT, classification="provider-outage")]
        ),
    )
    store = _seeded_store()
    operation = _operation(effects=_TOMBSTONE_APPLY)
    _ = _persisted(state_dir=state_dir, operation=operation)

    finished = _driven(state_dir=state_dir, store=store, operation=operation)

    assert isinstance(finished, Success), finished
    assert finished.unwrap() is None
    stored = _read(path=tombstone_path)
    assert isinstance(stored, dict)
    assert stored["report_markers"] == [
        _marker(occurred_at=_OCCURRED_AT, classification="authentication"),
        _marker(occurred_at=_OCCURRED_AT, classification="provider-outage"),
    ]
    assert stored["actual_lease_ended_at"] == _NORMALIZED_CLOSE_AT
    assert stored["closed_at"] == _ACCEPTED_AT
    assert len(store.items[_RECORD_ID]) == 2
    assert len(_audit_entries(state_dir=state_dir)) == 1


def test_a_tombstone_marker_lands_in_canonical_order_rather_than_at_the_end(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    tombstone_path = _family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,))
    _seed(
        path=tombstone_path,
        value=_tombstone(
            report_markers=[_marker(occurred_at=_OCCURRED_AT, classification="rate-limit")]
        ),
    )
    operation = _operation(effects=_TOMBSTONE_APPLY)
    _ = _persisted(state_dir=state_dir, operation=operation)
    store = _seeded_store(record=_credential(status="suspect"))

    driven = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir, store=store),
        operation=_module("_lpm_operation").OperationRecord(
            operation_id=_OPERATION_ID,
            command="report",
            phase="apply",
            idempotency_key=_KEY,
            accepted_at=_ACCEPTED_AT,
            normalized_input={**_report_input(), "occurred_at": _EARLIER_OCCURRED_AT},
            terminal_result=None,
            ordered_effects=_TOMBSTONE_APPLY,
            completed_step=-1,
        ),
        inputs=_inputs(),
    )

    assert isinstance(driven, Success), driven
    stored = _read(path=tombstone_path)
    assert isinstance(stored, dict)
    assert stored["report_markers"] == [
        _marker(occurred_at=_EARLIER_OCCURRED_AT, classification="authentication"),
        _marker(occurred_at=_OCCURRED_AT, classification="rate-limit"),
    ]


def test_re_driving_the_whole_report_phase_duplicates_no_logical_report(
    tmp_path: pathlib.Path,
) -> None:
    state_dir, store, operation = _live_report(tmp_path=tmp_path)
    first = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir, store=store),
        operation=operation,
        inputs=_inputs(),
    )
    assert isinstance(first, Success), first
    assert first.unwrap().performed == (0, 1, 3, 4, 5, 6, 7)
    assert first.unwrap().skipped == (2,)
    tombstone_bytes = _family_path(
        state_dir=state_dir, family="tombstone", identity=(_RUN_ID,)
    ).read_bytes()

    replay = _module("_lpm_engine").drive_phase(
        engine=_engine(state_dir=state_dir, store=store),
        operation=operation,
        inputs=_inputs(),
    )

    assert isinstance(replay, Success), replay
    assert replay.unwrap().performed == ()
    assert replay.unwrap().skipped == (0, 1, 2, 3, 4, 5, 6, 7)
    assert len(_audit_entries(state_dir=state_dir)) == 1
    assert len(store.items[_RECORD_ID]) == 2
    assert (
        _family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,)).read_bytes()
        == tombstone_bytes
    )
