"""The two selection strategies, and what a target commit does to the retained state.

SPECIFICATION/spec.md makes `consume-first` the FACTORY DEFAULT: it retains one incumbent per
provider, kind and purpose, reuses it across non-overlapping runs while it stays eligible and
unleased, and moves only when the incumbent becomes ineligible or leased — choosing, when no
incumbent is eligible, the eligible unleased record with the lexically smallest `record_id`. The
explicit `spread` strategy instead takes the eligible unleased record LEAST RECENTLY ASSIGNED,
breaking ties lexically by `record_id`, with a record carrying no retained assignment time sorting
before every assigned record.

SPECIFICATION/contracts.md then fixes what a COMMIT writes back: every target commit sets its
record's assignment time to the LATER of the stored `assigned_at` and that assignment's
`target_committed_at`; a `consume-first` commit replaces its incumbent only when the tuple of
`target_committed_at` and `record_id` is lexically later than the stored tuple, INCLUDING when the
prior incumbent was leased or ineligible; and a `spread` commit leaves every incumbent unchanged.

THE "LATER OF" RULES EXIST FOR DELAYED RECOVERY, NOT FOR TIDINESS. A post-commit effect may
be replayed long after a newer assignment landed — that is the whole point of write-ahead
effects — so a replay that simply STORED its own timestamps would walk selection state
backwards and re-offer an account a later run already took. Taking the later value makes
every replay idempotent AND monotonic, so a stale recovery converges on the newest state
rather than fighting it.

THIS MODULE ORDERS; IT DOES NOT FILTER. Eligibility is seven independent axes and lives
next door; a strategy's only inputs are the already-eligible set and the durable selection
state. Keeping the two apart is what lets `consume-first` prefer an incumbent WITHOUT being
able to resurrect one the lease or freshness axes have already refused: an ineligible
incumbent is simply not in the set it is offered.

AN EMPTY ELIGIBLE SET IS `retryable-exhaustion`, never a softer or harder failure. Nothing
was written, the target is untouched and the run identity is unconsumed — but every
candidate is spoken for right now, so the honest answer to the consumer is "ask again".
"""

from __future__ import annotations

from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_eligibility import SelectionRequest
from _lpm_record import CredentialRecord
from _lpm_results import ManagerError, internal_bug, invalid_request, retryable_exhaustion
from _lpm_selection_state import Incumbent, LastAssignment, SelectionState

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "CONSUME_FIRST_STRATEGY",
    "DEFAULT_SELECTION_STRATEGY",
    "SELECTION_STRATEGIES",
    "SPREAD_STRATEGY",
    "assignment_times",
    "committed_selection_state",
    "incumbent_for",
    "ordered_candidates",
    "select_record",
    "strategy_field",
]

CONSUME_FIRST_STRATEGY: Final = "consume-first"
SPREAD_STRATEGY: Final = "spread"

SELECTION_STRATEGIES: Final = (CONSUME_FIRST_STRATEGY, SPREAD_STRATEGY)
DEFAULT_SELECTION_STRATEGY: Final = CONSUME_FIRST_STRATEGY


def strategy_field(*, value: object) -> Result[str, ManagerError]:
    """Accept an optional `strategy`, materializing `consume-first` for an absent value."""
    if value is None:
        return Success(DEFAULT_SELECTION_STRATEGY)
    if not isinstance(value, str) or value not in SELECTION_STRATEGIES:
        return Failure(
            invalid_request(message=f"strategy must be one of: {', '.join(SELECTION_STRATEGIES)}")
        )
    return Success(value)


def incumbent_for(*, state: SelectionState, request: SelectionRequest) -> Incumbent | None:
    """The retained `consume-first` incumbent for this provider, kind and purpose."""
    for entry in state.incumbents:
        if (entry.provider, entry.kind, entry.purpose) == (
            request.provider,
            request.kind,
            request.purpose,
        ):
            return entry
    return None


def assignment_times(*, state: SelectionState) -> dict[str, str]:
    """The retained assignment time per `record_id`; an absent record has never been assigned."""
    return {entry.record_id: entry.assigned_at for entry in state.last_assignments}


