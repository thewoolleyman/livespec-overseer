"""Concurrent contributions to one closing assignment are idempotent and drift-free.

SPECIFICATION/contracts.md fixes `normalized_close_time` as the LATEST of the stored
`lease_started_at`, the stored non-null `target_committed_at` and the EARLIER of the stored
`accepted_at` and `lease_expires_at`; makes that value the `assignment-end-update`'s
`actual_lease_ended_at` while `closed_at` uses the stored `accepted_at`; fixes both at
`lease_expires_at` for expire; and requires `report_markers` to hold UNIQUE
`(occurred_at, classification)` objects sorted by `occurred_at` and then by the UTF-8 bytes of
`classification`, with each contribution inserted into that canonical order.

NOT ONE OF THESE TIMES COMES FROM A CLOCK, and that is what the drift tests are checking.
`accepted_at` was captured once after the operation's pre-validation and every retry reuses it,
so replaying a close computes the same pair of times however much wall clock has passed. The
tests therefore compute each close TWICE from the same stored inputs and assert byte equality —
a function that sampled a clock would pass every other assertion in this file.

THE ORDER TEST IS DELIBERATELY ARRIVAL-SCRAMBLED. Markers are inserted in two different orders
and the results compared: a canonical order makes the stored array a function of the SET of
contributions, whereas an append would make the stored bytes depend on which manager got there
first, and two managers applying the same two reports would then hold different assignment
bytes for the same facts.

A REPEAT AND A STORED DUPLICATE ARE DIFFERENT THINGS, and are asserted apart. Re-contributing
an existing marker is a completed no-op that leaves the array identical; a duplicate already
SITTING in the stored array is a malformed local record and fails closed, because silently
de-duplicating it would hide a write that should never have happened.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_STARTED = "2026-09-30T10:00:00Z"
_COMMITTED = "2026-09-30T10:00:30Z"
_EXPIRES = "2026-09-30T16:00:00Z"
_ACCEPTED = "2026-09-30T12:00:00Z"


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _close():
    return _module("_lpm_assignment_close")


def _marker(*, occurred_at: str, classification: str):
    return _module("_lpm_reports").ReportMarker(
        occurred_at=occurred_at, classification=classification
    )


def _normalized(**changes: object) -> str:
    values: dict[str, object] = {
        "lease_started_at": _STARTED,
        "lease_expires_at": _EXPIRES,
        "target_committed_at": _COMMITTED,
        "accepted_at": _ACCEPTED,
    }
    values.update(changes)
    return _close().normalized_close_time(**values).unwrap()  # pyright: ignore[reportArgumentType]


def _times(**changes: object):
    values: dict[str, object] = {
        "command": "report",
        "lease_started_at": _STARTED,
        "lease_expires_at": _EXPIRES,
        "target_committed_at": _COMMITTED,
        "accepted_at": _ACCEPTED,
    }
    values.update(changes)
    return _close().close_times(**values)  # pyright: ignore[reportArgumentType]


# ---------------------------------------------------------------------------
# normalized_close_time and the pair a close writes
# ---------------------------------------------------------------------------


def test_the_normalized_close_time_is_the_latest_of_its_three_stored_candidates():
    assert _normalized() == _ACCEPTED, "acceptance is the latest candidate here"
    assert (
        _normalized(accepted_at="2026-09-30T10:00:10Z") == _COMMITTED
    ), "a target commit later than acceptance wins"
    assert (
        _normalized(accepted_at="2026-09-30T09:00:00Z", target_committed_at=None) == _STARTED
    ), "a lease that started after acceptance wins — a backward clock step"
    assert _normalized(target_committed_at=None) == _ACCEPTED


def test_an_acceptance_past_the_lease_expiry_is_clamped_to_the_expiry():
    assert (
        _normalized(accepted_at="2026-09-30T23:00:00Z") == _EXPIRES
    ), "the candidate is the EARLIER of accepted_at and lease_expires_at"
    assert (
        _close().assignment_end_defect(
            lease_started_at=_STARTED,
            lease_expires_at=_EXPIRES,
            target_committed_at=_COMMITTED,
            actual_lease_ended_at=_normalized(accepted_at="2026-09-30T23:00:00Z"),
        )
        is None
    ), "the clamp is what keeps the lease end inside its own fence"


def test_every_close_time_input_must_be_the_one_canonical_spelling():
    module = _close()

    for member in ("lease_started_at", "lease_expires_at", "accepted_at"):
        refusal = module.normalized_close_time(
            **{
                "lease_started_at": _STARTED,
                "lease_expires_at": _EXPIRES,
                "target_committed_at": _COMMITTED,
                "accepted_at": _ACCEPTED,
                member: "2026-09-30 10:00:00",
            }
        )

        assert refusal.failure().error_type == "internal-bug"
        assert refusal.failure().message == (f"{member} must be a UTC RFC 3339-second timestamp")
    assert (
        module.normalized_close_time(
            lease_started_at=_STARTED,
            lease_expires_at=_EXPIRES,
            target_committed_at="whenever",
            accepted_at=_ACCEPTED,
        )
        .failure()
        .message
        == "target_committed_at must be null or a canonical timestamp"
    )


def test_a_close_writes_the_normalized_end_and_its_own_acceptance_as_closed_at():
    assert _close().CLOSING_COMMANDS == ("report", "complete", "release", "expire")
    for command in ("report", "complete", "release"):
        times = _times(command=command).unwrap()

        assert times.actual_lease_ended_at == _ACCEPTED
        assert times.closed_at == _ACCEPTED


def test_expire_closes_at_the_lease_expiry_rather_than_when_it_was_noticed():
    times = _times(command="expire", accepted_at="2026-09-30T20:00:00Z").unwrap()
    noticed_much_later = _times(command="expire", accepted_at="2026-10-05T04:00:00Z").unwrap()

    assert times.actual_lease_ended_at == _EXPIRES
    assert times.closed_at == _EXPIRES
    assert noticed_much_later == times, "when the expiry was noticed changes nothing"


def test_a_command_that_does_not_close_an_assignment_is_a_caller_bug():
    refusal = _times(command="provision")
    uncanonical = _times(accepted_at="2026-09-30 12:00:00")

    assert refusal.failure().error_type == "internal-bug"
    assert refusal.failure().message == "provision does not close an assignment"
    assert uncanonical.failure().message == (
        "accepted_at must be a UTC RFC 3339-second timestamp"
    ), "a close refuses an uncanonical stored time rather than comparing it"


def test_a_close_recomputed_from_the_same_stored_inputs_never_drifts():
    first = _times().unwrap()
    second = _times().unwrap()
    backwards = _times(lease_started_at="2026-09-30T13:00:00Z").unwrap()

    assert first == second, "every input is a STORED value; nothing here reads a clock"
    assert (
        backwards.closed_at < backwards.actual_lease_ended_at
    ), "closed_at may precede the normalized end only after a backward wall-clock step"
    assert _times(command="expire").unwrap() == _times(command="expire").unwrap()


def test_an_assignment_end_outside_its_own_lease_window_is_malformed():
    module = _close()

    assert (
        module.assignment_end_defect(
            lease_started_at=_STARTED,
            lease_expires_at=_EXPIRES,
            target_committed_at=None,
            actual_lease_ended_at="2026-09-30T09:59:59Z",
        )
        == "actual_lease_ended_at must be no earlier than the lease start and target commit"
    )
    assert (
        module.assignment_end_defect(
            lease_started_at=_STARTED,
            lease_expires_at=_EXPIRES,
            target_committed_at=_COMMITTED,
            actual_lease_ended_at="2026-09-30T10:00:15Z",
        )
        == "actual_lease_ended_at must be no earlier than the lease start and target commit"
    ), "a lease cannot have ended before its own target committed"
    assert (
        module.assignment_end_defect(
            lease_started_at=_STARTED,
            lease_expires_at=_EXPIRES,
            target_committed_at=_COMMITTED,
            actual_lease_ended_at="2026-09-30T16:00:01Z",
        )
        == "actual_lease_ended_at must be no later than lease_expires_at"
    )
    assert (
        module.assignment_end_defect(
            lease_started_at=_STARTED,
            lease_expires_at=_EXPIRES,
            target_committed_at=_COMMITTED,
            actual_lease_ended_at=_EXPIRES,
        )
        is None
    )


# ---------------------------------------------------------------------------
# Report markers: canonical order, idempotent contribution
# ---------------------------------------------------------------------------


def test_a_marker_array_is_stored_in_the_declared_canonical_order():
    module = _close()
    early = _marker(occurred_at="2026-09-30T11:00:00Z", classification="rate-limit")
    late_auth = _marker(occurred_at="2026-09-30T11:30:00Z", classification="authentication")
    late_outage = _marker(occurred_at="2026-09-30T11:30:00Z", classification="provider-outage")

    ordered = module.ordered_markers(
        markers=[module.marker_object(marker=marker) for marker in (late_outage, early, late_auth)]
    ).unwrap()

    assert module.MARKER_MEMBERS == ("occurred_at", "classification")
    assert ordered == (
        early,
        late_auth,
        late_outage,
    ), "sorted by occurred_at, then by the UTF-8 bytes of classification"
    assert module.marker_object(marker=early) == {
        "occurred_at": "2026-09-30T11:00:00Z",
        "classification": "rate-limit",
    }


def test_two_managers_applying_the_same_reports_in_either_order_store_the_same_array():
    module = _close()
    first = _marker(occurred_at="2026-09-30T11:00:00Z", classification="rate-limit")
    second = _marker(occurred_at="2026-09-30T11:30:00Z", classification="authentication")

    forwards = module.insert_report_marker(markers=[], marker=first).unwrap()
    forwards = module.insert_report_marker(
        markers=[module.marker_object(marker=marker) for marker in forwards], marker=second
    ).unwrap()
    backwards = module.insert_report_marker(markers=[], marker=second).unwrap()
    backwards = module.insert_report_marker(
        markers=[module.marker_object(marker=marker) for marker in backwards], marker=first
    ).unwrap()

    assert forwards == (first, second)
    assert backwards == forwards, "the stored array is a function of the SET of contributions"


def test_re_contributing_an_existing_marker_leaves_the_array_identical():
    module = _close()
    marker = _marker(occurred_at="2026-09-30T11:00:00Z", classification="authentication")
    stored = [module.marker_object(marker=marker)]

    repeated = module.insert_report_marker(markers=stored, marker=marker).unwrap()

    assert repeated == (marker,), "a repeated contribution is a completed no-op"
    assert len(repeated) == 1


def test_a_duplicate_already_in_the_stored_array_is_malformed_rather_than_collapsed():
    module = _close()
    marker = module.marker_object(
        marker=_marker(occurred_at="2026-09-30T11:00:00Z", classification="unknown")
    )

    refusal = module.insert_report_marker(
        markers=[marker, dict(marker)],
        marker=_marker(occurred_at="2026-09-30T12:00:00Z", classification="unknown"),
    )

    assert refusal.failure().error_type == "store-unavailable"
    assert refusal.failure().message == "report_markers must hold unique objects"


def test_every_marker_shape_defect_fails_closed():
    module = _close()

    def _defect(entry: object) -> str:
        return module.ordered_markers(markers=[entry]).failure().message

    assert _defect("2026-09-30T11:00:00Z") == "a report marker must be a JSON object"
    assert _defect({"occurred_at": "2026-09-30T11:00:00Z"}) == (
        "a report marker must contain exactly occurred_at, classification"
    )
    assert _defect({"occurred_at": "2026-09-30T11:00:00Z", "classification": "x", "extra": 1}) == (
        "a report marker must contain exactly occurred_at, classification"
    )
    assert _defect({"occurred_at": 1759230000, "classification": "unknown"}) == (
        "a marker occurred_at must be a canonical timestamp"
    )
    assert _defect({"occurred_at": "2026-09-30 11:00:00", "classification": "unknown"}) == (
        "a marker occurred_at must be a canonical timestamp"
    )
    assert _defect({"occurred_at": "2026-09-30T11:00:00Z", "classification": "vibes"}) == (
        "a marker classification must be one of: authentication, rate-limit, "
        "provider-outage, unknown"
    )
    assert module.ordered_markers(markers=[]).unwrap() == ()
