"""The three completed no-ops a report's audited pair owes, and the markers that survive them.

SPECIFICATION/contracts.md fixes all three. "The credential effect and its paired audit MUST be
completed no-ops for `unknown`, a replaced generation, or a matching generation whose credential
is already `suspect`, `dead` or `reacquiring`... so the persisted array never depends on that
outcome." For a replaced generation "the manager MUST accept the report and release any live
lease but MUST NOT change or invalidate the replacement credential's lifecycle or cache entry",
and `unknown` "MUST leave lifecycle status unchanged and release any live lease". A repeat is
recognized by the stored `(occurred_at, classification)` pair, and "the stored-marker duplicate
rule prevents every one of those effects from running again".

A NO-OP IS NOT A SHORTER PHASE, AND THAT IS THE LOAD-BEARING HALF. The array stays eight effects
long in every case; what changes is that two POSITIONS settle. So each exercise asserts the
positional dispositions — which indices were performed and which were skipped — as well as the
state: an engine that planned a shorter array for a no-op would produce the same files and a
different, unreplayable record.

THE EVIDENCE OF A NO-OP IS AN ABSENCE, SO IT IS ASSERTED AS ONE. No audit line may exist, because
the log attests adapter calls that were ACTUALLY attempted and is append-only; and the credential
chain must still hold exactly one revision, because a second one would be a lifecycle move no
report authorized. Asserting only that the phase succeeded would pass against an engine that
suspected a replacement credential the reporting run never used.

THE TERMINAL-LIFECYCLE CASE IS DRIVEN FOR ALL THREE STATES, not one representative. `suspect`,
`dead` and `reacquiring` reach the no-op through three different absent rows of the lifecycle
table, and a transition table that had gained a `(dead, consumer-failure-report)` row would still
pass a test that only tried `suspect`.

THE MARKER IS NOT PART OF THE NO-OP. Every one of these reports is ACCEPTED: its marker is
inserted in canonical order, its lease is released and its run is closed. A second report at an
EARLIER instant then has to land ahead of the first in the stored array, which is what proves the
insert is a re-sort rather than an append.
"""

from __future__ import annotations

import importlib
import os
import pathlib

import pytest

from overseer._vendor.returns.result import Success

__all__: list[str] = []

_OPERATION_ID = "6e4f1a82-3b57-4c90-8d21-7f0a9c5b3e64"
_SECOND_OPERATION_ID = "0a9b7c62-5d14-4e38-91f6-2b8d4a0c7e53"
_KEY = "3" * 64
_SECOND_KEY = "4" * 64
_ACCEPTED_AT = "2026-10-05T14:00:00Z"
_RUN_ID = "run-no-op-one"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_REPLACEMENT_GENERATION = "16fd2706-8baf-433b-82eb-8c7fada847da"
_TARGET_REF = "ref-no-op-6a31"
_ACCOUNT = "acct-primary"
_VALUE_REF = "op://llm-provider-manager-token-values/3f2504e0-gen/credential"
_LEASE_STARTED_AT = "2026-10-05T11:00:00Z"
_LEASE_EXPIRES_AT = "2026-10-05T13:00:00Z"
_COMMITTED_AT = "2026-10-05T11:00:05Z"
_NORMALIZED_CLOSE_AT = "2026-10-05T13:00:00Z"
_OCCURRED_AT = "2026-10-05T11:30:00Z"
_EARLIER_OCCURRED_AT = "2026-10-05T11:10:00Z"
_SEED_EFFECT_ID = "5" * 64

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
_TERMINAL_STATUSES = ("suspect", "dead", "reacquiring")


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


def _report_input(**changes: object) -> dict[str, object]:
    source: dict[str, object] = {
        "version": 1,
        "consumer_run_id": _RUN_ID,
        "record_id": _RECORD_ID,
        "occurred_at": _OCCURRED_AT,
        "classification": "authentication",
    }
    source.update(changes)
    return source


def _credential(**changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "version": 1,
        "record_id": _RECORD_ID,
        "provider": "anthropic",
        "account_id": _ACCOUNT,
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": "2026-10-05T10:00:00Z",
        "expires_at": None,
        "last_validated": "2026-10-05T10:30:00Z",
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


def _marker(*, occurred_at: str, classification: str) -> dict[str, str]:
    return {"occurred_at": occurred_at, "classification": classification}


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


def _seeded_store(*, record: dict[str, object]):
    store_module = _module("_lpm_store")
    store = store_module.InMemorySecretStore()
    encoded = _module("_lpm_canonical").canonical_json_text(value=record)
    assert isinstance(encoded, Success), encoded
    committed = store.credential_conditional_set(
        request=store_module.ConditionalSet(
            record_id=_RECORD_ID,
            effect_id=_SEED_EFFECT_ID,
            expected_record=None,
            desired_record=encoded.unwrap(),
        )
    )
    assert committed["status"] == "committed", committed
    return store


def _current_status(*, store) -> object:
    result = store.metadata_get(record_id=_RECORD_ID)
    assert result["status"] == "ok", result
    item = result["item"]
    assert isinstance(item, dict)
    parsed = _module("_lpm_canonical").parse_canonical_json(text=item["record"])
    assert isinstance(parsed, Success), parsed
    held = parsed.unwrap()
    assert isinstance(held, dict)
    return held["status"]


def _operation(
    *,
    effects: tuple[str, ...],
    normalized_input: dict[str, object] | None = None,
    operation_id: str = _OPERATION_ID,
    key: str = _KEY,
):
    return _module("_lpm_operation").OperationRecord(
        operation_id=operation_id,
        command="report",
        phase="apply",
        idempotency_key=key,
        accepted_at=_ACCEPTED_AT,
        normalized_input=_report_input() if normalized_input is None else normalized_input,
        terminal_result=None,
        ordered_effects=effects,
        completed_step=-1,
    )


def _driven(*, state_dir: pathlib.Path, store, operation):
    context_module = _module("_lpm_engine_context")
    return _module("_lpm_engine").drive_phase(
        engine=context_module.OperationEngine(
            state_dir=state_dir, owner_uid=os.getuid(), store=store
        ),
        operation=operation,
        inputs=context_module.EffectInputs(),
    )


def _live(*, tmp_path: pathlib.Path, assignment: dict[str, object] | None = None):
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


def _assert_audited_pair_settled(*, state_dir: pathlib.Path, store, driven) -> None:
    assert isinstance(driven, Success), driven
    assert driven.unwrap().skipped == (0, 1, 2)
    assert driven.unwrap().performed == (3, 4, 5, 6, 7)
    assert not (state_dir / _module("_lpm_paths").AUDIT_LOG_NAME).exists()
    assert len(store.items[_RECORD_ID]) == 1
    assert not _family_path(
        state_dir=state_dir, family="pending-metadata-effect", identity=(_RECORD_ID,)
    ).exists()


def _assert_report_accepted(*, state_dir: pathlib.Path, classification: str) -> None:
    assert _read(
        path=_family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,))
    ) == _tombstone(
        report_markers=[_marker(occurred_at=_OCCURRED_AT, classification=classification)]
    )
    assert not _family_path(state_dir=state_dir, family="assignment", identity=(_RUN_ID,)).exists()
    assert not _family_path(
        state_dir=state_dir, family="lease", identity=("anthropic", _ACCOUNT)
    ).exists()


