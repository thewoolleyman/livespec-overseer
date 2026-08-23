"""Focused tests for foreman-act ledger command execution."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"

__all__: list[str] = []


def ledger_module():
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_act_ledger")


def dispatch_result_module():
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_act_dispatch_result")


def test_ledger_update_command_uses_configured_wrapper_and_flags(*, tmp_path):
    ledger = ledger_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    repo.joinpath(".livespec.jsonc").write_text(
        json.dumps({"credential_wrapper": ["/wrap", "--"]}),
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    result = ledger.ledger_mutation(
        request={
            "action_id": "work_item_update",
            "repo": str(repo),
            "work_item_id": "overseer-child",
            "priority": "P1",
            "parent": "overseer-parent",
        },
        run=lambda *, argv: calls.append(argv) or 0,
    )

    assert result == ("update", "updated")
    assert calls == [
        [
            "/wrap",
            "--",
            "bd",
            "update",
            "overseer-child",
            "--priority",
            "P1",
            "--parent",
            "overseer-parent",
        ]
    ]


def test_ledger_update_command_covers_optional_flag_discrimination(*, tmp_path):
    ledger = ledger_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []

    for request in [
        {
            "action_id": "work_item_update",
            "repo": str(repo),
            "work_item_id": "overseer-child",
            "priority": "P1",
        },
        {
            "action_id": "work_item_update",
            "repo": str(repo),
            "work_item_id": "overseer-child",
            "parent": "overseer-parent",
        },
    ]:
        assert ledger.ledger_mutation(request=request, run=lambda *, argv: calls.append(argv) or 0)

    assert calls == [
        ["bd", "update", "overseer-child", "--priority", "P1"],
        ["bd", "update", "overseer-child", "--parent", "overseer-parent"],
    ]


def test_ledger_epic_create_parses_runner_stdout(*, tmp_path):
    ledger = ledger_module()
    dispatch_result = dispatch_result_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []

    result = ledger.ledger_mutation(
        request={
            "action_id": "foreman_epic_create",
            "repo": str(repo),
            "title": "Foreman anchor",
            "description": "Ledger timeline",
        },
        run=lambda *, argv: calls.append(argv)
        or dispatch_result.CommandResult(returncode=0, stdout='{"id": "overseer-x"}'),
    )

    assert result == ("overseer-x", "created")
    assert calls == [
        [
            "bd",
            "create",
            "Foreman anchor",
            "--type",
            "epic",
            "--description",
            "Ledger timeline",
            "--json",
        ]
    ]


def test_ledger_runner_oserror_names_missing_wrapper(*, tmp_path):
    ledger = ledger_module()
    repo = tmp_path / "repo"
    repo.mkdir()

    def fail_launch(*, argv: list[str]) -> int:
        _ = argv
        raise OSError("cannot execute bd")

    with pytest.raises(RuntimeError, match="credential_wrapper=none:cannot execute bd"):
        ledger.ledger_mutation(
            request={
                "action_id": "work_item_comment",
                "repo": str(repo),
                "work_item_id": "overseer-child",
                "text": "Evidence",
            },
            run=fail_launch,
        )
