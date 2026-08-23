"""Tests for the start-path identity revalidation split."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import ClassVar

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
MODULE_PATH = OVERSEER_DIR / "foreman_act.py"

__all__: list[str] = []


def foreman_act():
    assert MODULE_PATH.is_file()
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_act")


def base_document(*, repo: Path, generation: int = 7) -> dict[str, object]:
    return {
        "schema_version": 1,
        "repo": str(repo),
        "sources": {"snapshot": {"status": "ok", "mode": "daemon-snapshot"}},
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": generation,
            "rows": [
                {
                    "repo": str(repo),
                    "topic": "alpha",
                    "tmux": "alpha",
                    "runtime": "codex",
                    "status": "session-gone",
                    "session_identity": f"none:{repo}:alpha",
                }
            ],
        },
        "dispatch_journal": [],
    }


def document_without_rows(*, repo: Path, generation: int = 7) -> dict[str, object]:
    document = base_document(repo=repo, generation=generation)
    snapshot = document["snapshot"]
    assert isinstance(snapshot, dict)
    snapshot["rows"] = []
    return document


def start_proposal(*, repo: Path, action_id: str = "plan_start") -> dict[str, object]:
    return {
        "schema_version": 1,
        "action_id": action_id,
        "repo": str(repo),
        "topic": "alpha",
        "session_name": "alpha",
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "session_identity": f"none:{repo}:alpha",
        },
        "classifier": {
            "action": "start",
            "start": {"repo": str(repo), "topic": "alpha", "session_name": "alpha"},
        },
    }


class OccupancyTmuxModule:
    occupied: ClassVar[set[str]] = set()

    class TmuxIO:
        def session_exists(self, *, session: str) -> bool:
            return session in OccupancyTmuxModule.occupied


def resume_proposal(*, repo: Path) -> dict[str, object]:
    return start_proposal(repo=repo, action_id="qualifying_session_resume")


def test_plan_start_accepts_new_topic_without_daemon_row(*, tmp_path, monkeypatch):
    module = foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []
    OccupancyTmuxModule.occupied = set()
    monkeypatch.setattr(module, "tmuxio", OccupancyTmuxModule)

    result = module.act(
        proposal=start_proposal(repo=repo),
        seams=module.ActSeams(
            gather=lambda *, repo, snapshot_path: document_without_rows(repo=Path(repo)),
            run=lambda *, argv: calls.append(argv) or 0,
        ),
    )

    assert result == {
        "action_id": "plan_start",
        "mutated": True,
        "outcome": "acted",
        "reason": "started",
    }
    assert calls == [
        [
            sys.executable,
            str(OVERSEER_DIR / "supervisor.py"),
            "start",
            "--repo",
            str(repo),
            "--topic",
            "alpha",
        ]
    ]


def test_plan_start_refuses_occupied_topic_without_identity_refusal(*, tmp_path, monkeypatch):
    module = foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []
    OccupancyTmuxModule.occupied = {"alpha"}
    monkeypatch.setattr(module, "tmuxio", OccupancyTmuxModule)

    result = module.act(
        proposal=start_proposal(repo=repo),
        seams=module.ActSeams(
            gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
            run=lambda *, argv: calls.append(argv) or 0,
        ),
    )

    assert result == {
        "action_id": "plan_start",
        "mutated": False,
        "outcome": "refused",
        "reason": "tmux_session_occupied",
    }
    assert calls == []


def test_non_start_action_still_refuses_changed_session_identity(*, tmp_path, monkeypatch):
    module = foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
    document = base_document(repo=repo)
    row = document["snapshot"]["rows"][0]
    assert isinstance(row, dict)
    row["session_identity"] = "codex:changed"
    calls: list[list[str]] = []
    OccupancyTmuxModule.occupied = {"alpha"}
    monkeypatch.setattr(module, "tmuxio", OccupancyTmuxModule)

    result = module.act(
        proposal=resume_proposal(repo=repo),
        seams=module.ActSeams(
            gather=lambda *, repo, snapshot_path: document,
            run=lambda *, argv: calls.append(argv) or 0,
        ),
    )

    assert result == {
        "action_id": "qualifying_session_resume",
        "mutated": False,
        "outcome": "refused",
        "reason": "session_identity_changed",
    }
    assert calls == []
