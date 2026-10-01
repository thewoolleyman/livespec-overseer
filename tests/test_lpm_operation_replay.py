"""An effect that commits before its checkpoint replays as ONE logical effect.

SPECIFICATION/contracts.md requires every executor to inspect authoritative state for its
POSITION'S exact postcondition before performing it — an already-satisfied postcondition
advances `completed_step` without repeating the effect — and states the purpose outright:
"These checks MUST make an effect commit followed by a crash before `completed_step`
advancement replay as one logical effect."

THE FAULT INJECTED HERE IS EXACTLY THAT WINDOW, and it is the one this engine exists for. An
effect and its checkpoint live in two different stores, so the gap between them cannot be
closed; it is survived. The test commits position 1's effect into an authoritative world, then
fails its checkpoint, leaving the durable record one position BEHIND the world — and then
replays from disk and asserts both failure directions at once: no effect runs twice (a
duplicated contribution) and no pending effect is skipped (a lost one). Both are checked by
counting the world rather than by trusting the driver's own bookkeeping.

The two `audit-append` positions of an acquire `terminal` phase are the discriminator that
makes this test able to fail. A replay keyed on effect NAMES would find the first append's
contribution already present and mark the second one satisfied, silently losing it; the world
here is keyed on the POSITIONAL `effect_id`, so it holds two distinct append entries and a
name-keyed replay would be caught.

`accepted_at` is asserted byte-identical across every retry and phase replacement. It fixes a
tombstone's `closed_at` and a close's `normalized_close_time`, so a re-captured value would
drift those times on each retry — which is precisely the timestamp drift an idempotent
command must not have.
"""

from __future__ import annotations

import importlib
import os
import pathlib

from _lpm_results import store_unavailable

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_OPERATION_ID = "9f8c7b6a-5d4e-4f3a-8b2c-1d0e9f8a7b6c"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
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


def _replay():
    return _module("_lpm_operation_replay")


def _identity():
    return _module("_lpm_operation_identity")


def _uid() -> int:
    return os.geteuid()


