"""Consume-first is the default; spread hands simultaneous runs distinct accounts.

SPECIFICATION/spec.md makes `consume-first` the factory default — retaining one incumbent per
provider, kind and purpose, reusing it while eligible and unleased, and otherwise taking the
eligible record with the lexically smallest `record_id` — and makes the explicit `spread` strategy
take the least recently assigned, with a never-assigned record sorting before every assigned one.

SPECIFICATION/contracts.md then fixes the commit write-back: the assignment time becomes the LATER
of the stored value and this commit's `target_committed_at`, a `consume-first` commit replaces its
incumbent only when the `(target_committed_at, record_id)` tuple is lexically later, and a
`spread` commit leaves every incumbent alone. Those "later of" rules are what make a delayed post-
commit replay idempotent AND monotonic instead of walking selection state backwards onto an
account a newer run already took.

The simultaneous-spread property is composed rather than special-cased: run A's lease makes
its account ineligible to run B through the lease AXIS, so the second selection simply has a
different eligible set. These tests drive it that way.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_FIRST = "1f2504e0-4f89-41d3-9a0c-0305e82c3301"
_SECOND = "3c9e6679-7425-40de-944b-e07fc1f90ae7"
_THIRD = "8a7b6c5d-4e3f-42a1-8b9c-0d1e2f3a4b5c"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_strategy.py"
    assert module_path.is_file(), "overseer/_lpm_strategy.py must exist"
    return (
        importlib.import_module("_lpm_strategy"),
        importlib.import_module("_lpm_selection_state"),
        importlib.import_module("_lpm_eligibility"),
        importlib.import_module("_lpm_record"),
    )


def _request(eligibility, **changes):
    fields = {"provider": "anthropic", "kind": "claude-code-oauth", "purpose": "factory"}
    fields.update(changes)
    return eligibility.SelectionRequest(**fields)


def _record(records, record_id, **changes):
    fields = {
        "record_id": record_id,
        "provider": "anthropic",
        "account_id": f"{record_id[:4]}@example.test",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": "2026-09-12T09:00:00Z",
        "expires_at": None,
        "last_validated": "2026-09-12T09:58:00Z",
        "value_generation": _GENERATION,
        "value_ref": f"op://provisionable/{record_id}/value#{_GENERATION}",
        "previous_value_ref": None,
    }
    fields.update(changes)
    return records.CredentialRecord(**fields)


def _state(selection, *, incumbent=None, assignments=()):
    incumbents = () if incumbent is None else (incumbent,)
    return selection.SelectionState(
        incumbents=incumbents,
        last_assignments=tuple(
            selection.LastAssignment(record_id=record_id, assigned_at=assigned_at)
            for record_id, assigned_at in assignments
        ),
    )


def _incumbent(selection, record_id, *, committed_at="2026-09-12T09:00:00Z", purpose="factory"):
    return selection.Incumbent(
        provider="anthropic",
        kind="claude-code-oauth",
        purpose=purpose,
        record_id=record_id,
        target_committed_at=committed_at,
    )


def test_consume_first_is_the_default_and_spread_must_be_asked_for_explicitly():
    strategy, _, _, _ = _modules()

    assert strategy.DEFAULT_SELECTION_STRATEGY == "consume-first"
    assert strategy.SELECTION_STRATEGIES == ("consume-first", "spread")
    assert strategy.strategy_field(value=None).unwrap() == "consume-first"
    assert strategy.strategy_field(value="spread").unwrap() == "spread"
    assert strategy.strategy_field(value="round-robin").failure().error_type == "invalid-request"
    assert strategy.strategy_field(value=1).failure().message == (
        "strategy must be one of: consume-first, spread"
    )


def test_consume_first_keeps_its_incumbent_and_otherwise_takes_the_smallest_record_id():
    strategy, selection, eligibility, records = _modules()
    pool = (_record(records, _FIRST), _record(records, _SECOND), _record(records, _THIRD))
    retained = _state(selection, incumbent=_incumbent(selection, _SECOND))

    ordered = strategy.ordered_candidates(
        strategy="consume-first", request=_request(eligibility), records=pool, state=retained
    ).unwrap()

    assert [record.record_id for record in ordered] == [_SECOND, _FIRST, _THIRD]
    fresh = strategy.ordered_candidates(
        strategy="consume-first",
        request=_request(eligibility),
        records=pool,
        state=_state(selection),
    ).unwrap()
    assert [record.record_id for record in fresh] == [_FIRST, _SECOND, _THIRD]


def test_an_ineligible_incumbent_cannot_be_resurrected_because_it_is_not_in_the_pool():
    strategy, selection, eligibility, records = _modules()
    retained = _state(selection, incumbent=_incumbent(selection, _SECOND))

    chosen = strategy.select_record(
        strategy="consume-first",
        request=_request(eligibility),
        records=(_record(records, _THIRD), _record(records, _FIRST)),
        state=retained,
    )

    assert chosen.unwrap().record_id == _FIRST
    assert strategy.incumbent_for(state=retained, request=_request(eligibility)).record_id == (
        _SECOND
    )
    assert (
        strategy.incumbent_for(state=retained, request=_request(eligibility, purpose="interactive"))
        is None
    )


def test_spread_takes_the_least_recently_assigned_and_a_never_assigned_record_first():
    strategy, selection, eligibility, records = _modules()
    pool = (_record(records, _FIRST), _record(records, _SECOND), _record(records, _THIRD))
    history = _state(
        selection,
        assignments=(
            (_FIRST, "2026-09-12T09:30:00Z"),
            (_SECOND, "2026-09-12T09:10:00Z"),
        ),
    )

    ordered = strategy.ordered_candidates(
        strategy="spread", request=_request(eligibility), records=pool, state=history
    ).unwrap()

    assert [record.record_id for record in ordered] == [_THIRD, _SECOND, _FIRST]
    assert strategy.assignment_times(state=history) == {
        _FIRST: "2026-09-12T09:30:00Z",
        _SECOND: "2026-09-12T09:10:00Z",
    }


def test_two_simultaneous_runs_under_spread_receive_distinct_eligible_accounts():
    strategy, selection, eligibility, records = _modules()
    pool = (_record(records, _FIRST), _record(records, _SECOND))
    policy = eligibility.EligibilityPolicy(
        now="2026-09-12T10:00:00Z",
        maximum_validation_age_seconds=300,
        health_strategy="none",
        health_floor_percent=10,
        account_reservations={},
    )

    first_run = strategy.select_record(
        strategy="spread",
        request=_request(eligibility),
        records=eligibility.eligible_records(
            request=_request(eligibility), records=pool, observations={}, policy=policy
        ),
        state=_state(selection),
    ).unwrap()
    second_run = strategy.select_record(
        strategy="spread",
        request=_request(eligibility),
        records=eligibility.eligible_records(
            request=_request(eligibility),
            records=pool,
            observations={first_run.account_id: eligibility.AccountObservation(leased=True)},
            policy=policy,
        ),
        state=_state(selection),
    ).unwrap()

    assert first_run.record_id == _FIRST
    assert second_run.record_id == _SECOND
    assert second_run.account_id != first_run.account_id


def test_an_exhausted_pool_returns_typed_retryable_exhaustion_and_an_unknown_strategy_is_a_bug():
    strategy, selection, eligibility, records = _modules()

    exhausted = strategy.select_record(
        strategy="consume-first",
        request=_request(eligibility),
        records=(),
        state=_state(selection),
    )
    unregistered = strategy.select_record(
        strategy="least-used",
        request=_request(eligibility),
        records=(_record(records, _FIRST),),
        state=_state(selection),
    )

    assert exhausted.failure().error_type == "retryable-exhaustion"
    assert exhausted.failure().message == (
        "no eligible unleased credential for provider anthropic, "
        "kind claude-code-oauth, purpose factory"
    )
    assert unregistered.failure().error_type == "internal-bug"
    assert unregistered.failure().message == "unregistered selection strategy: least-used"


def test_a_commit_takes_the_later_assignment_time_so_a_delayed_replay_cannot_regress_it():
    strategy, selection, eligibility, _ = _modules()
    history = _state(selection, assignments=((_FIRST, "2026-09-12T12:00:00Z"),))

    replayed = strategy.committed_selection_state(
        state=history,
        strategy="spread",
        request=_request(eligibility),
        record_id=_FIRST,
        target_committed_at="2026-09-12T11:00:00Z",
    ).unwrap()
    advanced = strategy.committed_selection_state(
        state=history,
        strategy="spread",
        request=_request(eligibility),
        record_id=_SECOND,
        target_committed_at="2026-09-12T13:00:00Z",
    ).unwrap()

    assert strategy.assignment_times(state=replayed) == {_FIRST: "2026-09-12T12:00:00Z"}
    assert strategy.assignment_times(state=advanced) == {
        _FIRST: "2026-09-12T12:00:00Z",
        _SECOND: "2026-09-12T13:00:00Z",
    }
    assert replayed.incumbents == (), "a spread commit leaves every incumbent unchanged"


def test_a_consume_first_commit_moves_its_incumbent_only_for_a_lexically_later_tuple():
    strategy, selection, eligibility, _ = _modules()
    neighbour = _incumbent(selection, _THIRD, purpose="interactive")
    standing = _state(selection, incumbent=_incumbent(selection, _SECOND))
    standing = selection.SelectionState(
        incumbents=(*standing.incumbents, neighbour), last_assignments=()
    )

    moved = strategy.committed_selection_state(
        state=standing,
        strategy="consume-first",
        request=_request(eligibility),
        record_id=_FIRST,
        target_committed_at="2026-09-12T10:00:00Z",
    ).unwrap()
    stale = strategy.committed_selection_state(
        state=standing,
        strategy="consume-first",
        request=_request(eligibility),
        record_id=_FIRST,
        target_committed_at="2026-09-12T09:00:00Z",
    ).unwrap()

    assert strategy.incumbent_for(state=moved, request=_request(eligibility)).record_id == _FIRST
    assert neighbour in moved.incumbents, "another purpose's incumbent is untouched"
    assert stale.incumbents == standing.incumbents
    assert (
        strategy.committed_selection_state(
            state=standing,
            strategy="spread-out",
            request=_request(eligibility),
            record_id=_FIRST,
            target_committed_at="2026-09-12T10:00:00Z",
        )
        .failure()
        .error_type
        == "internal-bug"
    )


def test_a_first_commit_for_a_provider_kind_and_purpose_creates_its_incumbent():
    strategy, selection, eligibility, _ = _modules()

    created = strategy.committed_selection_state(
        state=_state(selection),
        strategy="consume-first",
        request=_request(eligibility),
        record_id=_SECOND,
        target_committed_at="2026-09-12T10:00:00Z",
    ).unwrap()

    assert created.incumbents == (
        _incumbent(selection, _SECOND, committed_at="2026-09-12T10:00:00Z"),
    )
    assert (
        selection.selection_state_from_object(
            parsed=selection.selection_state_object(state=created)
        ).unwrap()
        == created
    )
