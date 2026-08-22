"""Ledger-anchor edge coverage for foreman roster work state."""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from typing import NoReturn

import foreman_plan_roster_work

__all__: list[str] = []


def _completed(*, stdout: str, returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, returncode=returncode)


def test_ledger_records_fail_soft_on_unreadable_outputs(*, tmp_path, monkeypatch):
    def missing_bd(*_args: object, **_kwargs: object) -> NoReturn:
        raise OSError("bd missing")

    monkeypatch.setattr(foreman_plan_roster_work.subprocess, "run", missing_bd)
    assert foreman_plan_roster_work.ledger_epic_records(repo=tmp_path) == []

    def timeout(*_args: object, **_kwargs: object) -> NoReturn:
        raise subprocess.TimeoutExpired(cmd=["bd"], timeout=1)

    monkeypatch.setattr(foreman_plan_roster_work.subprocess, "run", timeout)
    assert foreman_plan_roster_work.ledger_epic_records(repo=tmp_path) == []

    monkeypatch.setattr(
        foreman_plan_roster_work.subprocess,
        "run",
        lambda *_args, **_kwargs: _completed(stdout="[]", returncode=2),
    )
    assert foreman_plan_roster_work.ledger_epic_records(repo=tmp_path) == []

    monkeypatch.setattr(
        foreman_plan_roster_work.subprocess,
        "run",
        lambda *_args, **_kwargs: _completed(stdout="{not-json"),
    )
    assert foreman_plan_roster_work.ledger_epic_records(repo=tmp_path) == []

    monkeypatch.setattr(
        foreman_plan_roster_work.subprocess,
        "run",
        lambda *_args, **_kwargs: _completed(stdout=json.dumps({})),
    )
    assert foreman_plan_roster_work.ledger_epic_records(repo=tmp_path) == []


def test_ledger_anchor_uses_only_unique_open_plan_slug_epics(*, tmp_path, monkeypatch):
    payload = [
        [],
        {"id": "ignored-task", "issue_type": "task", "metadata": {"plan_slug": "alpha"}},
        {"id": "ignored-metadata", "issue_type": "epic", "metadata": {}},
        {
            "id": "closed-alpha",
            "issue_type": "epic",
            "status": "closed",
            "metadata": {"plan_slug": "alpha"},
        },
        {
            "id": "open-alpha",
            "issue_type": "epic",
            "status": "active",
            "metadata": {"plan_slug": "alpha"},
        },
    ]
    monkeypatch.setattr(
        foreman_plan_roster_work.subprocess,
        "run",
        lambda *_args, **_kwargs: _completed(stdout=json.dumps(payload)),
    )

    assert (
        foreman_plan_roster_work.ledger_plan_epic_anchor(repo=tmp_path, plan="alpha")
        == "open-alpha"
    )
    assert foreman_plan_roster_work.plan_anchor_resolved(repo=tmp_path, plan="alpha") is True


def test_legacy_anchor_fallback_remains_when_ledger_has_no_match(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "plan" / "alpha").mkdir(parents=True)
    (repo / "plan" / "alpha" / "epic.md").write_text(
        "**Ledger anchor:** epic **`legacy-alpha`**\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        foreman_plan_roster_work.subprocess,
        "run",
        lambda *_args, **_kwargs: _completed(stdout=json.dumps([])),
    )

    assert foreman_plan_roster_work.plan_epic_anchor(repo=repo, plan="alpha") == "legacy-alpha"
    assert foreman_plan_roster_work.plan_anchor_resolved(repo=repo, plan="missing") is False
