"""Release and expire close a run from the DURABLE record, never from the resuming clock.

SPECIFICATION/contracts.md states both halves. "Release `apply` against a live assignment and
expire `close` MUST contain exactly `assignment-end-update`, `lease-release`, `tombstone-create`,
`assignment-close`"; "For report, complete or release, `assignment-end-update` MUST conditionally
set `actual_lease_ended_at` to the operation's defined `normalized_close_time`; for expire it MUST
use `lease_expires_at`"; and a tombstone's "`closed_at` MUST equal the operation's stored
`accepted_at` for report, complete or release and MUST equal `lease_expires_at` for expire".
"Every retry MUST reuse `accepted_at`."

THE PHASE IS RESUMED, NOT RE-DRIVEN FROM A HELD RECORD. `resume_phase` reads the write-ahead
record off disk rather than being handed one, which is exactly the difference a crash makes and
the only difference it makes. A test that passed the record in would prove the arithmetic and
nothing about where the inputs came from — and "the inputs came from somewhere else" is the whole
failure mode: a resuming process that sampled its own clock would date the close from the
recovery rather than from the acceptance.

THE TWO COMMANDS ARE DELIBERATELY GIVEN THE SAME FIXTURE AND MUST DISAGREE. Both operations are
accepted well AFTER the lease expired, which is the contract's "Run closure clamps a lease that
expires during global recovery" case. Release then clamps its lease end to `lease_expires_at`
while recording the later `accepted_at` as `closed_at`; expire records `lease_expires_at` for
BOTH. An implementation that reached for the acceptance time in expire's closing instant — the
natural shape, since every other closing command does — produces release's answer for expire, and
only the two side by side catch it.

THE CRASH ARC IS DRIVEN THROUGH A REAL CHECKPOINT, not a second clean pass. The durable record is
advanced to the position a crash would have left it at, with the assignment carrying the end its
first pass wrote, and the resume finishes from there. The tombstone it produces must be
BYTE-IDENTICAL to the one an uninterrupted pass produced, which is the property every stored-value
derivation exists to give.
"""

from __future__ import annotations

import importlib
import os
import pathlib

from overseer._vendor.returns.result import Success

__all__: list[str] = []

_RELEASE_OPERATION_ID = "2f6c81b4-7d39-4a52-8e07-b3f1c9d5a648"
_EXPIRE_OPERATION_ID = "8b0d5e37-1c42-4f96-a5d8-0e7b2a4c6139"
_RELEASE_KEY = "1" * 64
_EXPIRE_KEY = "2" * 64
_ACCEPTED_AT = "2026-10-05T18:00:00Z"
_RUN_ID = "run-release-one"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_TARGET_REF = "ref-release-2e8a"
_ACCOUNT = "acct-primary"
_VALUE_REF = "op://llm-provider-manager-token-values/3f2504e0-gen/credential"
_LEASE_STARTED_AT = "2026-10-05T11:00:00Z"
_LEASE_EXPIRES_AT = "2026-10-05T13:00:00Z"
_COMMITTED_AT = "2026-10-05T11:00:05Z"

_CLOSE_APPLY = (
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
    state_dir.mkdir(mode=0o700, parents=True)
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
    """A FRESH engine over the same state directory — one resuming process's whole world."""
    return _module("_lpm_engine_context").OperationEngine(
        state_dir=state_dir,
        owner_uid=os.getuid(),
        store=_module("_lpm_store").InMemorySecretStore(),
    )


def _release_operation(*, completed_step: int = -1):
    return _module("_lpm_operation").OperationRecord(
        operation_id=_RELEASE_OPERATION_ID,
        command="release",
        phase="apply",
        idempotency_key=_RELEASE_KEY,
        accepted_at=_ACCEPTED_AT,
        normalized_input={"version": 1, "consumer_run_id": _RUN_ID, "record_id": _RECORD_ID},
        terminal_result=None,
        ordered_effects=_CLOSE_APPLY,
        completed_step=completed_step,
    )


def _expire_operation():
    return _module("_lpm_operation").OperationRecord(
        operation_id=_EXPIRE_OPERATION_ID,
        command="expire",
        phase="close",
        idempotency_key=_EXPIRE_KEY,
        accepted_at=_ACCEPTED_AT,
        normalized_input={"consumer_run_id": _RUN_ID, "record_id": _RECORD_ID},
        terminal_result=None,
        ordered_effects=_CLOSE_APPLY,
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


def _bound(*, tmp_path: pathlib.Path, assignment: dict[str, object] | None = None):
    state_dir = _state(tmp_path=tmp_path)
    _seed(
        path=_family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)),
        value=_assignment() if assignment is None else assignment,
    )
    _seed(
        path=_family_path(state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT)),
        value=_lease(),
    )
    return state_dir


