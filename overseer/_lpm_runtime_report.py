"""Concrete report command composition with durable replay and duplicate detection."""

from __future__ import annotations

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_engine import drive_operation, pending_operation
from _lpm_engine_context import AuditInputs, EffectInputs
from _lpm_locks import release_lock
from _lpm_operation import OperationRecord
from _lpm_operation_identity import idempotency_key_for
from _lpm_operation_plan import PlanContext
from _lpm_reports import FailureReport, occurred_within_interval
from _lpm_results import ManagerError, invalid_report
from _lpm_runtime_base import RuntimeHost, engine_for, new_operation, run_lock, write_new_operation
from _lpm_runtime_bindings import ReportBinding, report_binding

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "run_report",
]


def run_report(
    *, host: RuntimeHost, report: FailureReport
) -> Result[dict[str, object], ManagerError]:
    """Resume or apply one report while holding its complete per-run serialization."""
    held = run_lock(host=host, consumer_run_id=report.consumer_run_id)
    if isinstance(held, Failure):
        return Failure(held.failure())
    try:
        return _serialized(host=host, report=report)
    finally:
        release_lock(held=held.unwrap())


def _serialized(
    *, host: RuntimeHost, report: FailureReport
) -> Result[dict[str, object], ManagerError]:
    normalized = _normalized(report=report)
    key = idempotency_key_for(
        command="report",
        identity={
            "consumer_run_id": report.consumer_run_id,
            "record_id": report.record_id,
            "occurred_at": report.occurred_at,
            "classification": report.classification,
        },
    )
    if isinstance(key, Failure):
        return Failure(key.failure())
    engine = engine_for(host=host)
    pending = pending_operation(engine=engine, command="report", idempotency_key=key.unwrap())
    if isinstance(pending, Failure):
        return Failure(pending.failure())
    binding = report_binding(host=host, consumer_run_id=report.consumer_run_id)
    if isinstance(binding, Failure):
        return Failure(binding.failure())
    bound = binding.unwrap()
    if report.record_id != bound.record_id:
        return Failure(invalid_report(message="report record_id does not match this run"))
    operation = pending.unwrap()
    if operation is not None:
        return _resume_report(
            host=host, report=report, operation=operation, normalized=normalized, binding=bound
        )
    return _fresh_report(host=host, report=report, normalized=normalized, binding=bound)


def _resume_report(
    *,
    host: RuntimeHost,
    report: FailureReport,
    operation: OperationRecord,
    normalized: dict[str, object],
    binding: ReportBinding,
) -> Result[dict[str, object], ManagerError]:
    _ = report
    if operation.normalized_input != normalized:
        return Failure(invalid_report(message="a different report operation is pending"))
    resumed = drive_operation(
        engine=engine_for(host=host),
        operation=operation,
        inputs=EffectInputs(audit=AuditInputs(attempt_now=host.capture_time())),
        condition="every-effect-committed",
        context=PlanContext(against_tombstone=binding.tombstone),
        terminal_result=None,
    )
    if isinstance(resumed, Failure):
        return Failure(resumed.failure())
    return Success(_payload(duplicate=False))


def _fresh_report(
    *,
    host: RuntimeHost,
    report: FailureReport,
    normalized: dict[str, object],
    binding: ReportBinding,
) -> Result[dict[str, object], ManagerError]:
    marker = {"occurred_at": report.occurred_at, "classification": report.classification}
    if marker in binding.markers:
        return Success(_payload(duplicate=True))
    if not occurred_within_interval(
        report=report,
        target_committed_at=binding.target_committed_at,
        lease_closes_at=binding.closes_at,
        now=host.capture_time(),
    ):
        return Failure(invalid_report(message="report occurred_at is outside this run's interval"))
    created = new_operation(
        host=host,
        command="report",
        phase="apply",
        normalized_input=normalized,
        context=PlanContext(against_tombstone=binding.tombstone),
    )
    if isinstance(created, Failure):
        return Failure(created.failure())
    written = write_new_operation(host=host, operation=created.unwrap())
    if isinstance(written, Failure):
        return Failure(written.failure())
    driven = drive_operation(
        engine=engine_for(host=host),
        operation=written.unwrap(),
        inputs=EffectInputs(audit=AuditInputs(attempt_now=host.capture_time())),
        condition="every-effect-committed",
        context=PlanContext(against_tombstone=binding.tombstone),
        terminal_result=None,
    )
    if isinstance(driven, Failure):
        return Failure(driven.failure())
    return Success(_payload(duplicate=False))


def _normalized(*, report: FailureReport) -> dict[str, object]:
    return {
        "version": 1,
        "consumer_run_id": report.consumer_run_id,
        "record_id": report.record_id,
        "occurred_at": report.occurred_at,
        "classification": report.classification,
    }


def _payload(*, duplicate: bool) -> dict[str, object]:
    return {"operation": "report", "duplicate": duplicate}
