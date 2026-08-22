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
