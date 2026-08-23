"""Pure option/record matching extracted from the wait-premise question lint."""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []


def _match_module():
    module_path = (
        Path(__file__).resolve().parents[1] / "overseer" / "wait_premise_question_match.py"
    )
    assert module_path.is_file()
    return importlib.import_module("wait_premise_question_match")


def test_option_lines_reads_every_enumerated_option():
    module = _match_module()
    question = (
        "Choose the next action:\n\n"
        "1. Wait for fabro run 01ABC to finish.\n"
        "2. Continue with the local-only cleanup.\n"
        "- Escalate to the maintainer.\n"
    )

    assert module.option_lines(text=question) == (
        "Wait for fabro run 01ABC to finish.",
        "Continue with the local-only cleanup.",
        "Escalate to the maintainer.",
    )


def test_canonical_kind_folds_spaced_and_hyphenated_spellings():
    module = _match_module()

    assert module.canonical_kind(kind="fabro run") == "fabro-run"
    assert module.canonical_kind(kind="Fabro-Run") == "fabro-run"
    assert module.canonical_kind(kind="work item close") == "work-item-close"


def test_issue_for_option_surfaces_an_expressible_wait_with_no_record():
    module = _match_module()

    issue = module.issue_for_option(
        option="Wait for fabro run 01ABC to finish.",
        records=[],
        now="2026-08-22T10:05:00Z",
        evidence_still_holds=None,
    )

    assert issue is not None
    assert issue.reason == "missing-typed-premise"
    assert issue.kind == "fabro-run"


def test_issue_for_option_ignores_an_option_that_asks_for_no_wait():
    module = _match_module()

    issue = module.issue_for_option(
        option="Continue with the local-only cleanup.",
        records=[],
        now="2026-08-22T10:05:00Z",
        evidence_still_holds=None,
    )

    assert issue is None


def test_typed_wait_premise_sentence_punctuation_matches_the_same_record():
    module = _match_module()
    records = [
        {
            "kind": "work-item-close",
            "target_id": "overseer-eplzam",
            "evidence_source": "bd show overseer-eplzam",
            "recorded_at": "2026-08-23T01:00:00Z",
            "recheck_by": "2026-08-23T02:00:00Z",
        },
    ]
    forms = (
        "Wait for work item close (wait-premise: kind=work-item-close target=overseer-eplzam)",
        "Wait for work item close (wait-premise: kind=work-item-close target=overseer-eplzam",
        "Wait for work item close (wait-premise: kind=work-item-close target=overseer-eplzam.",
        "Wait for work item close (wait-premise: kind=work-item-close target=overseer-eplzam,",
    )

    issues = tuple(
        module.issue_for_option(
            option=option,
            records=records,
            now="2026-08-23T03:00:00Z",
            evidence_still_holds=None,
        )
        for option in forms
    )

    assert [issue.reason for issue in issues if issue is not None] == [
        "premise-recheck-untestable",
        "premise-recheck-untestable",
        "premise-recheck-untestable",
        "premise-recheck-untestable",
    ]
    assert [issue.target_id for issue in issues if issue is not None] == [
        "overseer-eplzam",
        "overseer-eplzam",
        "overseer-eplzam",
        "overseer-eplzam",
    ]


def test_typed_wait_premise_preserves_dotted_ids_while_trimming_sentence_period():
    module = _match_module()

    assert module.typed_premise(
        option=(
            "Wait for work item close "
            "(wait-premise: kind=work-item-close target=overseer-au3pt3.16.1"
        )
    ) == ("work-item-close", "overseer-au3pt3.16.1")


def test_typed_wait_premise_trims_trailing_semicolon():
    module = _match_module()

    assert module.typed_premise(
        option=(
            "Wait for work item close "
            "(wait-premise: kind=work-item-close target=overseer-eplzam;"
        )
    ) == ("work-item-close", "overseer-eplzam")
    assert module.typed_premise(
        option=(
            "Wait for work item close "
            "(wait-premise: kind=work-item-close target=overseer-au3pt3.16.1."
        )
    ) == ("work-item-close", "overseer-au3pt3.16.1")


def test_punctuated_due_premise_reaches_reverification_in_fail_soft_lint(tmp_path):
    module = importlib.import_module("wait_premise_question_lint")
    report = module.record_foreman_wait_premise(
        repo=tmp_path,
        kind="work-item-close",
        target_id="overseer-eplzam",
        evidence_source="bd show overseer-eplzam",
        recorded_at="2026-08-23T01:00:00Z",
        recheck_by="2026-08-23T02:00:00Z",
    )
    assert report.can_raise_question is True

    lint = module.lint_foreman_wait_question(
        text=(
            "Choose the next action:\n\n"
            "1. Wait for work item close "
            "(wait-premise: kind=work-item-close target=overseer-eplzam)."
        ),
        repo=tmp_path,
        now="2026-08-23T03:00:00Z",
        evidence_still_holds=None,
    )

    assert lint.can_raise_question is True
    assert [issue.reason for issue in lint.issues] == ["premise-recheck-untestable"]