def ordered_candidates(
    *,
    strategy: str,
    request: SelectionRequest,
    records: tuple[CredentialRecord, ...],
    state: SelectionState,
) -> Result[tuple[CredentialRecord, ...], ManagerError]:
    """`records` in the order `strategy` would take them, most preferred first."""
    if strategy == CONSUME_FIRST_STRATEGY:
        return Success(_consume_first_order(request=request, records=records, state=state))
    if strategy == SPREAD_STRATEGY:
        return Success(_spread_order(records=records, state=state))
    return Failure(internal_bug(message=f"unregistered selection strategy: {strategy}"))


def select_record(
    *,
    strategy: str,
    request: SelectionRequest,
    records: tuple[CredentialRecord, ...],
    state: SelectionState,
) -> Result[CredentialRecord, ManagerError]:
    """The record `strategy` chooses, or typed retryable exhaustion for an empty pool."""
    ordered = ordered_candidates(strategy=strategy, request=request, records=records, state=state)
    if isinstance(ordered, Failure):
        return Failure(ordered.failure())
    candidates = ordered.unwrap()
    if candidates == ():
        return Failure(
            retryable_exhaustion(
                message=(
                    "no eligible unleased credential for provider "
                    f"{request.provider}, kind {request.kind}, purpose {request.purpose}"
                )
            )
        )
    return Success(candidates[0])


def committed_selection_state(
    *,
    state: SelectionState,
    strategy: str,
    request: SelectionRequest,
    record_id: str,
    target_committed_at: str,
) -> Result[SelectionState, ManagerError]:
    """The selection state after one target commit, applied idempotently and monotonically."""
    if strategy not in SELECTION_STRATEGIES:
        return Failure(internal_bug(message=f"unregistered selection strategy: {strategy}"))
    assignments = _committed_assignments(
        state=state, record_id=record_id, target_committed_at=target_committed_at
    )
    incumbents = state.incumbents
    if strategy == CONSUME_FIRST_STRATEGY:
        incumbents = _committed_incumbents(
            state=state,
            request=request,
            record_id=record_id,
            target_committed_at=target_committed_at,
        )
    return Success(SelectionState(incumbents=incumbents, last_assignments=assignments))


def _consume_first_order(
    *,
    request: SelectionRequest,
    records: tuple[CredentialRecord, ...],
    state: SelectionState,
) -> tuple[CredentialRecord, ...]:
    incumbent = incumbent_for(state=state, request=request)
    retained_id = None if incumbent is None else incumbent.record_id
    retained = [record for record in records if record.record_id == retained_id]
    rest = sorted(
        (record for record in records if record.record_id != retained_id),
        key=lambda record: record.record_id,
    )
    return tuple(retained + rest)


def _spread_order(
    *, records: tuple[CredentialRecord, ...], state: SelectionState
) -> tuple[CredentialRecord, ...]:
    assigned = assignment_times(state=state)
    return tuple(
        sorted(
            records,
            key=lambda record: (assigned.get(record.record_id, ""), record.record_id),
        )
    )


def _committed_assignments(
    *, state: SelectionState, record_id: str, target_committed_at: str
) -> tuple[LastAssignment, ...]:
    stored = assignment_times(state=state)
    # The default makes the never-assigned case the same expression as the stored case: the
    # later of the two IS the commit time when there is nothing stored to be later than.
    stored[record_id] = max(stored.get(record_id, target_committed_at), target_committed_at)
    return tuple(
        LastAssignment(record_id=identifier, assigned_at=stored[identifier])
        for identifier in sorted(stored)
    )


def _committed_incumbents(
    *,
    state: SelectionState,
    request: SelectionRequest,
    record_id: str,
    target_committed_at: str,
) -> tuple[Incumbent, ...]:
    stored = incumbent_for(state=state, request=request)
    if stored is not None and (target_committed_at, record_id) <= (
        stored.target_committed_at,
        stored.record_id,
    ):
        return state.incumbents
    replacement = Incumbent(
        provider=request.provider,
        kind=request.kind,
        purpose=request.purpose,
        record_id=record_id,
        target_committed_at=target_committed_at,
    )
    key = (request.provider, request.kind, request.purpose)
    others = [
        entry for entry in state.incumbents if (entry.provider, entry.kind, entry.purpose) != key
    ]
    return tuple(
        sorted(
            [*others, replacement],
            key=lambda entry: (entry.provider, entry.kind, entry.purpose),
        )
    )
