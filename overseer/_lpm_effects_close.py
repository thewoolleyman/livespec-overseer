"""The three conditional field updates a close writes into its own binding record.

SPECIFICATION/contracts.md states each one narrowly. "`report-marker-update` MUST insert the new
unique marker in the assignment or tombstone's declared canonical order." For report, complete or
release "`assignment-end-update` MUST conditionally set `actual_lease_ended_at` to the operation's
defined `normalized_close_time`; for expire it MUST use `lease_expires_at`". And an assignment's
or tombstone's nullable `completion` "MUST have the exact completion-input shape", which IS the
complete command's own normalized input — so the completion is COPIED from the operation record
rather than rebuilt, and the write-back validator is what rejects it under any other command.

ALL THREE ARE SETTLED BY COMPARING THE WHOLE RECORD, not by asking whether the field "looks done".
Every value each one writes is derived from stored values alone — the operation's retained
`accepted_at` and the record's own lease window — so the replacement a replay computes is
BYTE-IDENTICAL to the one the first pass wrote, and equality IS the satisfied postcondition. A
field-level check would have to re-derive the same value anyway and could not see a record that
had drifted in some other member.

THE MARKER INSERT IS A RE-SORT AND A SET UNION, so arrival order cannot reach the stored bytes.
Two managers that applied the same two reports in different orders hold the same array, and a
repeat of one report contributes nothing — the already-present case returns the same canonical
array, which the comparison above then settles.

A DIFFERENT STORED COMPLETION REFUSES RATHER THAN BEING OVERWRITTEN. A completion is the
consumer's own account of a finished run; a second, DISAGREEING one means two commands claim the
same `consumer_run_id`, and whichever survived an overwrite would be a record nobody filed. An
IDENTICAL one is not that case at all — it compares equal and settles, which is what a replay of
a committed `completion-update` has to do.
"""

from __future__ import annotations

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment_close import marker_object, ordered_with
from _lpm_closing_records import closing_record, closing_times, settle_closing_update
from _lpm_engine_context import EffectContext, input_text
from _lpm_reports import ReportMarker
from _lpm_results import ManagerError, store_unavailable

from overseer._vendor.returns.result import Failure, Result

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "assignment_end_update",
    "completion_update",
    "report_marker_update",
]


def report_marker_update(*, context: EffectContext) -> Result[str, ManagerError]:
    """Insert this report's marker in canonical order, or settle an array already holding it."""
    bound = closing_record(context=context)
    if isinstance(bound, Failure):
        return bound
    occurred_at = input_text(operation=context.operation, member="occurred_at")
    if isinstance(occurred_at, Failure):
        return occurred_at
    classification = input_text(operation=context.operation, member="classification")
    if isinstance(classification, Failure):
        return classification
    record = bound.unwrap()
    inserted = ordered_with(
        markers=record.report_markers,
        marker=ReportMarker(
            occurred_at=occurred_at.unwrap(), classification=classification.unwrap()
        ),
    )
    return settle_closing_update(
        context=context,
        record=record,
        updated={
            **record.stored,
            "report_markers": [marker_object(marker=marker) for marker in inserted],
        },
    )


def completion_update(*, context: EffectContext) -> Result[str, ManagerError]:
    """Record this completion against the run's binding, or settle the one already stored."""
    bound = closing_record(context=context)
    if isinstance(bound, Failure):
        return bound
    record = bound.unwrap()
    completion = dict(context.operation.normalized_input)
    if record.completion is not None and record.completion != completion:
        return Failure(store_unavailable(message="a different completion already closes this run"))
    return settle_closing_update(
        context=context, record=record, updated={**record.stored, "completion": completion}
    )


def assignment_end_update(*, context: EffectContext) -> Result[str, ManagerError]:
    """Set the lease's actual end to this command's normalized close time, or settle it."""
    bound = closing_record(context=context)
    if isinstance(bound, Failure):
        return bound
    record = bound.unwrap()
    times = closing_times(context=context, record=record)
    if isinstance(times, Failure):
        return Failure(times.failure())
    return settle_closing_update(
        context=context,
        record=record,
        updated={
            **record.stored,
            "actual_lease_ended_at": times.unwrap().actual_lease_ended_at,
        },
    )
