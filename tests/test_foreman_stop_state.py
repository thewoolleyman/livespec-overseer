"""Focused coverage for foreman stop-state sidecars."""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"

__all__: list[str] = []


@dataclass(frozen=True, kw_only=True)
class Lapse:
    stale: bool
    heartbeat_written_at: datetime
    stale_after_seconds: float


def foreman_stop_state():
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_stop_state")


def test_heading_only_hold_uses_generic_hold_reason(*, tmp_path: Path):
    module = foreman_stop_state()
    repo = tmp_path / "repo"
    hold = repo / "tmp" / "overseer" / "foreman" / "HOLD.md"
    hold.parent.mkdir(parents=True)
    _ = hold.write_text("# Hold\n\n", encoding="utf-8")

    state = module.read_foreman_stop_state(repo=repo)

    assert state is not None
    assert state.state == "held"
    assert state.reason == "operator hold"


@pytest.mark.parametrize(
    "payload",
    [
        "{",
        json.dumps({"state": "held", "reason": "not via stop", "observed_at": "t"}),
        json.dumps({"state": "died", "reason": "x"}),
        json.dumps({"state": "died", "reason": "x", "observed_at": "t", "lapsed_at": 3}),
        json.dumps([]),
    ],
)
def test_malformed_stop_json_is_absent(*, tmp_path: Path, payload: str):
    module = foreman_stop_state()
    repo = tmp_path / "repo"
    path = repo / "tmp" / "overseer" / "foreman" / "stop.json"
    path.parent.mkdir(parents=True)
    _ = path.write_text(payload, encoding="utf-8")

    assert module.read_foreman_stop_state(repo=repo) is None


def test_missing_stop_json_is_absent(*, tmp_path: Path):
    module = foreman_stop_state()

    assert module.read_foreman_stop_state(repo=tmp_path / "repo") is None


def test_runtime_stop_state_does_nothing_for_auto_resume(*, tmp_path: Path):
    module = foreman_stop_state()
    repo = tmp_path / "repo"

    module.record_runtime_stop_state(
        repo=repo,
        lapse=None,
        exit_reason="hard-tick-budget",
        auto_resume_interval_seconds=7200.0,
        now=lambda: 1000.0,
    )

    assert not (repo / "tmp" / "overseer" / "foreman" / "stop.json").exists()


def test_runtime_stop_state_records_lapsed_deadline(*, tmp_path: Path):
    module = foreman_stop_state()
    repo = tmp_path / "repo"
    lapse = Lapse(
        stale=True,
        heartbeat_written_at=datetime.fromtimestamp(1000.0, tz=timezone.utc),
        stale_after_seconds=7200.0,
    )

    module.record_runtime_stop_state(
        repo=repo,
        lapse=lapse,
        exit_reason="converged",
        auto_resume_interval_seconds=None,
        now=lambda: 11800.0,
    )

    stop = json.loads((repo / "tmp" / "overseer" / "foreman" / "stop.json").read_text())
    assert stop["state"] == "died"
    assert stop["lapsed_at"] == "1970-01-01T02:16:40Z"


def test_unreadable_hold_uses_generic_hold_reason(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    module = foreman_stop_state()
    repo = tmp_path / "repo"
    hold = repo / "tmp" / "overseer" / "foreman" / "HOLD.md"
    hold.parent.mkdir(parents=True)
    _ = hold.write_text("held", encoding="utf-8")
    original = Path.read_text

    def fake_read_text(
        self: Path, *, encoding: str | None = None, errors: str | None = None
    ) -> str:
        if self == hold:
            raise OSError("unreadable")
        return original(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    state = module.read_foreman_stop_state(repo=repo)

    assert state is not None
    assert state.reason == "operator hold"