def _resumed(*, state_dir: pathlib.Path, command: str, key: str):
    return _module("_lpm_engine").resume_phase(
        engine=_engine(state_dir=state_dir),
        command=command,
        idempotency_key=key,
        inputs=_module("_lpm_engine_context").EffectInputs(),
    )


def _tombstone_of(*, state_dir: pathlib.Path) -> dict[str, object]:
    stored = _read(path=_family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,)))
    assert isinstance(stored, dict)
    return stored


def test_a_resumed_release_clamps_its_lease_end_and_keeps_its_accepted_closing_instant(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _bound(tmp_path=tmp_path)
    _persisted(state_dir=state_dir, operation=_release_operation())

    resumed = _resumed(state_dir=state_dir, command="release", key=_RELEASE_KEY)

    assert isinstance(resumed, Success), resumed
    assert resumed.unwrap().performed == (0, 1, 2, 3)
    closed = _tombstone_of(state_dir=state_dir)
    assert closed["actual_lease_ended_at"] == _LEASE_EXPIRES_AT
    assert closed["closed_at"] == _ACCEPTED_AT
    assert not _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)).exists()
    assert not _family_path(
        state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT)
    ).exists()


def test_a_resumed_expiry_closes_at_the_recorded_lease_expiry_not_the_recovery_clock(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _bound(tmp_path=tmp_path)
    _persisted(state_dir=state_dir, operation=_expire_operation())

    resumed = _resumed(state_dir=state_dir, command="expire", key=_EXPIRE_KEY)

    assert isinstance(resumed, Success), resumed
    closed = _tombstone_of(state_dir=state_dir)
    assert closed["actual_lease_ended_at"] == _LEASE_EXPIRES_AT
    assert closed["closed_at"] == _LEASE_EXPIRES_AT
    assert closed["closed_at"] != _ACCEPTED_AT, "expiry must not date its close from acceptance"


def test_a_release_resumed_past_its_first_position_lands_the_identical_tombstone(
    tmp_path: pathlib.Path,
) -> None:
    uninterrupted = _bound(tmp_path=tmp_path / "clean")
    _persisted(state_dir=uninterrupted, operation=_release_operation())
    first = _resumed(state_dir=uninterrupted, command="release", key=_RELEASE_KEY)
    assert isinstance(first, Success), first
    expected = _family_path(
        state_dir=uninterrupted, family="tombstone", identity=(_RUN_ID,)
    ).read_bytes()

    interrupted = _bound(
        tmp_path=tmp_path / "crashed",
        assignment=_assignment(actual_lease_ended_at=_LEASE_EXPIRES_AT),
    )
    _persisted(state_dir=interrupted, operation=_release_operation(completed_step=0))
    resumed = _resumed(state_dir=interrupted, command="release", key=_RELEASE_KEY)

    assert isinstance(resumed, Success), resumed
    assert resumed.unwrap().performed == (1, 2, 3)
    assert (
        _family_path(state_dir=interrupted, family="tombstone", identity=(_RUN_ID,)).read_bytes()
        == expected
    )


def test_resuming_a_command_with_no_durable_record_is_refused_rather_than_invented(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _bound(tmp_path=tmp_path)

    resumed = _resumed(state_dir=state_dir, command="release", key=_RELEASE_KEY)

    assert not isinstance(resumed, Success)
    assert resumed.failure().error_type == "store-unavailable"
    assert "no pending release operation to resume" in resumed.failure().message
    assert _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)).exists()
