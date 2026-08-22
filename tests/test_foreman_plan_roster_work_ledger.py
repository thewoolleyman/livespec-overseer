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


def test_ledger_records_use_configured_credential_wrapper(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".livespec.jsonc").write_text(
        '{"credential_wrapper": ["/usr/local/bin/with-livespec-env.sh", "--"]}\n',
        encoding="utf-8",
    )
    seen_command: list[str] = []

    def capture(command: list[str], **_kwargs: object) -> SimpleNamespace:
        seen_command.extend(command)
        return _completed(stdout="[]")

    monkeypatch.setattr(foreman_plan_roster_work.subprocess, "run", capture)

    assert foreman_plan_roster_work.ledger_epic_records(repo=repo) == []
    assert seen_command == [
        "/usr/local/bin/with-livespec-env.sh",
        "--",
        "bd",
        "list",
        "--type",
        "epic",
        "--status",
        "all",
        "--limit",
        "0",
        "--json",
    ]


def test_work_item_records_use_all_item_ledger_query(*, tmp_path, monkeypatch):
    seen_command: list[str] = []

    def capture(command: list[str], **_kwargs: object) -> SimpleNamespace:
        seen_command.extend(command)
        return _completed(stdout="[]")

    monkeypatch.setattr(foreman_plan_roster_work.subprocess, "run", capture)

    assert foreman_plan_roster_work.ledger_work_item_records(repo=tmp_path) == []
    assert seen_command == ["bd", "list", "--status", "all", "--limit", "0", "--json"]


def test_work_state_uses_unlimited_ledger_queries_past_bd_default_limit(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    (repo / "plan" / "late-running-plan").mkdir(parents=True)
    journal.parent.mkdir(parents=True)
    journal.write_text(
        json.dumps(
            {
                "stage": "dispatch-id",
                "work_item_id": "overseer-late.1",
                "at": "2026-08-22T20:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    early_epics = [
        {
            "id": f"overseer-early-{index}",
            "issue_type": "epic",
            "status": "closed",
            "metadata": {"plan_slug": f"early-{index}"},
        }
        for index in range(50)
    ]
    late_epic = {
        "id": "overseer-late",
        "issue_type": "epic",
        "status": "active",
        "metadata": {"plan_slug": "late-running-plan"},
    }
    late_child = {
        "id": "overseer-late.1",
        "issue_type": "bug",
        "status": "active",
        "parent": "overseer-late",
    }
    epic_payload = [*early_epics, late_epic]
    work_item_payload = [*early_epics, late_epic, late_child]
    commands: list[list[str]] = []

    def capture(command: list[str], **_kwargs: object) -> SimpleNamespace:
        commands.append(command)
        payload = epic_payload if "--type" in command else work_item_payload
        if "--limit" not in command:
            payload = payload[:50]
        return _completed(stdout=json.dumps(payload))

    monkeypatch.setattr(foreman_plan_roster_work.subprocess, "run", capture)

    assert foreman_plan_roster_work.work_states_by_plan(
        repo=repo,
        plan_names=["late-running-plan"],
        journal_path=journal,
    ) == {"late-running-plan": "work-in-flight"}
    assert commands == [
        ["bd", "list", "--type", "epic", "--status", "all", "--limit", "0", "--json"],
        ["bd", "list", "--status", "all", "--limit", "0", "--json"],
    ]


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


def test_work_state_documents_fetch_ledger_epics_once_for_all_plans(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    (repo / "plan" / "alpha").mkdir(parents=True)
    (repo / "plan" / "beta").mkdir(parents=True)
    journal.parent.mkdir(parents=True)
    journal.write_text(
        json.dumps(
            {
                "stage": "dispatch-id",
                "work_item_id": "overseer-alpha.1",
                "at": "2026-08-22T09:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    epic_payload = [
        {
            "id": "overseer-alpha",
            "issue_type": "epic",
            "status": "active",
            "metadata": {"plan_slug": "alpha"},
        },
        {
            "id": "overseer-beta",
            "issue_type": "epic",
            "status": "active",
            "metadata": {"plan_slug": "beta"},
        },
    ]
    work_item_payload = [
        *epic_payload,
        {
            "id": "overseer-alpha.1",
            "issue_type": "bug",
            "status": "active",
            "parent": "overseer-alpha",
        },
    ]
    calls = 0

    def capture(command: list[str], **_kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        if "--type" in command:
            return _completed(stdout=json.dumps(epic_payload))
        return _completed(stdout=json.dumps(work_item_payload))

    monkeypatch.setattr(foreman_plan_roster_work.subprocess, "run", capture)

    assert foreman_plan_roster_work.work_state_documents_by_plan(
        repo=repo,
        plan_names=["alpha", "beta"],
        journal_path=journal,
    ) == {
        "alpha": {
            "work_state": "work-in-flight",
            "work_state_evidence": "anchor-resolved",
        },
        "beta": {
            "work_state": "no-work-in-flight",
            "work_state_evidence": "anchor-resolved",
        },
    }
    assert calls == 2


def test_parentless_explicit_plan_association_raises_work_state_without_id_prefix(
    *, tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    (repo / "plan" / "model-preserving-restarts").mkdir(parents=True)
    (repo / "plan" / "unrelated").mkdir(parents=True)
    journal.parent.mkdir(parents=True)
    journal.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "stage": "dispatch-id",
                        "work_item_id": "overseer-8f18",
                        "dispatch_id": "f6090b30480d40979acb44ef5c574c8b",
                        "at": "2026-08-22T17:49:01Z",
                    }
                ),
                json.dumps(
                    {
                        "stage": "dispatch-id",
                        "work_item_id": "overseer-other",
                        "dispatch_id": "unrelated-run",
                        "at": "2026-08-22T17:50:00Z",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    epic_payload = [
        {
            "id": "overseer-bc55wx",
            "issue_type": "epic",
            "status": "active",
            "metadata": {"plan_slug": "model-preserving-restarts"},
        },
        {
            "id": "overseer-unrelated",
            "issue_type": "epic",
            "status": "active",
            "metadata": {"plan_slug": "unrelated"},
        },
    ]
    work_item_payload = [
        *epic_payload,
        {
            "id": "overseer-8f18",
            "issue_type": "bug",
            "status": "active",
            "parent": None,
            "description": "Thread membership: plan epic overseer-bc55wx.",
            "metadata": {},
        },
        {
            "id": "overseer-other",
            "issue_type": "bug",
            "status": "active",
            "parent": None,
            "description": "Thread membership: plan epic overseer-somewhere-else.",
            "metadata": {},
        },
    ]

    commands: list[list[str]] = []

    def capture(command: list[str], **_kwargs: object) -> SimpleNamespace:
        commands.append(command)
        if "--type" in command:
            return _completed(stdout=json.dumps(epic_payload))
        return _completed(stdout=json.dumps(work_item_payload))

    monkeypatch.setattr(
        foreman_plan_roster_work.subprocess,
        "run",
        capture,
    )

    assert foreman_plan_roster_work.work_states_by_plan(
        repo=repo,
        plan_names=["model-preserving-restarts", "unrelated"],
        journal_path=journal,
    ) == {
        "model-preserving-restarts": "work-in-flight",
        "unrelated": "no-work-in-flight",
    }
    assert commands == [
        ["bd", "list", "--type", "epic", "--status", "all", "--limit", "0", "--json"],
        ["bd", "list", "--status", "all", "--limit", "0", "--json"],
    ]


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
