"""The lifecycle table is closed, and the only road out of `suspect` runs through revalidation.

SPECIFICATION/spec.md fixes six credential states and states that ONLY the events in its table may
change them. These tests hold the table to that closedness — every row names a ratified status and
a registered event, an unlisted pair has NO answer, and there is deliberately no row taking
`suspect` straight back to `valid`, which is what stops a consumer failure report from being
undone by anything short of a fresh provider validation.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []


def _modules():
    root = pathlib.Path(__file__).parents[1] / "overseer"
    for name in ("_lpm_lifecycle.py", "_lpm_signal.py"):
        assert (root / name).is_file(), f"overseer/{name} must exist"
    return (
        importlib.import_module("_lpm_lifecycle"),
        importlib.import_module("_lpm_signal"),
        importlib.import_module("_lpm_record"),
    )


def test_every_table_row_names_a_ratified_status_and_a_registered_event():
    lifecycle, _, records = _modules()

    starts = {status for status, _ in lifecycle.LIFECYCLE_TRANSITIONS}
    events = {event for _, event in lifecycle.LIFECYCLE_TRANSITIONS}
    landings = set(lifecycle.LIFECYCLE_TRANSITIONS.values())

    assert starts - {lifecycle.NO_RECORD} <= set(records.CREDENTIAL_STATUSES)
    assert landings <= set(records.CREDENTIAL_STATUSES)
    assert events == set(lifecycle.LIFECYCLE_EVENTS)
    assert set(lifecycle.ACTIVE_STATE_BY_OPERATION.values()) == set(records.ACTIVE_STATUSES)


def test_a_suspect_credential_cannot_reach_valid_without_revalidating_first():
    lifecycle, _, _ = _modules()

    to_valid = {
        status
        for (status, _), landing in lifecycle.LIFECYCLE_TRANSITIONS.items()
        if landing == "valid"
    }

    assert "suspect" not in to_valid
    assert to_valid == {"acquiring", "revalidating", "reacquiring"}
    assert (
        lifecycle.admitted_move(
            status="suspect", event=lifecycle.REVALIDATION_STARTS_EVENT
        ).next_status
        == "revalidating"
    )
    assert (
        lifecycle.admitted_move(
            status="revalidating", event=lifecycle.REVALIDATION_SUCCEEDS_EVENT
        ).next_status
        == "valid"
    )


def test_a_report_suspects_a_live_credential_and_is_a_no_op_against_every_other_state():
    lifecycle, _, _ = _modules()

    assert lifecycle.admitted_move(status="valid", event=lifecycle.REPORT_EVENT) == (
        lifecycle.LifecycleMove(status="valid", event=lifecycle.REPORT_EVENT, next_status="suspect")
    )
    assert (
        lifecycle.admitted_move(status="revalidating", event=lifecycle.REPORT_EVENT).next_status
        == "suspect"
    )
    for status in ("suspect", "dead", "reacquiring"):
        assert lifecycle.admitted_move(status=status, event=lifecycle.REPORT_EVENT) is None


def test_acquisition_dies_on_the_third_consecutive_inconclusive_attempt_only():
    lifecycle, _, _ = _modules()

    assert lifecycle.inconclusive_event(consecutive_attempts=1) == (
        lifecycle.INCONCLUSIVE_RETRY_EVENT
    )
    assert lifecycle.inconclusive_event(consecutive_attempts=2) == (
        lifecycle.INCONCLUSIVE_RETRY_EVENT
    )
    assert (
        lifecycle.inconclusive_event(consecutive_attempts=lifecycle.INCONCLUSIVE_FINAL_ATTEMPT)
        == lifecycle.INCONCLUSIVE_FINAL_EVENT
    )
    for active in ("acquiring", "reacquiring"):
        assert (
            lifecycle.admitted_move(
                status=active, event=lifecycle.INCONCLUSIVE_RETRY_EVENT
            ).next_status
            == active
        )
        assert (
            lifecycle.admitted_move(
                status=active, event=lifecycle.INCONCLUSIVE_FINAL_EVENT
            ).next_status
            == "dead"
        )


def test_revalidation_is_single_attempt_so_either_inconclusive_spelling_lands_on_suspect():
    lifecycle, _, _ = _modules()

    for event in (lifecycle.INCONCLUSIVE_RETRY_EVENT, lifecycle.INCONCLUSIVE_FINAL_EVENT):
        assert lifecycle.admitted_move(status="revalidating", event=event).next_status == "suspect"


def test_an_unadmitted_pair_has_no_answer_rather_than_a_plausible_one():
    lifecycle, _, _ = _modules()

    assert lifecycle.admitted_move(status="dead", event="acquisition-succeeds") is None
    assert lifecycle.admitted_move(status="valid", event="replacement-starts") is None
    assert lifecycle.admitted_move(status="valid", event="not-an-event") is None
    assert (
        lifecycle.admitted_move(status=lifecycle.NO_RECORD, event="acquisition-starts").next_status
        == "acquiring"
    )


def test_active_states_map_one_to_one_onto_the_three_run_scoped_operations():
    lifecycle, _, _ = _modules()

    assert lifecycle.active_state_for(operation="acquire") == "acquiring"
    assert lifecycle.active_state_for(operation="reacquire") == "reacquiring"
    assert lifecycle.active_state_for(operation="revalidate") == "revalidating"
    assert lifecycle.active_state_for(operation="provision") is None
    assert lifecycle.is_active_status(status="revalidating") is True
    assert lifecycle.is_active_status(status="valid") is False


def test_the_signal_sources_partition_the_lifecycle_event_set():
    lifecycle, signal, _ = _modules()

    raised = [event for events in signal.EVENTS_BY_SIGNAL_SOURCE.values() for event in events]

    assert sorted(raised) == sorted(lifecycle.LIFECYCLE_EVENTS)
    assert len(raised) == len(set(raised))
    assert set(signal.SIGNAL_SOURCES) == set(signal.EVENTS_BY_SIGNAL_SOURCE)


def test_a_consumer_may_raise_only_its_own_event_and_an_unknown_source_may_raise_none():
    lifecycle, signal, _ = _modules()

    assert signal.source_may_raise(source="consumer-report", event=lifecycle.REPORT_EVENT) is True
    assert (
        signal.source_may_raise(
            source="consumer-report", event=lifecycle.REVALIDATION_SUCCEEDS_EVENT
        )
        is False
    )
    assert signal.source_may_raise(source="the-consumer", event=lifecycle.REPORT_EVENT) is False
