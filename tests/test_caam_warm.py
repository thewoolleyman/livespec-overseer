"""Tests for caam idle-profile keep-warm maintenance."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

__all__: list[str] = []


def caam_warm_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_warm.py"
    assert module_path.is_file()
    return importlib.import_module("caam_warm")


def write_creds(*, path: Path, bearer: str, expires_at_s: float | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    oauth: dict[str, object] = {"accessToken": bearer}
    if expires_at_s is not None:
        oauth["expiresAt"] = int(expires_at_s * 1000)
    _ = path.write_text(json.dumps({"claudeAiOauth": oauth}), encoding="utf-8")


def write_snapshot(*, home: Path, name: str, credential: str, expires_at_s: float) -> Path:
    profile = home / ".local" / "share" / "caam" / "vault" / "claude" / name
    write_creds(path=profile / ".credentials.json", bearer=credential, expires_at_s=expires_at_s)
    _ = (profile / ".claude.json").write_text('{"oauthAccount":{}}\n', encoding="utf-8")
    _ = (profile / "settings.json").write_text('{"effortLevel":"high"}\n', encoding="utf-8")
    return profile


class Agent:
    def __init__(
        self,
        *,
        refreshed_credential: str | None = None,
        after_expires_at_s: float | None = None,
        stdout: str = "ok\n",
        stderr: str = "",
        fail: BaseException | None = None,
    ) -> None:
        self.refreshed_credential = refreshed_credential
        self.after_expires_at_s = after_expires_at_s
        self.stdout = stdout
        self.stderr = stderr
        self.fail = fail
        self.calls: list[tuple[tuple[str, ...], Path, float]] = []

    def __call__(self, *, args: tuple[str, ...], env: dict[str, str], timeout: float) -> object:
        sandbox = Path(env["CLAUDE_CONFIG_DIR"])
        self.calls.append((args, sandbox, timeout))
        if self.fail is not None:
            raise self.fail
        if self.refreshed_credential is not None:
            write_creds(
                path=sandbox / ".credentials.json",
                bearer=self.refreshed_credential,
                expires_at_s=0.0 if self.after_expires_at_s is None else self.after_expires_at_s,
            )
        return type("Process", (), {"stdout": self.stdout, "stderr": self.stderr})()


def warm_config(
    *,
    module: ModuleType,
    active_name: str,
    home: Path,
    dry_run: bool = False,
    no_warm: bool = False,
) -> object:
    return module.WarmConfig(
        active_name=active_name,
        home=home,
        dry_run=dry_run,
        no_warm=no_warm,
    )


def ignore_log(message: str) -> None:
    del message


def test_warm_profile_delegates_refresh_to_agent_sandbox_and_copies_back(*, tmp_path: Path):
    module = caam_warm_module()
    profile = write_snapshot(home=tmp_path, name="idle", credential="old", expires_at_s=1000.0)
    write_creds(path=tmp_path / ".claude" / ".credentials.json", bearer="live", expires_at_s=9000.0)
    agent = Agent(refreshed_credential="new", after_expires_at_s=30_000.0)
    logs: list[str] = []
    stale_sandbox = tmp_path / ".local" / "state" / "caam-usage-rotate" / "warm" / "idle"
    stale_sandbox.mkdir(parents=True)
    _ = (stale_sandbox / "stale").write_text("stale", encoding="utf-8")

    result = module.warm_profile(
        name="idle",
        home=tmp_path,
        now=2000.0,
        agent_runner=agent,
        logger=logs.append,
    )

    assert result.ok is True
    assert result.detail == "refreshed, +7.8h"
    assert module.read_creds(path=profile / ".credentials.json") == ("new", 30_000.0)
    assert (profile / ".credentials.json").stat().st_mode & 0o777 == 0o600
    assert agent.calls == [
        (
            ("claude", "-p", "ok"),
            tmp_path / ".local" / "state" / "caam-usage-rotate" / "warm" / "idle",
            180.0,
        )
    ]
    assert not agent.calls[0][1].exists()
    assert module.__file__ is not None
    assert "api.anthropic.com/api/oauth/token" not in Path(module.__file__).read_text(
        encoding="utf-8"
    )
    assert logs == []


def test_warm_profile_reports_no_refresh_with_agent_output_without_copying_back(*, tmp_path: Path):
    module = caam_warm_module()
    profile = write_snapshot(home=tmp_path, name="idle", credential="old", expires_at_s=1000.0)
    write_creds(path=tmp_path / ".claude" / ".credentials.json", bearer="live", expires_at_s=9000.0)
    agent = Agent(stdout="", stderr="OAuth session expired and could not be refreshed\nsecond")

    result = module.warm_profile(
        name="idle",
        home=tmp_path,
        now=2000.0,
        agent_runner=agent,
        logger=ignore_log,
    )

    assert result.ok is False
    assert result.detail == "no refresh -- OAuth session expired and could not be refreshed"
    assert module.read_creds(path=profile / ".credentials.json") == ("old", 1000.0)
    assert not agent.calls[0][1].exists()


def test_warm_profile_treats_still_comfortably_valid_snapshot_as_success(*, tmp_path: Path):
    module = caam_warm_module()
    profile = write_snapshot(home=tmp_path, name="idle", credential="old", expires_at_s=20_000.0)
    write_creds(path=tmp_path / ".claude" / ".credentials.json", bearer="live", expires_at_s=9000.0)
    agent = Agent(refreshed_credential="old", after_expires_at_s=20_000.0)

    result = module.warm_profile(
        name="idle",
        home=tmp_path,
        now=12_000.0,
        agent_runner=agent,
        logger=ignore_log,
    )

    assert result.ok is True
    assert result.detail == "already valid, no refresh needed"
    assert module.read_creds(path=profile / ".credentials.json") == ("old", 20_000.0)


def test_warm_profile_reports_exception_removes_sandbox_and_checks_live_token(*, tmp_path: Path):
    module = caam_warm_module()
    _ = write_snapshot(home=tmp_path, name="idle", credential="old", expires_at_s=1000.0)
    live = tmp_path / ".claude" / ".credentials.json"
    write_creds(path=live, bearer="live-before", expires_at_s=9000.0)
    logs: list[str] = []

    class MutatingAgent:
        def __call__(self, *, args: tuple[str, ...], env: dict[str, str], timeout: float) -> object:
            del args, env, timeout
            write_creds(path=live, bearer="live-after", expires_at_s=9000.0)
            raise OSError("agent failed")

    result = module.warm_profile(
        name="idle",
        home=tmp_path,
        now=2000.0,
        agent_runner=MutatingAgent(),
        logger=logs.append,
    )

    assert result.ok is False
    assert result.detail == "OSError: agent failed"
    assert not (tmp_path / ".local" / "state" / "caam-usage-rotate" / "warm" / "idle").exists()
    assert logs == [
        "FAIL keep-warm altered the LIVE credential -- this must never happen; "
        "investigate before trusting the next rotation"
    ]


def test_keep_warm_skips_disabled_dry_run_and_missing_vault(*, tmp_path: Path):
    module = caam_warm_module()
    agent = Agent(refreshed_credential="new", after_expires_at_s=30_000.0)
    state: dict[str, object] = {}

    module.keep_warm(
        state=state,
        config=warm_config(module=module, active_name="active", home=tmp_path),
        now=2000.0,
        agent_runner=agent,
        logger=ignore_log,
    )
    module.keep_warm(
        state=state,
        config=warm_config(module=module, active_name="active", home=tmp_path, dry_run=True),
        now=2000.0,
        agent_runner=agent,
        logger=ignore_log,
    )
    module.keep_warm(
        state=state,
        config=warm_config(module=module, active_name="active", home=tmp_path, no_warm=True),
        now=2000.0,
        agent_runner=agent,
        logger=ignore_log,
    )

    assert agent.calls == []
    assert state == {}


def test_keep_warm_skips_active_underscore_valid_and_backed_off_profiles(*, tmp_path: Path):
    module = caam_warm_module()
    write_creds(path=tmp_path / ".claude" / ".credentials.json", bearer="live", expires_at_s=9000.0)
    _ = write_snapshot(home=tmp_path, name="active", credential="active", expires_at_s=1000.0)
    _ = write_snapshot(home=tmp_path, name="_backup", credential="backup", expires_at_s=1000.0)
    _ = write_snapshot(
        home=tmp_path, name="valid-boundary", credential="valid", expires_at_s=17_200.1
    )
    _ = write_snapshot(home=tmp_path, name="backed-off", credential="old", expires_at_s=1000.0)
    due = write_snapshot(home=tmp_path, name="due", credential="old", expires_at_s=1000.0)
    (due / "settings.json").unlink()
    agent = Agent(refreshed_credential="new", after_expires_at_s=30_000.0)
    logs: list[str] = []
    state: dict[str, object] = {
        "warm": {
            "backed-off": {"at": 9999.0, "ok": False},
            "due": {"at": "never", "ok": False},
        }
    }

    module.keep_warm(
        state=state,
        config=warm_config(module=module, active_name="active", home=tmp_path),
        now=10_000.0,
        agent_runner=agent,
        logger=logs.append,
    )

    assert [call[1].name for call in agent.calls] == ["due"]
    assert state["warm"] == {
        "backed-off": {"at": 9999.0, "ok": False},
        "due": {"at": 10_000.0, "ok": True},
    }
    assert logs == ["warm: due refreshed, +5.6h"]


def test_keep_warm_attempts_at_staleness_boundary_and_backs_off_success(*, tmp_path: Path):
    module = caam_warm_module()
    write_creds(path=tmp_path / ".claude" / ".credentials.json", bearer="live", expires_at_s=9000.0)
    _ = write_snapshot(home=tmp_path, name="boundary", credential="old", expires_at_s=17_200.0)
    agent = Agent(refreshed_credential="new", after_expires_at_s=30_000.0)
    state: dict[str, object] = {}

    module.keep_warm(
        state=state,
        config=warm_config(module=module, active_name="active", home=tmp_path),
        now=10_000.0,
        agent_runner=agent,
        logger=ignore_log,
    )
    module.keep_warm(
        state=state,
        config=warm_config(module=module, active_name="active", home=tmp_path),
        now=10_001.0,
        agent_runner=agent,
        logger=ignore_log,
    )

    assert len(agent.calls) == 1
    assert state["warm"] == {"boundary": {"at": 10_000.0, "ok": True}}


def test_keep_warm_backoff_applies_after_failure_and_logs_survivable_failure(*, tmp_path: Path):
    module = caam_warm_module()
    write_creds(path=tmp_path / ".claude" / ".credentials.json", bearer="live", expires_at_s=9000.0)
    _ = write_snapshot(home=tmp_path, name="orphan", credential="old", expires_at_s=1000.0)
    agent = Agent(stdout="", stderr="You've hit your monthly spend limit\n")
    logs: list[str] = []
    state: dict[str, object] = {}

    module.keep_warm(
        state=state,
        config=warm_config(module=module, active_name="active", home=tmp_path),
        now=10_000.0,
        agent_runner=agent,
        logger=logs.append,
    )
    module.keep_warm(
        state=state,
        config=warm_config(module=module, active_name="active", home=tmp_path),
        now=10_001.0,
        agent_runner=agent,
        logger=logs.append,
    )

    assert len(agent.calls) == 1
    assert state["warm"] == {"orphan": {"at": 10_000.0, "ok": False}}
    assert logs == ["warm: orphan FAILED -- no refresh -- You've hit your monthly spend limit"]
