"""Question lint for foreman wait-premise discipline."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import wait_premises

__all__: list[str] = []


def _lint_module():
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "wait_premise_question_lint.py"
    assert module_path.is_file()
    return importlib.import_module("wait_premise_question_lint")


@pytest.mark.integration
def test_compliant_foreman_wait_question_passes(*, tmp_path):
    module = _lint_module()
    repo = tmp_path / "repo"
    _ = wait_premises.write_wait_premise(
        repo=repo,
        topic="foreman",
        kind="fabro-run",
        target_id="01JABC",
        evidence_source="fabro ps --json",
        recorded_at="2026-08-22T10:00:00Z",
        recheck_by="2026-08-22T10:30:00Z",
    )
    question = (
        "Choose the next action:\n\n"
        "1. Wait for Fabro run 01JABC to finish. "
        "wait-premise: kind=fabro-run target=01JABC\n"
        "2. Escalate the failure."
    )

    report = module.lint_foreman_wait_question(
        text=question,
        repo=repo,
        now="2026-08-22T10:05:00Z",
    )

    assert report.can_raise_question is True
    assert report.issues == ()


def test_expressible_wait_question_without_record_is_surfaced(*, tmp_path):
    module = _lint_module()
    question = (
        "Choose the next action:\n\n"
        "1. Wait for PR 1594 to merge, then archive the plan.\n"
        "2. Stop waiting and escalate."
    )

    report = module.lint_foreman_wait_question(
        text=question,
        repo=tmp_path / "repo",
        now="2026-08-22T10:05:00Z",
    )

    assert report.can_raise_question is True
    assert [issue.reason for issue in report.issues] == ["missing-typed-premise"]


@pytest.mark.integration
def test_inexpressible_wait_kind_is_surfaced_but_not_refused(*, tmp_path):
    module = _lint_module()
    question = (
        "Choose the next action:\n\n"
        "1. Wait for the maintainer's deployment window to open.\n"
        "2. Continue with the local-only cleanup."
    )

    report = module.lint_foreman_wait_question(
        text=question,
        repo=tmp_path / "repo",
        now="2026-08-22T10:05:00Z",
    )

    assert report.can_raise_question is True
    assert [issue.reason for issue in report.issues] == ["inexpressible-wait-kind"]


def test_failed_premise_write_is_surfaced_but_not_refused(*, tmp_path, monkeypatch):
    module = _lint_module()

    def raise_oserror(**_kwargs: object) -> Path:
        raise OSError("disk unavailable")

    monkeypatch.setattr(module.wait_premises, "write_wait_premise", raise_oserror)

    report = module.record_foreman_wait_premise(
        repo=tmp_path / "repo",
        kind="fabro-run",
        target_id="01JABC",
        evidence_source="fabro ps --json",
        recorded_at="2026-08-22T10:00:00Z",
        recheck_by="2026-08-22T10:30:00Z",
    )

    assert report.can_raise_question is True
    assert report.path is None
    assert [issue.reason for issue in report.issues] == ["premise-write-failed"]


def test_successful_premise_write_reports_path_and_no_gap(*, tmp_path):
    module = _lint_module()

    report = module.record_foreman_wait_premise(
        repo=tmp_path / "repo",
        kind="pr",
        target_id="1594",
        evidence_source="gh pr view 1594 --json state",
        recorded_at="2026-08-22T10:00:00Z",
        recheck_by="2026-08-22T10:30:00Z",
    )

    assert report.can_raise_question is True
    assert report.path is not None
    assert report.path.name.startswith("pr-1594-")
    assert report.issues == ()


def test_typed_option_without_matching_record_is_surfaced(*, tmp_path):
    module = _lint_module()
    question = (
        "Choose the next action:\n\n"
        "1. Wait for PR 1594 to merge. wait-premise: kind=pr target=1594\n"
        "2. Stop waiting."
    )

    report = module.lint_foreman_wait_question(
        text=question,
        repo=tmp_path / "repo",
        now="2026-08-22T10:05:00Z",
    )

    assert report.can_raise_question is True
    assert [issue.reason for issue in report.issues] == ["missing-recorded-premise"]


def test_typed_option_with_different_recorded_target_is_surfaced(*, tmp_path):
    module = _lint_module()
    repo = tmp_path / "repo"
    _ = wait_premises.write_wait_premise(
        repo=repo,
        topic="foreman",
        kind="pr",
        target_id="1593",
        evidence_source="gh pr view 1593 --json state",
        recorded_at="2026-08-22T10:00:00Z",
        recheck_by="2026-08-22T10:30:00Z",
    )
    question = (
        "Choose the next action:\n\n"
        "1. Wait for PR 1594 to merge. wait-premise: kind=pr target=1594\n"
        "2. Stop waiting."
    )

    report = module.lint_foreman_wait_question(
        text=question,
        repo=repo,
        now="2026-08-22T10:05:00Z",
    )

    assert [issue.reason for issue in report.issues] == ["missing-recorded-premise"]


@pytest.mark.integration
def test_due_premise_without_checker_is_surfaced_as_untestable(*, tmp_path):
    module = _lint_module()
    repo = tmp_path / "repo"
    _ = wait_premises.write_wait_premise(
        repo=repo,
        topic="foreman",
        kind="ci-run",
        target_id="run-9",
        evidence_source="gh run view run-9 --json status,conclusion",
        recorded_at="2026-08-22T10:00:00Z",
        recheck_by="2026-08-22T10:30:00Z",
    )
    question = (
        "Choose the next action:\n\n"
        "1. Wait for CI run run-9 to finish. wait-premise: kind=ci-run target=run-9\n"
        "2. Stop waiting."
    )

    report = module.lint_foreman_wait_question(
        text=question,
        repo=repo,
        now="2026-08-22T10:31:00Z",
    )

    assert [issue.reason for issue in report.issues] == ["premise-recheck-untestable"]


@pytest.mark.integration
def test_due_premise_is_reverified_against_its_recorded_source(*, tmp_path):
    module = _lint_module()
    repo = tmp_path / "repo"
    _ = wait_premises.write_wait_premise(
        repo=repo,
        topic="foreman",
        kind="ci-run",
        target_id="run-9",
        evidence_source="gh run view run-9 --json status,conclusion",
        recorded_at="2026-08-22T10:00:00Z",
        recheck_by="2026-08-22T10:30:00Z",
    )
    question = (
        "Choose the next action:\n\n"
        "1. Wait for CI run run-9 to finish. wait-premise: kind=ci-run target=run-9\n"
        "2. Stop waiting."
    )
    checked_sources: list[str] = []

    def evidence_still_holds(*, record: dict[str, object]) -> bool:
        checked_sources.append(str(record["evidence_source"]))
        return False

    report = module.lint_foreman_wait_question(
        text=question,
        repo=repo,
        now="2026-08-22T10:31:00Z",
        evidence_still_holds=evidence_still_holds,
    )

    assert checked_sources == ["gh run view run-9 --json status,conclusion"]
    assert [issue.reason for issue in report.issues] == ["premise-recheck-failed"]
    assert [issue.option for issue in report.issues] == [
        "Wait for CI run run-9 to finish. wait-premise: kind=ci-run target=run-9"
    ]


def test_due_premise_passes_when_recorded_evidence_still_holds(*, tmp_path):
    module = _lint_module()
    repo = tmp_path / "repo"
    _ = wait_premises.write_wait_premise(
        repo=repo,
        topic="foreman",
        kind="ci-run",
        target_id="run-9",
        evidence_source="gh run view run-9 --json status,conclusion",
        recorded_at="2026-08-22T10:00:00Z",
        recheck_by="2026-08-22T10:30:00Z",
    )
    question = (
        "Choose the next action:\n\n"
        "1. Wait for CI run run-9 to finish. wait-premise: kind=ci-run target=run-9\n"
        "2. Stop waiting."
    )

    report = module.lint_foreman_wait_question(
        text=question,
        repo=repo,
        now="2026-08-22T10:31:00Z",
        evidence_still_holds=lambda **_kwargs: True,
    )

    assert report.issues == ()


def test_due_premise_with_indeterminate_checker_is_surfaced(*, tmp_path):
    module = _lint_module()
    repo = tmp_path / "repo"
    _ = wait_premises.write_wait_premise(
        repo=repo,
        topic="foreman",
        kind="ci-run",
        target_id="run-9",
        evidence_source="gh run view run-9 --json status,conclusion",
        recorded_at="2026-08-22T10:00:00Z",
        recheck_by="2026-08-22T10:30:00Z",
    )
    question = (
        "Choose the next action:\n\n"
        "1. Wait for CI run run-9 to finish. wait-premise: kind=ci-run target=run-9\n"
        "2. Stop waiting."
    )

    report = module.lint_foreman_wait_question(
        text=question,
        repo=repo,
        now="2026-08-22T10:31:00Z",
        evidence_still_holds=lambda **_kwargs: None,
    )

    assert [issue.reason for issue in report.issues] == ["premise-recheck-untestable"]
