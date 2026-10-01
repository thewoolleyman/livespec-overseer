"""No public path installs a phase the contract does not reach, or drops a pending effect.

SPECIFICATION/contracts.md lets a phase transition happen only on a condition the contract
states — a `launch` becomes `terminal` when its worker persisted an outcome and `recovery` when
the worker was lost; a provision `start` becomes `postcommit` after a committed target and
`cleanup` after a pre-commit failure — and requires the replacement to install THAT PHASE'S
COMPLETE effect array while resetting `completed_step` to `-1`. Removal is terminal housekeeping
permitted only after every ordered effect commits, and is not itself an effect.

THE HOLE THIS CLOSES WAS REAL AND IT WAS MINE. An earlier shape of this store took `phase` and
`ordered_effects` as arguments, which made every rule above a convention the caller was trusted
to follow: nothing stopped a caller rewriting a terminal-success operation into any phase it
liked with any array it liked, and nothing stopped it removing a record whose plan still had
pending effects — silently discarding exactly the effects a later replay would have performed.
The surface now takes a CONDITION. The transition table picks the phase, the plan tables pick
that phase's array, and `finish_operation` refuses an unfinished plan, so those are structural
rather than documented.

TWO REFUSALS ARE ASSERTED THAT A HAPPY-PATH TEST WOULD NOT REACH. A condition the table does not
state for the current phase is refused with the prior bytes intact; and a condition that WOULD
reach a phase the command does not have — the table is keyed on phase and condition, not on
command — is refused by the plan tables rather than written. Both leave the record exactly as
found, because a half-applied transition is the one state a write-ahead record must never be in.
"""

from __future__ import annotations

import importlib
import os
import pathlib

__all__: list[str] = []

_OPERATION_ID = "9f8c7b6a-5d4e-4f3a-8b2c-1d0e9f8a7b6c"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_NEXT_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_KEY = "c" * 64
_ACCEPTED_AT = "2026-09-30T18:30:00Z"

_TERMINAL_EFFECTS = (
    "audit-append",
    "secret-value-set",
    "audit-append",
    "credential-conditional-set",
    "worker-record-remove",
)
_TERMINAL_RESULT: dict[str, object] = {
    "outcome": "success",
    "validated_at": "2026-09-30T18:30:04Z",
    "published_at": "2026-09-30T18:30:06Z",
    "expires_at": None,
    "failure_reason": None,
}


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _store():
    return _module("_lpm_operation_store")


def _plan():
    return _module("_lpm_operation_plan")


def _uid() -> int:
    return os.geteuid()


def _acquire_input() -> dict[str, object]:
    return {
        "version": 1,
        "provider": "anthropic",
        "account_id": "acct-1",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "record_id": _RECORD_ID,
        "next_value_generation": _NEXT_GENERATION,
    }


def _operation(**changes: object):
    module = _module("_lpm_operation")
    fields: dict[str, object] = {
        "operation_id": _OPERATION_ID,
        "command": "acquire",
        "phase": "terminal",
        "idempotency_key": _KEY,
        "accepted_at": _ACCEPTED_AT,
        "normalized_input": _acquire_input(),
        "terminal_result": dict(_TERMINAL_RESULT),
        "ordered_effects": _TERMINAL_EFFECTS,
        "completed_step": module.UNSTARTED_STEP,
    }
    fields.update(changes)
    return module.OperationRecord(**fields)  # pyright: ignore[reportArgumentType]


def _persisted(tmp_path: pathlib.Path):
    path = (
        _store()
        .operation_path(state_dir=tmp_path / "state", command="acquire", idempotency_key=_KEY)
        .unwrap()
    )
    written = _store().write_operation(path=path, operation=_operation(), owner_uid=_uid())
    return path, written.unwrap()


def _completed(*, path: pathlib.Path, operation):
    current = operation
    for step in range(len(operation.ordered_effects)):
        current = (
            _store()
            .checkpoint_step(path=path, operation=current, step=step, owner_uid=_uid())
            .unwrap()
        )
    return current


def test_a_transition_names_a_condition_and_never_a_phase_or_an_effect_array(tmp_path):
    path, operation = _persisted(tmp_path)
    terminal = _module("_lpm_operation_terminal")
    at_zero = (
        _store().checkpoint_step(path=path, operation=operation, step=0, owner_uid=_uid()).unwrap()
    )

    replaced = (
        _store()
        .transition_operation(
            path=path,
            operation=at_zero,
            condition="terminal-success-rewrite",
            context=_plan().PlanContext(),
            terminal_result=terminal.recovery_terminal_result(command="acquire"),
            owner_uid=_uid(),
        )
        .unwrap()
    )

    assert replaced.phase == "recovery", "the TABLE chose the phase; the caller named a condition"
    assert replaced.ordered_effects == (
        "audit-append",
        "credential-conditional-set",
        "worker-record-remove",
    ), "the plan chose the array; the caller supplied none"
    assert replaced.completed_step == -1, "the replacement plan starts unstarted"
    assert replaced.operation_id == _OPERATION_ID, "the operation_id is retained byte-for-byte"
    assert replaced.accepted_at == _ACCEPTED_AT, "a retry reuses accepted_at; it never re-captures"
    assert replaced.normalized_input == _acquire_input()
    assert replaced.terminal_result == {
        "outcome": "failure",
        "validated_at": None,
        "published_at": None,
        "expires_at": None,
        "failure_reason": "flow-unavailable",
    }
    assert _store().read_operation(path=path, owner_uid=_uid()).unwrap() == replaced


