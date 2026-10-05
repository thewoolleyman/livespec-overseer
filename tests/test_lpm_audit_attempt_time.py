"""An audit line's `attempted_at` is the first ADAPTER ATTEMPT's time, not the acceptance time.

SPECIFICATION/contracts.md states two DIFFERENT times for one audited effect, and the whole
point of this file is that they are not interchangeable:

- "Every retry MUST reuse `accepted_at`, which MUST be the manager's current time immediately
  after pre-operation validation" — so a report that crashed and resumed later still carries
  the acceptance instant it was first admitted at.
- "`attempted_at` MUST be manager time captured for the first adapter attempt represented by
  that audit line and is informational rather than part of the replay match above."

A report accepted at one instant and first ATTEMPTED at a much later one is therefore an
ordinary consequence of the retry rule, not an exotic case: acceptance is pinned by the durable
record while the attempt happens whenever the phase actually runs. Dating the line at
`accepted_at` makes it assert an adapter call at an instant when no adapter call could have
occurred, and the log is append-only, so nothing downstream can ever correct it.

THE TWO HALVES PULL IN OPPOSITE DIRECTIONS, WHICH IS WHY BOTH ARE PINNED HERE. The fix to the
first test — take the attempt time from the caller's clock sample — is also the way to break
the append-only guarantee, because a sample re-taken on every pass would rewrite the attempt
instant of a line that was already written. The contract leaves exactly the right room for
both: the idempotency match compares `version`, `record_id`, `effect_id`, `actor` and
`operation` "REGARDLESS of that first attempt's stored `attempted_at`", so a replay must FIND
the existing line and append nothing, leaving the original time in place. A fix that satisfies
only the first test is a regression against the second.

The sample arrives BESIDE the record rather than being read inside the executor, for the reason
`ProvisionInputs.fence_now` already documents: a replay must not re-sample, and an input is the
only shape that lets the caller hold the one sample that matters.
"""

from __future__ import annotations

import importlib
import os
import pathlib

from overseer._vendor.returns.result import Success

__all__: list[str] = []

_OPERATION_ID = "1b6a7c54-9e02-4d38-b1f7-50c9a3e8d472"
_KEY = "c" * 64
_RUN_ID = "run-audit-attempt-time"
_RECORD_ID = "8d42e1f7-3c05-4b96-a7e1-6f20b9c84d35"
_GENERATION = "4a7b9c21-5de8-4f03-9b62-1c8e70da5f49"
_TARGET_REF = "ref-audit-attempt-5c13"
_ACCOUNT = "acct-primary"
_VALUE_REF = "op://llm-provider-manager-token-values/8d42e1f7-gen/credential"
_SEED_EFFECT_ID = "d" * 64

# The report is accepted in JANUARY and its apply phase first runs in OCTOBER. Nothing about
# that gap is contrived: `accepted_at` is retained byte-for-byte across every retry, so any
# report whose phase is interrupted and resumed later has exactly this shape.
_ACCEPTED_AT = "2026-01-02T18:00:00Z"
_FIRST_ATTEMPT_AT = "2026-10-05T16:39:26Z"
_LATER_ATTEMPT_AT = "2026-10-05T17:11:04Z"

_LEASE_STARTED_AT = "2026-01-02T17:00:00Z"
_LEASE_EXPIRES_AT = "2026-01-02T19:00:00Z"
_COMMITTED_AT = "2026-01-02T17:00:05Z"
_OCCURRED_AT = "2026-01-02T17:30:00Z"

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


def _credential() -> dict[str, object]:
    return {
        "version": 1,
        "record_id": _RECORD_ID,
        "provider": "anthropic",
        "account_id": _ACCOUNT,
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": "2026-01-02T16:00:00Z",
        "expires_at": None,
        "last_validated": "2026-01-02T16:30:00Z",
        "value_generation": _GENERATION,
        "value_ref": _VALUE_REF,
        "previous_value_ref": None,
    }


def _assignment() -> dict[str, object]:
    return {
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
            "validated_at": "2026-01-02T16:30:00Z",
            "lease_expires_at": _LEASE_EXPIRES_AT,
        },
        "lease_started_at": _LEASE_STARTED_AT,
        "lease_expires_at": _LEASE_EXPIRES_AT,
        "target_committed_at": _COMMITTED_AT,
        "actual_lease_ended_at": None,
        "report_markers": [],
        "completion": None,
    }


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


