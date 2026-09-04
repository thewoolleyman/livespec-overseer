"""Production-path tests for caam model enforcement."""

from __future__ import annotations

import ast
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import caam_enforcement
import pytest
from _signals_topics import reserved_worker_suffix
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import UsageRecord
from caam_profile_state import STATE_REL

__all__: list[str] = []

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
RESERVED_SUFFIX_VALUES = {
    suffix
    for topic in ("topic-supervisor", "topic-foreman", "topic-grooming")
    if (suffix := reserved_worker_suffix(topic=topic)) is not None
}


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
            session_models=(),
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
            session_models=(),
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
        active_fable=58.0,
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
    after_first = dict(state)
    second = caam_enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=Path("/tmp"),
        state_path=state_path,
        session_names=("alpha-foreman",),
        active_fable=58.0,
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
    # A busy pane gets NO set-record (that is what lets the next tick retry it);
    # per ratified v045 enforcement still records every pane's observed model.
    assert "models" not in after_first
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
        active_fable=58.0,
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
        active_fable=58.0,
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


def test_grooming_seat_receives_foreman_model_policy(*, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    messages = caam_enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=Path("/tmp"),
        state_path=tmp_path / "state.json",
        session_names=("alpha-foreman", "alpha-grooming", "worker"),
        active_fable=58.0,
        foreman_model="fable",
        now=1234.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_model=lambda **_: "opus",
        pane_idle=lambda **_: True,
        set_model=lambda *, session, model: calls.append((session, model)),
        state={},
    )

    assert calls == [("alpha-foreman", "fable"), ("alpha-grooming", "fable")]
    assert messages[-1] == (
        "models: foremen want fable [pinned] (active account Fable left); "
        "alpha-foreman opus->fable, alpha-grooming opus->fable"
    )


def test_reserved_suffix_literals_stay_inside_signals_topics() -> None:
    offenders: list[str] = []

    for path in sorted(OVERSEER_DIR.glob("*.py")):
        if path.name == "_signals_topics.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in RESERVED_SUFFIX_VALUES:
                offenders.append(f"{path.relative_to(OVERSEER_DIR.parent)}:{node.lineno}")

    assert offenders == []


def test_session_model_exception_outranks_foreman_pin_and_fable_resets(*, tmp_path: Path) -> None:
    state: dict[str, object] = {}
    calls: list[tuple[str, str]] = []

    messages = caam_enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=Path("/tmp"),
        state_path=tmp_path / "state.json",
        session_names=("alpha-foreman", "beta"),
        active_fable=0.0,
        foreman_model="opus",
        session_models=(("alpha-foreman", "fable"), ("beta", "fable")),
        now=1234.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_model=lambda **_: "opus",
        pane_idle=lambda **_: True,
        set_model=lambda *, session, model: calls.append((session, model)),
        state=state,
    )

    assert calls == [("alpha-foreman", "fable"), ("beta", "fable")]
    assert state["session_models"] == {"alpha-foreman": "fable", "beta": "fable"}
    assert messages[-1] == (
        "models: foremen want opus [pinned] (active account Fable EXHAUSTED); "
        "alpha-foreman opus->fable, beta opus->fable; "
        "exceptions: alpha-foreman=fable, beta=fable"
    )


def test_session_model_exception_clear_restores_lower_precedence_rule(*, tmp_path: Path) -> None:
    state: dict[str, object] = {"session_models": {"alpha-foreman": "fable"}}
    calls: list[tuple[str, str]] = []

    messages = caam_enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=Path("/tmp"),
        state_path=tmp_path / "state.json",
        session_names=("alpha-foreman",),
        active_fable=0.0,
        foreman_model="opus",
        session_models=(("alpha-foreman", "auto"),),
        now=1234.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_model=lambda **_: "fable",
        pane_idle=lambda **_: True,
        set_model=lambda *, session, model: calls.append((session, model)),
        state=state,
    )

    assert calls == [("alpha-foreman", "opus")]
    assert state["session_models"] == {}
    assert "exceptions:" not in messages[-1]


def test_session_model_exception_warns_but_does_not_fallback_when_fable_spent(
    *, tmp_path: Path
) -> None:
    state: dict[str, object] = {}

    messages = caam_enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=Path("/tmp"),
        state_path=tmp_path / "state.json",
        session_names=("beta",),
        active_fable=0.0,
        foreman_model=None,
        session_models=(("beta", "fable"),),
        now=1234.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_model=lambda **_: "fable",
        pane_idle=lambda **_: True,
        set_model=lambda **_: None,
        state=state,
    )

    assert messages[0] == (
        "models: WARNING beta pins fable but the active account's Fable is spent -- "
        "that session will be blocked"
    )
    assert messages[-1] == (
        "models: foremen want opus (active account Fable EXHAUSTED); nothing to change; "
        "exceptions: beta=fable"
    )


def test_session_model_exception_persists_before_no_models_early_return(*, tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"

    messages = caam_enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=True,
        home=Path("/tmp"),
        state_path=state_path,
        session_models=(("beta", "opus"),),
        set_model=lambda **_: pytest.fail("no picker keystroke expected"),
        state={},
    )

    assert messages == []
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "session_models": {"beta": "opus"}
    }


def test_session_model_exception_no_models_without_state_path_is_non_driving() -> None:
    messages = caam_enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=True,
        session_models=(("beta", "opus"),),
        set_model=lambda **_: pytest.fail("no picker keystroke expected"),
        state={},
    )

    assert messages == []


def test_session_model_exception_ignores_malformed_requests(*, tmp_path: Path) -> None:
    state: dict[str, object] = {"session_models": {"alpha": "sonnet", "old": "opus"}}

    messages = caam_enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=Path("/tmp"),
        state_path=tmp_path / "state.json",
        session_names=("old",),
        active_fable=58.0,
        foreman_model=None,
        session_models=(("", "fable"), ("old", "sonnet")),
        now=1234.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_model=lambda **_: "opus",
        pane_idle=lambda **_: True,
        set_model=lambda **_: None,
        state=state,
    )

    assert messages[0] == "models: ignoring --session-model==fable (expected session=model)"
    assert (
        messages[1] == "models: ignoring --session-model=old=sonnet (expected fable/opus or auto)"
    )
    assert state["session_models"] == {"old": "opus"}


def test_session_model_option_parser_ignores_malformed_tuples(*, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []
    mixed_session_models: tuple[object, ...] = (
        "not-a-pair",
        ("too-short",),
        ("wrong-type", 1),
        ("beta", "opus"),
    )

    messages = caam_enforcement.enforce_models(
        settings_path=Path("/missing/settings.json"),
        no_models=False,
        home=Path("/tmp"),
        state_path=tmp_path / "state.json",
        session_names=("beta",),
        active_fable=58.0,
        foreman_model=None,
        session_models=mixed_session_models,
        now=1234.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_model=lambda **_: "fable",
        pane_idle=lambda **_: True,
        set_model=lambda *, session, model: calls.append((session, model)),
        state={},
    )

    assert calls == [("beta", "opus")]
    assert messages[-1] == (
        "models: foremen want fable (active account Fable left); beta fable->opus; "
        "exceptions: beta=opus"
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
        five_hour_remaining=90.0,
        seven_day_remaining=90.0,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None if fable is None else 100.0 - fable,
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
