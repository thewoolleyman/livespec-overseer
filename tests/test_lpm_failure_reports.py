"""A consumer report is exact, idempotent, and cannot cost a replacement credential its life.

SPECIFICATION/contracts.md fixes the report object exactly, requires a stored `(occurred_at,
classification)` marker to answer `duplicate` true BEFORE interval validation and apply nothing at
all, refuses a report against a currently `acquiring` record, makes the lifecycle move a compare-
and-set on the stored value generation, and leaves lifecycle status untouched for `unknown` while
still releasing the lease.

These tests separate the two no-ops that a plausible implementation merges. A DUPLICATE
applies nothing — the first report already released the lease and made the transition. A
generation mismatch or an already-`suspect` record applies the lease release and NOTHING else:
the report is accepted, the run is let go, and the replacement credential's lifecycle and
cache entry are deliberately left alone. Merging them one way strands a lease; merging them
the other way suspects a credential the reporting run never used.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_OCCURRED = "2026-09-12T11:00:00Z"


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_reports.py"
    assert module_path.is_file(), "overseer/_lpm_reports.py must exist"
    return (
        importlib.import_module("_lpm_reports"),
        importlib.import_module("_lpm_results"),
    )


def _object(**changes):
    source = {
        "version": 1,
        "consumer_run_id": "run-a",
        "record_id": _RECORD_ID,
        "occurred_at": _OCCURRED,
        "classification": "authentication",
    }
    source.update(changes)
    return source


def _refusal(reports, **changes) -> str:
    return reports.report_from_object(parsed=_object(**changes)).failure().message


def _report(reports, **changes):
    return reports.report_from_object(parsed=_object(**changes)).unwrap()


def _effects(reports, *, status="valid", markers=(), generation_matches=True, **changes):
    return reports.report_effects(
        report=_report(reports, **changes),
        status=status,
        markers=markers,
        generation_matches=generation_matches,
    ).unwrap()


def test_an_accepted_report_is_four_scalars_and_its_diagnostic_is_discarded():
    reports, _ = _modules()

    plain = _report(reports)
    annotated = _report(reports, diagnostic="HTTP 401 from the messages endpoint")

    assert plain == reports.FailureReport(
        consumer_run_id="run-a",
        record_id=_RECORD_ID,
        occurred_at=_OCCURRED,
        classification="authentication",
    )
    assert annotated == plain, "a diagnostic is excluded from normalized-input equality"
    assert "diagnostic" not in vars(annotated)
    assert reports.REPORT_OPTIONAL_MEMBERS == ("diagnostic",)


def test_every_malformed_report_is_invalid_report_before_anything_is_touched():
    reports, results = _modules()

    assert reports.report_from_object(parsed=[]).failure().error_type == "invalid-report"
    assert reports.report_from_object(parsed=[]).failure().message == (
        "report must be a JSON object"
    )
    assert results.exit_status_for(error_type="invalid-report") == 2
    assert _refusal(reports, version=None) == "report version must be the integer 1"
    assert _refusal(reports, version=True) == "report version must be the integer 1"
    assert _refusal(reports, extra="x") == "report has extra member extra"
    assert _refusal(reports, consumer_run_id="") == "consumer_run_id must be a non-empty string"
    assert _refusal(reports, record_id=7) == "record_id must be a non-empty string"
    assert _refusal(reports, occurred_at="2026-09-12T11:00:00+00:00") == (
        "occurred_at must be a UTC RFC 3339-second timestamp"
    )
    assert _refusal(reports, occurred_at=0) == (
        "occurred_at must be a UTC RFC 3339-second timestamp"
    )
    assert _refusal(reports, classification="quota") == (
        "classification must be one of: authentication, rate-limit, provider-outage, unknown"
    )


def test_a_missing_member_names_itself_and_a_non_redacted_diagnostic_is_refused():
    reports, _ = _modules()
    without_record = _object()
    del without_record["record_id"]

    assert reports.report_from_object(parsed=without_record).failure().message == (
        "report is missing record_id"
    )
    assert _refusal(reports, diagnostic=0) == "diagnostic must be a string"
    assert _refusal(reports, diagnostic="leaked sk-ant-oat01-zzz") == (
        "diagnostic is not mechanically redacted"
    )
    assert _refusal(reports, diagnostic="x" * 1025) == "diagnostic is not mechanically redacted"


def test_an_authentication_report_suspects_a_live_credential_and_evicts_its_cache_entry():
    reports, _ = _modules()

    effects = _effects(reports, status="valid")

    assert effects == reports.ReportEffects(
        duplicate=False, releases_lease=True, next_status="suspect", evicts_cache_entry=True
    )
    assert _effects(reports, status="revalidating").next_status == "suspect"


def test_rate_limit_and_provider_outage_suspect_without_evicting_and_unknown_changes_nothing():
    reports, _ = _modules()

    for classification in ("rate-limit", "provider-outage"):
        effects = _effects(reports, classification=classification)
        assert effects.next_status == "suspect", classification
        assert effects.evicts_cache_entry is False, classification
        assert effects.releases_lease is True, classification
    unknown = _effects(reports, classification="unknown")
    assert unknown.next_status is None
    assert unknown.releases_lease is True
    assert unknown.evicts_cache_entry is False


def test_a_stored_marker_makes_the_repeat_apply_nothing_at_all():
    reports, _ = _modules()
    report = _report(reports)
    marker = reports.report_marker(report=report)

    repeat = _effects(reports, markers=(marker,))

    assert reports.stored_marker(report=report, markers=(marker,)) is True
    assert reports.stored_marker(report=report, markers=()) is False
    assert repeat == reports.ReportEffects(
        duplicate=True, releases_lease=False, next_status=None, evicts_cache_entry=False
    )
    assert (
        reports.stored_marker(report=_report(reports, classification="unknown"), markers=(marker,))
        is False
    )


def test_a_replaced_generation_or_already_suspect_record_releases_the_lease_and_nothing_else():
    reports, _ = _modules()

    replaced = _effects(reports, generation_matches=False)
    already = _effects(reports, status="suspect")

    for effects in (replaced, already):
        assert effects.duplicate is False
        assert effects.releases_lease is True
        assert effects.next_status is None
        assert effects.evicts_cache_entry is False
    for status in ("dead", "reacquiring"):
        assert _effects(reports, status=status).next_status is None, status


def test_a_report_against_an_acquiring_record_is_refused_and_an_unknown_status_is_a_bug():
    reports, _ = _modules()

    acquiring = reports.report_effects(
        report=_report(reports), status="acquiring", markers=(), generation_matches=True
    )
    nonsense = reports.report_effects(
        report=_report(reports), status="retired", markers=(), generation_matches=True
    )
    unclassified = reports.report_effects(
        report=reports.FailureReport(
            consumer_run_id="run-a",
            record_id=_RECORD_ID,
            occurred_at=_OCCURRED,
            classification="quota",
        ),
        status="valid",
        markers=(),
        generation_matches=True,
    )

    assert acquiring.failure().message == (
        "an acquiring credential could not have been provisioned"
    )
    assert acquiring.failure().error_type == "invalid-report"
    assert nonsense.failure().error_type == "internal-bug"
    assert nonsense.failure().message == "unregistered credential status: retired"
    assert unclassified.failure().error_type == "invalid-report"


def test_occurred_at_must_sit_inside_the_assignment_or_tombstone_interval():
    reports, _ = _modules()

    def _inside(occurred_at, *, closes_at="2026-09-12T16:00:00Z", now="2026-09-12T12:00:00Z"):
        return reports.occurred_within_interval(
            report=_report(reports, occurred_at=occurred_at),
            target_committed_at="2026-09-12T10:00:00Z",
            lease_closes_at=closes_at,
            now=now,
        )

    assert _inside("2026-09-12T10:00:00Z") is True
    assert _inside("2026-09-12T11:00:00Z") is True
    assert _inside("2026-09-12T09:59:59Z") is False
    assert _inside("2026-09-12T12:00:01Z") is False
    assert _inside("2026-09-12T11:00:00Z", closes_at="2026-09-12T10:30:00Z") is False


def test_retryable_exhaustion_is_its_own_typed_result_with_exit_three():
    _, results = _modules()

    exhausted = results.retryable_exhaustion(message="every eligible account is leased")

    assert exhausted.error_type == "retryable-exhaustion"
    assert results.exit_status_for(error_type=exhausted.error_type) == 3
    assert results.error_object(error=exhausted) == {
        "version": 1,
        "status": "error",
        "error_type": "retryable-exhaustion",
        "message": "every eligible account is leased",
    }