def _seeded_store():
    store_module = _module("_lpm_store")
    store = store_module.InMemorySecretStore()
    desired = _module("_lpm_canonical").canonical_json_text(value=_credential())
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


def _operation():
    return _module("_lpm_operation").OperationRecord(
        operation_id=_OPERATION_ID,
        command="report",
        phase="apply",
        idempotency_key=_KEY,
        accepted_at=_ACCEPTED_AT,
        normalized_input=_report_input(),
        terminal_result=None,
        ordered_effects=_LIVE_APPLY,
        completed_step=-1,
    )


def _persisted(*, state_dir: pathlib.Path, operation) -> None:
    store_module = _module("_lpm_operation_store")
    located = store_module.operation_path(
        state_dir=state_dir, command=operation.command, idempotency_key=operation.idempotency_key
    )
    assert isinstance(located, Success)
    written = store_module.write_operation(
        path=located.unwrap(), operation=operation, owner_uid=os.getuid()
    )
    assert isinstance(written, Success), written


def _audit_entries(*, state_dir: pathlib.Path) -> tuple[object, ...]:
    log = _module("_lpm_audit").read_audit_log(
        path=state_dir / _module("_lpm_paths").AUDIT_LOG_NAME, owner_uid=os.getuid()
    )
    assert isinstance(log, Success), log
    return log.unwrap()


def _inputs(*, attempt_now: str):
    context_module = _module("_lpm_engine_context")
    return context_module.EffectInputs(audit=context_module.AuditInputs(attempt_now=attempt_now))


def _live_report(*, tmp_path: pathlib.Path):
    state_dir = tmp_path / "manager-state"
    state_dir.mkdir(mode=0o700)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment(),
    )
    _seed(
        path=_family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT)),
        value=_lease(),
    )
    operation = _operation()
    _persisted(state_dir=state_dir, operation=operation)
    return state_dir, _seeded_store(), operation


def _driven(*, state_dir: pathlib.Path, store, operation, attempt_now: str):
    return _module("_lpm_engine").drive_phase(
        engine=_module("_lpm_engine_context").OperationEngine(
            state_dir=state_dir, owner_uid=os.getuid(), store=store
        ),
        operation=operation,
        inputs=_inputs(attempt_now=attempt_now),
    )


def test_a_delayed_first_attempt_dates_the_audit_line_at_the_attempt_not_the_acceptance(
    tmp_path: pathlib.Path,
) -> None:
    state_dir, store, operation = _live_report(tmp_path=tmp_path)

    driven = _driven(
        state_dir=state_dir, store=store, operation=operation, attempt_now=_FIRST_ATTEMPT_AT
    )

    assert isinstance(driven, Success), driven
    assert _audit_entries(state_dir=state_dir) == (
        _module("_lpm_audit").AuditEntry(
            record_id=_RECORD_ID,
            effect_id=_module("_lpm_operation_identity")
            .effect_id(operation=operation, index=0)
            .unwrap(),
            actor="report-writer",
            operation="credential-conditional-set",
            attempted_at=_FIRST_ATTEMPT_AT,
        ),
    )
    # Stated as its own assertion rather than left implicit in the equality above: the
    # acceptance instant is precisely the value this line must NOT carry.
    assert _ACCEPTED_AT != _FIRST_ATTEMPT_AT
    assert _audit_entries(state_dir=state_dir)[0].attempted_at != _ACCEPTED_AT


def test_a_replayed_append_preserves_the_first_attempts_own_recorded_time(
    tmp_path: pathlib.Path,
) -> None:
    state_dir, store, operation = _live_report(tmp_path=tmp_path)
    first = _driven(
        state_dir=state_dir, store=store, operation=operation, attempt_now=_FIRST_ATTEMPT_AT
    )
    assert isinstance(first, Success), first

    replay = _driven(
        state_dir=state_dir, store=store, operation=operation, attempt_now=_LATER_ATTEMPT_AT
    )

    assert isinstance(replay, Success), replay
    assert replay.unwrap().performed == ()
    entries = _audit_entries(state_dir=state_dir)
    assert len(entries) == 1
    assert entries[0].attempted_at == _FIRST_ATTEMPT_AT