def _terminal_operation(**changes: object):
    module = _module("_lpm_operation")
    fields: dict[str, object] = {
        "operation_id": _OPERATION_ID,
        "command": "acquire",
        "phase": "terminal",
        "idempotency_key": _KEY,
        "accepted_at": _ACCEPTED_AT,
        "normalized_input": {"record_id": _RECORD_ID},
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
    written = _store().write_operation(path=path, operation=_terminal_operation(), owner_uid=_uid())
    return path, written.unwrap()


# ---------------------------------------------------------------------------
# Validated, atomic persistence
# ---------------------------------------------------------------------------


def test_the_operation_path_is_the_contract_s_command_and_key_digest(tmp_path):
    paths = _module("_lpm_paths")
    state_dir = tmp_path / "state"

    resolved = (
        _store()
        .operation_path(state_dir=state_dir, command="provision", idempotency_key=_KEY)
        .unwrap()
    )

    assert (
        resolved
        == paths.local_record_path(
            state_dir=state_dir, family="operation", identity=("provision", _KEY)
        ).unwrap()
    )
    assert resolved.parent.name == "operations"


def test_an_absent_operation_record_means_no_pending_operation(tmp_path):
    path = tmp_path / "state" / "operations" / "absent.json"

    assert _store().read_operation(path=path, owner_uid=_uid()).unwrap() is None


def test_a_persisted_record_reads_back_owner_only_through_its_own_validator(tmp_path):
    path, operation = _persisted(tmp_path)

    reread = _store().read_operation(path=path, owner_uid=_uid()).unwrap()

    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert reread == operation
    assert reread.accepted_at == _ACCEPTED_AT
    assert reread.completed_step == -1


def test_a_malformed_stored_record_fails_closed_without_being_rewritten(tmp_path):
    path, _ = _persisted(tmp_path)
    path.write_text('{"version":1}', encoding="utf-8")

    refusal = _store().read_operation(path=path, owner_uid=_uid())

    assert refusal.failure().error_type == "store-unavailable"
    assert refusal.failure().message == "operation record is missing operation_id"
    assert path.read_text(encoding="utf-8") == '{"version":1}', "no reset, no mutation"


def test_an_unsafe_stored_record_is_refused_before_it_is_parsed(tmp_path):
    path, _ = _persisted(tmp_path)
    path.chmod(0o644)

    assert (
        _store()
        .read_operation(path=path, owner_uid=_uid())
        .failure()
        .message.endswith("is more broadly accessible")
    )


def test_a_record_that_would_not_read_back_is_refused_before_it_is_staged(tmp_path):
    path = (
        _store()
        .operation_path(state_dir=tmp_path / "state", command="acquire", idempotency_key=_KEY)
        .unwrap()
    )

    refusal = _store().write_operation(
        path=path, operation=_terminal_operation(phase="settling"), owner_uid=_uid()
    )

    assert refusal.failure().message == (
        "phase must be one of launch, terminal, recovery for acquire"
    )
    assert not path.exists(), "an unreadable record is worse than no record at all"


def test_a_write_onto_an_unsafe_destination_reports_the_store_as_unavailable(tmp_path):
    path, _ = _persisted(tmp_path)
    path.chmod(0o666)

    refusal = _store().write_operation(
        path=path, operation=_terminal_operation(completed_step=0), owner_uid=_uid()
    )

    assert refusal.failure().message.endswith("is more broadly accessible")


def test_a_checkpoint_must_advance_exactly_one_position(tmp_path):
    path, operation = _persisted(tmp_path)

    skipped = _store().checkpoint_step(path=path, operation=operation, step=2, owner_uid=_uid())
    backwards = _store().checkpoint_step(path=path, operation=operation, step=-1, owner_uid=_uid())
    advanced = (
        _store().checkpoint_step(path=path, operation=operation, step=0, owner_uid=_uid()).unwrap()
    )

    assert skipped.failure().error_type == "internal-bug"
    assert skipped.failure().message == "a checkpoint must advance exactly one position from -1"
    assert backwards.failure().error_type == "internal-bug"
    assert advanced.completed_step == 0
    assert _store().read_operation(path=path, owner_uid=_uid()).unwrap().completed_step == 0


def test_a_phase_replacement_is_the_same_operation_with_a_new_plan(tmp_path):
    path, operation = _persisted(tmp_path)
    terminal = _module("_lpm_operation_terminal")
    plan = _module("_lpm_operation_plan")
    effects = plan.ordered_effects_for(
        command="acquire", phase="recovery", context=plan.PlanContext()
    ).unwrap()

    replaced = (
        _store()
        .replace_phase(
            path=path,
            operation=_store()
            .checkpoint_step(path=path, operation=operation, step=0, owner_uid=_uid())
            .unwrap(),
            phase="recovery",
            ordered_effects=effects,
            terminal_result=terminal.recovery_terminal_result(command="acquire"),
            owner_uid=_uid(),
        )
        .unwrap()
    )

    assert replaced.operation_id == _OPERATION_ID, "the operation_id is retained byte-for-byte"
    assert replaced.accepted_at == _ACCEPTED_AT, "a retry reuses accepted_at; it never re-captures"
    assert replaced.normalized_input == {"record_id": _RECORD_ID}
    assert replaced.phase == "recovery"
    assert replaced.ordered_effects == effects
    assert replaced.completed_step == -1, "the replacement plan starts unstarted"
    assert replaced.terminal_result == {
        "outcome": "failure",
        "validated_at": None,
        "published_at": None,
        "expires_at": None,
        "failure_reason": "flow-unavailable",
    }
    assert _identity().effect_id(operation=replaced, index=0).unwrap() != (
        _identity().effect_id(operation=operation, index=0).unwrap()
    ), "every effect of a replaced phase carries a new identity"


def test_a_replacement_the_contract_does_not_admit_leaves_the_prior_bytes(tmp_path):
    path, operation = _persisted(tmp_path)
    before = path.read_bytes()

    refusal = _store().replace_phase(
        path=path,
        operation=operation,
        phase="recovery",
        ordered_effects=("audit-append",),
        terminal_result=dict(_TERMINAL_RESULT),
        owner_uid=_uid(),
    )

    assert refusal.failure().message == (
        "a recovery phase must carry its command's failure terminal result"
    )
    assert path.read_bytes() == before


def test_removing_a_finished_operation_is_idempotent_housekeeping(tmp_path):
    path, _ = _persisted(tmp_path)

    first = _store().remove_operation(path=path, owner_uid=_uid())
    second = _store().remove_operation(path=path, owner_uid=_uid())

    assert first.unwrap() is None
    assert second.unwrap() is None, "absence after the delete is the committed postcondition"
    assert not path.exists()


def test_an_unsafe_or_unremovable_path_is_never_unlinked(tmp_path, monkeypatch):
    localstate = _module("_lpm_localstate")
    path, _ = _persisted(tmp_path)
    path.chmod(0o666)

    unsafe = localstate.remove_local_record(path=path, owner_uid=_uid())
    path.chmod(0o600)

    def _refuse(self, **unlink_options):  # stands in for Path.unlink
        raise OSError(5, "simulated")

    monkeypatch.setattr(localstate.Path, "unlink", _refuse)
    failed = localstate.remove_local_record(path=path, owner_uid=_uid())

    assert unsafe.failure().message.endswith("is more broadly accessible")
    assert failed.failure().message.endswith("was not removed: OSError")
    assert path.exists(), "an unsafe path is evidence; removing it destroys the evidence"


# ---------------------------------------------------------------------------
# Positional replay across the effect-before-checkpoint crash window
# ---------------------------------------------------------------------------


def test_the_pending_positions_start_just_past_the_stored_checkpoint():
    replay = _replay()

    unstarted = replay.pending_positions(operation=_terminal_operation())
    resumed = replay.pending_positions(operation=_terminal_operation(completed_step=2))
    finished = replay.pending_positions(operation=_terminal_operation(completed_step=4))

    assert [position.index for position in unstarted] == [0, 1, 2, 3, 4]
    assert [position.index for position in resumed] == [3, 4]
    assert finished == ()
    assert unstarted[0].effect == "audit-append"
    assert unstarted[2].effect == "audit-append"
    assert (
        unstarted[0].effect_id != unstarted[2].effect_id
    ), "two positions holding one name must not share an identity"


def test_an_effect_that_commits_before_its_checkpoint_replays_as_one_logical_effect(tmp_path):
    replay, store = _replay(), _store()
    path, operation = _persisted(tmp_path)
    world: list[str] = []

    def _execute(position):
        if position.effect_id in world:
            return Success(replay.SATISFIED)
        world.append(position.effect_id)
        return Success(replay.PERFORMED)

    def _checkpoint(current, step):
        return store.checkpoint_step(path=path, operation=current, step=step, owner_uid=_uid())

    def _crashing_checkpoint(current, step):
        if step == 1:
            return Failure(store_unavailable(message="simulated loss before the checkpoint"))
        return _checkpoint(current, step)

    crashed = replay.replay_phase(
        operation=operation, execute=_execute, checkpoint=_crashing_checkpoint
    )
    durable = store.read_operation(path=path, owner_uid=_uid()).unwrap()

    assert crashed.failure().message == "simulated loss before the checkpoint"
    assert durable.completed_step == 0, "the record is one position BEHIND the world"
    assert len(world) == 2, "position 1's effect DID commit before the loss"

    resumed = replay.replay_phase(
        operation=durable, execute=_execute, checkpoint=_checkpoint
    ).unwrap()

    assert resumed.skipped == (1,), "the already-authoritative postcondition is not repeated"
    assert resumed.performed == (2, 3, 4), "no pending effect is skipped"
    assert resumed.operation.completed_step == 4
    assert len(world) == 5, "five positions, five contributions — no duplicate, none lost"
    assert sorted(world) == sorted(set(world))
    assert resumed.operation.accepted_at == _ACCEPTED_AT, "no timestamp drift across the retry"
    assert store.read_operation(path=path, owner_uid=_uid()).unwrap().completed_step == 4


def test_a_second_replay_of_a_finished_phase_performs_nothing_at_all(tmp_path):
    replay, store = _replay(), _store()
    path, operation = _persisted(tmp_path)
    performed: list[int] = []

    def _execute(position):
        performed.append(position.index)
        return Success(replay.PERFORMED)

    def _checkpoint(current, step):
        return store.checkpoint_step(path=path, operation=current, step=step, owner_uid=_uid())

    first = replay.replay_phase(
        operation=operation, execute=_execute, checkpoint=_checkpoint
    ).unwrap()
    again = replay.replay_phase(
        operation=first.operation, execute=_execute, checkpoint=_checkpoint
    ).unwrap()

    assert first.performed == (0, 1, 2, 3, 4)
    assert first.skipped == ()
    assert again.performed == ()
    assert again.skipped == ()
    assert performed == [0, 1, 2, 3, 4], "a finished phase re-runs nothing"


def test_a_refused_effect_stops_the_replay_and_leaves_the_checkpoint_alone(tmp_path):
    replay, store = _replay(), _store()
    path, operation = _persisted(tmp_path)

    def _refusing(position):
        if position.index == 0:
            return Success(replay.PERFORMED)
        return Failure(store_unavailable(message="the authoritative state is neither"))

    def _checkpoint(current, step):
        return store.checkpoint_step(path=path, operation=current, step=step, owner_uid=_uid())

    refusal = replay.replay_phase(operation=operation, execute=_refusing, checkpoint=_checkpoint)

    assert refusal.failure().message == "the authoritative state is neither"
    assert (
        store.read_operation(path=path, owner_uid=_uid()).unwrap().completed_step == 0
    ), "the committed position stays committed; the refused one stays pending"


def test_an_unrecognized_disposition_is_a_bug_rather_than_a_silent_advance(tmp_path):
    replay, store = _replay(), _store()
    path, operation = _persisted(tmp_path)

    def _vague(position):
        return Success("probably-fine")

    def _checkpoint(current, step):
        return store.checkpoint_step(path=path, operation=current, step=step, owner_uid=_uid())

    refusal = replay.replay_phase(operation=operation, execute=_vague, checkpoint=_checkpoint)

    assert replay.EFFECT_DISPOSITIONS == ("satisfied", "performed")
    assert refusal.failure().error_type == "internal-bug"
    assert refusal.failure().message == "probably-fine is not a ratified effect disposition"
    assert store.read_operation(path=path, owner_uid=_uid()).unwrap().completed_step == -1
