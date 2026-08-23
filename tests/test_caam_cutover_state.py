"""Cutover-state regressions for the caam Anthropic rotation loop."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

import caam_enforcement
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import UsageRecord

__all__: list[str] = []


class FakeProcess:
    returncode = 0
    stdout = '{"tools": [{"tool": "claude", "active_profile": "active"}]}'
    stderr = ""


def caam_profile_state_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_profile_state.py"
    assert module_path.is_file()
    return importlib.import_module("caam_profile_state")


def test_loop_state_path_is_the_caam_state_module_path(*, tmp_path: Path) -> None:
    module = caam_profile_state_module()

    assert module.state_path(home=tmp_path) == tmp_path / module.STATE_REL


def test_full_pass_preserves_live_cutover_state_and_unknown_keys(*, tmp_path: Path) -> None:
    module = caam_profile_state_module()
    home = tmp_path / "home"
    _write_caam_home(home=home, sessions=("homelab-foreman",))
    live_state = {
        "session-models": {
            "homelab-foreman": "fable",
            "livespec-overseer-foreman": "fable",
        },
        "foreman_model": "opus",
        "last-switch": {
            "from": "anthropic-1",
            "to": "anthropic-0",
            "at": "2026-08-22T20:15:39Z",
        },
        "models": {
            "homelab-foreman": {"want": "fable", "at": 1787394200.0},
            "other-foreman": {"want": "opus", "at": 1787394200.0},
        },
        "profiles": {
            "active": {"at": 1787394200.0, "five_hour": 20.0, "seven_day": 30.0},
            "_active-before-refresh": {
                "at": 1787394200.0,
                "five_hour": 21.0,
                "seven_day": 31.0,
            },
        },
        "future-key": {"kept": True},
    }
    state_path = module.state_path(home=home)
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps(live_state), encoding="utf-8")
    before = json.loads(state_path.read_text(encoding="utf-8"))
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
        now=1787395200.0,
        stdout=lines.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=_usage_fetcher(),
        switch_account=lambda **_: None,
        agent_runner=_agent_runner(),
        enforce_models=lambda **_: [],
    )

    assert code == 0
    after = json.loads(state_path.read_text(encoding="utf-8"))
    assert after["session-models"] == before["session-models"]
    assert after["foreman_model"] == before["foreman_model"]
    assert after["last-switch"] == before["last-switch"]
    assert after["models"] == before["models"]
    assert (
        after["profiles"]["_active-before-refresh"] == before["profiles"]["_active-before-refresh"]
    )
    assert after["future-key"] == before["future-key"]


def test_live_cutover_session_pins_override_global_foreman_pin(*, tmp_path: Path) -> None:
    state = {
        "foreman_model": "opus",
        "session-models": {
            "homelab-foreman": "fable",
            "livespec-overseer-foreman": "fable",
        },
    }
    calls: list[tuple[str, str]] = []

    messages = caam_enforcement.enforce_models(
        settings_path=tmp_path / "settings.json",
        no_models=False,
        home=tmp_path,
        state_path=tmp_path / "state.json",
        session_names=(
            "homelab-foreman",
            "livespec-overseer-foreman",
            "other-foreman",
        ),
        active_fable=42.0,
        foreman_model=None,
        session_models=(),
        now=1787395200.0,
        pane_pid=lambda **_: 101,
        children_of=lambda **_: (),
        environ_of=lambda **_: b"CLAUDE_CODE_SESSION_ID=sid-1\0",
        pane_model=lambda **_: "opus",
        pane_idle=lambda **_: True,
        set_model=lambda *, session, model: calls.append((session, model)),
        state=state,
    )

    assert calls == [
        ("homelab-foreman", "fable"),
        ("livespec-overseer-foreman", "fable"),
    ]
    assert "other-foreman" not in {session for session, _model in calls}
    assert messages[-1] == (
        "models: foremen want opus [pinned] (active account Fable left); "
        "homelab-foreman opus->fable, livespec-overseer-foreman opus->fable; "
        "exceptions: homelab-foreman=fable, livespec-overseer-foreman=fable"
    )


def _write_caam_home(*, home: Path, sessions: tuple[str, ...]) -> None:
    vault_profile = home / ".local/share/caam/vault/claude/active"
    projects = home / ".claude/projects/project"
    settings = home / ".claude/settings.json"
    vault_profile.mkdir(parents=True)
    projects.mkdir(parents=True)
    settings.parent.mkdir(parents=True, exist_ok=True)
    (home / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": "account-1"}}),
        encoding="utf-8",
    )
    (vault_profile / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"accountUuid": "account-1"}}),
        encoding="utf-8",
    )
    (vault_profile / ".credentials.json").write_text("{}", encoding="utf-8")
    for session in sessions:
        (projects / f"{session}.jsonl").write_text(
            json.dumps({"message": {"model": "claude-opus-5"}}) + "\n",
            encoding="utf-8",
        )


def _usage_fetcher():
    def fetcher(
        *, creds_path: Path, now: float | None = None
    ) -> tuple[UsageRecord | None, str | None]:
        del creds_path, now
        return (
            UsageRecord(
                five_hour=20.0,
                seven_day=30.0,
                five_hour_resets_at="2026-08-22T12:00:00Z",
                seven_day_resets_at="2026-08-24T00:00:00Z",
                fable=42.0,
                fable_resets_at="2026-08-24T00:00:00Z",
            ),
            None,
        )

    return fetcher


def _agent_runner():
    def run_agent(*, args: tuple[str, ...], env: dict[str, str], timeout: float):
        del args, env, timeout
        return FakeProcess()

    return run_agent