def test_the_provision_start_transitions_pick_their_phase_from_the_condition(tmp_path):
    store, plan = _store(), _plan()
    provision_input: dict[str, object] = {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "consumer_run_id": "run-7",
        "target_ref": "ref-7",
        "strategy": "consume-first",
        "lease_seconds": 21600,
    }
    start = _operation(
        command="provision",
        phase="start",
        normalized_input=provision_input,
        terminal_result=None,
        ordered_effects=("lease-create", "prepared-assignment-create", "target-write"),
    )
    path = store.operation_path(
        state_dir=tmp_path / "state", command="provision", idempotency_key=_KEY
    ).unwrap()
    _ = store.write_operation(path=path, operation=start, owner_uid=_uid()).unwrap()

    committed = store.transition_operation(
        path=path,
        operation=start,
        condition="target-committed",
        context=plan.PlanContext(),
        terminal_result=None,
        owner_uid=_uid(),
    ).unwrap()
    failed = store.transition_operation(
        path=path,
        operation=start,
        condition="pre-commit-failure",
        context=plan.PlanContext(prepared_state_exists=True),
        terminal_result=None,
        owner_uid=_uid(),
    ).unwrap()

    assert committed.phase == "postcommit"
    assert committed.ordered_effects == ("assignment-commit", "selection-update", "proof-update")
    assert failed.phase == "cleanup"
    assert failed.ordered_effects == (
        "prepared-assignment-discard",
        "lease-release",
    ), "the authoritative prepared-state fact selects the array; the caller still names no array"


def test_no_public_path_can_install_a_transition_the_contract_does_not_reach(tmp_path):
    path, operation = _persisted(tmp_path)
    before = path.read_bytes()

    unreachable = _store().transition_operation(
        path=path,
        operation=operation,
        condition="target-committed",
        context=_plan().PlanContext(),
        terminal_result=None,
        owner_uid=_uid(),
    )
    foreign_phase = _store().transition_operation(
        path=path,
        operation=_operation(command="target", phase="launch", terminal_result=None),
        condition="worker-terminal",
        context=_plan().PlanContext(),
        terminal_result=None,
        owner_uid=_uid(),
    )

    assert unreachable.failure().message == (
        "no ratified transition from terminal under target-committed"
    )
    assert (
        foreign_phase.failure().message == "the only phase here is issue, not terminal"
    ), "the table is keyed on phase and condition, so the PLAN refuses a phase the command lacks"
    assert path.read_bytes() == before, "a half-applied transition is the one forbidden state"


def test_a_transition_whose_terminal_result_the_phase_forbids_leaves_the_prior_bytes(tmp_path):
    path, operation = _persisted(tmp_path)
    before = path.read_bytes()

    refusal = _store().transition_operation(
        path=path,
        operation=operation,
        condition="terminal-success-rewrite",
        context=_plan().PlanContext(),
        terminal_result=dict(_TERMINAL_RESULT),
        owner_uid=_uid(),
    )

    assert refusal.failure().message == (
        "a recovery phase must carry its command's failure terminal result"
    )
    assert path.read_bytes() == before


def test_an_operation_is_removable_only_once_every_ordered_effect_commits(tmp_path):
    store = _store()
    path, operation = _persisted(tmp_path)

    unfinished = store.finish_operation(path=path, operation=operation, owner_uid=_uid())
    standing = path.read_bytes()
    complete = _completed(path=path, operation=operation)
    first = store.finish_operation(path=path, operation=complete, owner_uid=_uid())
    second = store.finish_operation(path=path, operation=complete, owner_uid=_uid())

    assert unfinished.failure().error_type == "internal-bug"
    assert unfinished.failure().message == (
        "an operation is removable only once every ordered effect commits; "
        "completed_step is -1 of 4"
    )
    assert standing, "an unfinished plan is never discarded"
    assert first.unwrap() is None
    assert second.unwrap() is None, "absence after the delete is the committed postcondition"
    assert not path.exists()


def test_the_every_effect_committed_transition_finishes_rather_than_rewrites(tmp_path):
    store = _store()
    path, operation = _persisted(tmp_path)
    complete = _completed(path=path, operation=operation)

    finished = store.transition_operation(
        path=path,
        operation=complete,
        condition="every-effect-committed",
        context=_plan().PlanContext(),
        terminal_result=None,
        owner_uid=_uid(),
    )

    assert finished.unwrap() is None, "no next phase means terminal housekeeping, not a rewrite"
    assert not path.exists()


def test_even_the_finishing_transition_goes_through_the_finished_plan_precondition(tmp_path):
    store = _store()
    path, operation = _persisted(tmp_path)

    premature = store.transition_operation(
        path=path,
        operation=operation,
        condition="every-effect-committed",
        context=_plan().PlanContext(),
        terminal_result=None,
        owner_uid=_uid(),
    )

    assert premature.failure().error_type == "internal-bug"
    assert premature.failure().message.startswith(
        "an operation is removable only once every ordered effect commits"
    )
    assert path.exists(), "the pending effects a later replay would perform are still there"