def test_an_unknown_report_leaves_the_lifecycle_alone_and_still_closes_the_run(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _live(tmp_path=tmp_path)
    store = _seeded_store(record=_credential())

    driven = _driven(
        state_dir=state_dir,
        store=store,
        operation=_operation(
            effects=_LIVE_APPLY, normalized_input=_report_input(classification="unknown")
        ),
    )

    _assert_audited_pair_settled(state_dir=state_dir, store=store, driven=driven)
    assert _current_status(store=store) == "valid"
    _assert_report_accepted(state_dir=state_dir, classification="unknown")


def test_a_replaced_generation_leaves_the_replacement_credential_untouched(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _live(tmp_path=tmp_path)
    store = _seeded_store(record=_credential(value_generation=_REPLACEMENT_GENERATION))

    driven = _driven(state_dir=state_dir, store=store, operation=_operation(effects=_LIVE_APPLY))

    _assert_audited_pair_settled(state_dir=state_dir, store=store, driven=driven)
    assert _current_status(store=store) == "valid"
    _assert_report_accepted(state_dir=state_dir, classification="authentication")


@pytest.mark.parametrize("status", _TERMINAL_STATUSES)
def test_a_terminal_lifecycle_record_makes_the_audited_pair_a_completed_no_op(
    tmp_path: pathlib.Path, status: str
) -> None:
    state_dir = _live(tmp_path=tmp_path)
    store = _seeded_store(record=_credential(status=status))

    driven = _driven(state_dir=state_dir, store=store, operation=_operation(effects=_LIVE_APPLY))

    _assert_audited_pair_settled(state_dir=state_dir, store=store, driven=driven)
    assert _current_status(store=store) == status
    _assert_report_accepted(state_dir=state_dir, classification="authentication")


def test_a_repeated_report_against_the_tombstone_rewrites_nothing_at_all(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _state(tmp_path=tmp_path)
    tombstone_path = _family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,))
    _seed(
        path=tombstone_path,
        value=_tombstone(
            report_markers=[_marker(occurred_at=_OCCURRED_AT, classification="authentication")]
        ),
    )
    store = _seeded_store(record=_credential())
    untouched = tombstone_path.read_bytes()

    driven = _driven(
        state_dir=state_dir, store=store, operation=_operation(effects=_TOMBSTONE_APPLY)
    )

    assert isinstance(driven, Success), driven
    assert driven.unwrap().performed == ()
    assert driven.unwrap().skipped == (0, 1, 2, 3)
    assert tombstone_path.read_bytes() == untouched
    assert not (state_dir / _module("_lpm_paths").AUDIT_LOG_NAME).exists()
    assert len(store.items[_RECORD_ID]) == 1


def test_a_second_earlier_report_lands_ahead_of_the_stored_one_in_canonical_order(
    tmp_path: pathlib.Path,
) -> None:
    state_dir = _live(tmp_path=tmp_path)
    store = _seeded_store(record=_credential())
    first = _driven(state_dir=state_dir, store=store, operation=_operation(effects=_LIVE_APPLY))
    assert isinstance(first, Success), first

    second = _driven(
        state_dir=state_dir,
        store=store,
        operation=_operation(
            effects=_TOMBSTONE_APPLY,
            normalized_input=_report_input(
                occurred_at=_EARLIER_OCCURRED_AT, classification="rate-limit"
            ),
            operation_id=_SECOND_OPERATION_ID,
            key=_SECOND_KEY,
        ),
    )

    assert isinstance(second, Success), second
    closed = _read(path=_family_path(state_dir=state_dir, family="tombstone", identity=(_RUN_ID,)))
    assert isinstance(closed, dict)
    assert closed["report_markers"] == [
        _marker(occurred_at=_EARLIER_OCCURRED_AT, classification="rate-limit"),
        _marker(occurred_at=_OCCURRED_AT, classification="authentication"),
    ]
    assert _current_status(store=store) == "suspect"
    assert len(store.items[_RECORD_ID]) == 2
