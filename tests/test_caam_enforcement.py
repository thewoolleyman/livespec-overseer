"""Production-path tests for caam model enforcement."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import caam_enforcement
import pytest
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import UsageRecord
from caam_profile_state import STATE_REL

__all__: list[str] = []


@dataclass(kw_only=True)
class RecordingTmux:
    sessions: tuple[str, ...] = ("alpha-foreman",)
    screens: dict[str, list[str]] = field(default_factory=dict)
    send_keys_calls: list[tuple[str, str]] = field(default_factory=list)
    send_literal_keys_calls: list[tuple[str, str]] = field(default_factory=list)

    def list_sessions(self) -> list[str]:
        return list(self.sessions)

    def pane_pid(self, *, session: str) -> int:
        del session
        return 101

    def capture_pane(self, *, session: str) -> str:
        screens = self.screens.get(session, ["❯"])
        if len(screens) == 1:
            return screens[0]
        return screens.pop(0)

    def send_keys(self, *, session: str, keys: str) -> bool:
        self.send_keys_calls.append((session, keys))
        return True

    def send_literal_keys(self, *, session: str, text: str) -> bool:
        self.send_literal_keys_calls.append((session, text))
        return True


def test_production_pass_reaches_tmux_discovery_and_model_picker(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmux = RecordingTmux(
        screens={
            "alpha-foreman": [
                "❯",
                "Select model\n❯ 1. Opus\n  2. Fable\n",
                "ready",
            ],
        }
    )
    home = _caam_home(tmp_path=tmp_path, fable=42.0, model="claude-opus-5")
    _patch_production_model_boundaries(monkeypatch=monkeypatch, tmux=tmux)
    lines: list[str] = []

    code = run_pass(
        flags=Flags(
            scheduled=True,
            force=False,
            dry_run=False,
            no_models=False,
            no_warm=True,
            foreman_model=None,
        ),
        home=home,
        now=1234.0,
        stdout=lines.append,
        caam_runner=_active_profile_runner(),
        fetcher=_usage_fetcher(fable=42.0),
        save_state=lambda **_: None,
        switch_account=lambda **_: None,
        agent_runner=_agent_runner(),
    )

    assert code == 0
    assert tmux.send_literal_keys_calls[0] == ("alpha-foreman", "/model")
    assert tmux.send_keys_calls[:2] == [("alpha-foreman", "Enter"), ("alpha-foreman", "Down")]


def test_dry_run_reports_would_line_and_sends_no_picker_keys(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmux = RecordingTmux()
    home = _caam_home(tmp_path=tmp_path, fable=42.0, model="claude-opus-5")
    _patch_production_model_boundaries(monkeypatch=monkeypatch, tmux=tmux)
    lines: list[str] = []

    code = run_pass(
        flags=Flags(
            scheduled=True,
            force=False,
            dry_run=True,
            no_models=False,
            no_warm=True,
            foreman_model=None,
        ),
        home=home,
        now=1234.0,
        stdout=lines.append,
        caam_runner=_active_profile_runner(),
        fetcher=_usage_fetcher(fable=42.0),
        save_state=lambda **_: None,
        switch_account=lambda **_: None,
        agent_runner=_agent_runner(),
    )

    assert code == 0
    assert tmux.send_keys_calls == []
    assert tmux.send_literal_keys_calls == []
    assert (
        "models: foremen want fable (active account Fable left); alpha-foreman would opus->fable"
        in lines
    )


def test_busy_pane_reports_busy_without_recording_and_retries_next_tick(*, tmp_path: Path) -> None:
    state: dict[str, object] = {}
    state_path = tmp_path / "state.json"

    first = caam_enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=Path("/tmp"),
        state_path=state_path,
        session_names=("alpha-foreman",),
        active_fable=42.0,
        foreman_model=None,
        now=1234.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_model=lambda **_: "opus",
        pane_idle=lambda **_: False,
        set_model=lambda **_: None,
        state=state,
    )
    second = caam_enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=Path("/tmp"),
        state_path=state_path,
        session_names=("alpha-foreman",),
        active_fable=42.0,
        foreman_model=None,
        now=1244.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_model=lambda **_: "opus",
        pane_idle=lambda **_: True,
        set_model=lambda **_: None,
        state=state,
    )

    assert (
        first[-1]
        == "models: foremen want fable (active account Fable left); alpha-foreman busy(opus->fable)"
    )
    assert state == {}
    assert (
        second[-1]
        == "models: foremen want fable (active account Fable left); alpha-foreman opus->fable"
    )


def test_model_report_lines_match_source_oracle(*, tmp_path: Path) -> None:
    state: dict[str, object] = {}
    state_path = tmp_path / "state.json"

    would = caam_enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=Path("/tmp"),
        state_path=state_path,
        session_names=("alpha-foreman",),
        active_fable=42.0,
        foreman_model=None,
        now=1234.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_model=lambda **_: None,
        pane_idle=lambda **_: True,
        dry_run=True,
        set_model=lambda **_: None,
        state=state,
    )
    busy = caam_enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=Path("/tmp"),
        state_path=state_path,
        session_names=("alpha-foreman",),
        active_fable=42.0,
        foreman_model=None,
        now=1234.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_model=lambda **_: None,
        pane_idle=lambda **_: False,
        set_model=lambda **_: None,
        state=state,
    )

    assert (
        would[-1] == "models: foremen want fable (active account Fable left); "
        "alpha-foreman would unknown->fable"
    )
    assert (
        busy[-1] == "models: foremen want fable (active account Fable left); "
        "alpha-foreman busy(unknown->fable)"
    )


def _patch_production_model_boundaries(
    *, monkeypatch: pytest.MonkeyPatch, tmux: RecordingTmux
) -> None:
    monkeypatch.setattr(caam_enforcement, "real_picker_tmux", lambda: tmux, raising=False)
    monkeypatch.setattr(caam_enforcement, "_sleep", lambda seconds: None, raising=False)
    monkeypatch.setattr(caam_enforcement, "proc_children", lambda *, pid: (), raising=False)
    monkeypatch.setattr(
        caam_enforcement,
        "proc_environ",
        lambda *, pid: b"CLAUDE_CODE_SESSION_ID=sid-1\0" if pid == 101 else None,
        raising=False,
    )


def _caam_home(*, tmp_path: Path, fable: float, model: str) -> Path:
    home = tmp_path / "home"
    vault_profile = home / ".local/share/caam/vault/claude/active"
    projects = home / ".claude/projects/project"
    settings = home / ".claude/settings.json"
    vault_profile.mkdir(parents=True)
    projects.mkdir(parents=True)
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text("{}", encoding="utf-8")
    (home / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": "account-1"}}),
        encoding="utf-8",
    )
    (vault_profile / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": "account-1"}}),
        encoding="utf-8",
    )
    (vault_profile / ".credentials.json").write_text("{}", encoding="utf-8")
    (projects / "sid-1.jsonl").write_text(
        json.dumps({"message": {"model": model}}) + "\n",
        encoding="utf-8",
    )
    state_path = home / STATE_REL
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{}", encoding="utf-8")
    del fable
    return home


def _usage_fetcher(*, fable: float) -> Callable[..., tuple[UsageRecord | None, str | None]]:
    usage = UsageRecord(
        five_hour=10.0,
        seven_day=10.0,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable=fable,
        fable_resets_at=None,
    )

    def fetcher(**_: Any) -> tuple[UsageRecord | None, str | None]:
        return usage, None

    return fetcher


def _active_profile_runner() -> Callable[..., Any]:
    def run_caam(**_: Any) -> Any:
        return type(
            "Completed",
            (),
            {
                "returncode": 0,
                "stdout": json.dumps({"tools": [{"tool": "claude", "active_profile": "active"}]}),
            },
        )()

    return run_caam


def _agent_runner() -> Callable[..., Any]:
    def run_agent(**_: Any) -> Any:
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    return run_agent
