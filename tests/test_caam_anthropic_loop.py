"""Tests for the caam account-rotation executable."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

import pytest
from caam_decision import UsageRecord

__all__: list[str] = []


def caam_loop_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_anthropic_loop.py"
    assert module_path.is_file()
    return importlib.import_module("caam_anthropic_loop")


def usage(
    *,
    five_hour: float = 20.0,
    seven_day: float = 30.0,
    seven_day_resets_at: str | None = "2026-08-24T00:00:00Z",
) -> UsageRecord:
    return UsageRecord(
        five_hour=five_hour,
        seven_day=seven_day,
        five_hour_resets_at="2026-08-22T12:00:00Z",
        seven_day_resets_at=seven_day_resets_at,
        fable=10.0,
        fable_resets_at="2026-08-24T00:00:00Z",
    )


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


class FakeProcess:
    returncode = 0
    stdout = '{"tools": [{"tool": "claude", "active_profile": "active"}]}'
    stderr = ""


class RefreshingAgent:
    def __init__(self, *, refreshed_credential: str, after_expires_at_s: float) -> None:
        self.refreshed_credential = refreshed_credential
        self.after_expires_at_s = after_expires_at_s
        self.calls: list[tuple[tuple[str, ...], Path, float]] = []

    def __call__(self, *, args: tuple[str, ...], env: dict[str, str], timeout: float) -> object:
        sandbox = Path(env["CLAUDE_CONFIG_DIR"])
        self.calls.append((args, sandbox, timeout))
        write_creds(
            path=sandbox / ".credentials.json",
            bearer=self.refreshed_credential,
            expires_at_s=self.after_expires_at_s,
        )
        return type("Process", (), {"stdout": "ok\n", "stderr": ""})()


class StaticAgent:
    def __init__(self, *, stdout: str = "", stderr: str = "") -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[tuple[tuple[str, ...], Path, float]] = []

    def __call__(self, *, args: tuple[str, ...], env: dict[str, str], timeout: float) -> object:
        sandbox = Path(env["CLAUDE_CONFIG_DIR"])
        self.calls.append((args, sandbox, timeout))
        return type("Process", (), {"stdout": self.stdout, "stderr": self.stderr})()


def test_console_script_registers_the_caam_operation():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'caam-anthropic-loop = "overseer.caam_anthropic_loop:main"' in pyproject


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ([], {"scheduled": False, "force": False, "dry_run": False}),
        (["--scheduled"], {"scheduled": True, "force": False, "dry_run": False}),
        (["--force", "--dry-run"], {"scheduled": False, "force": True, "dry_run": True}),
        (["--NO-MODELS", "--no-warm"], {"no_models": True, "no_warm": True}),
        (["--foreman-model= FABLE "], {"foreman_model": "fable"}),
        (["--foreman-model", " Opus "], {"foreman_model": "opus"}),
        (["--foreman-model= AUTO "], {"foreman_model": "auto"}),
        (
            ["--session-model= alpha-foreman = FABLE ", "--session-model", "beta= Opus "],
            {"session_models": (("alpha-foreman", "fable"), ("beta", "opus"))},
        ),
    ],
)
def test_flags_use_prefix_matching_lowercasing_and_absent_none(*, argv, expected):
    module = caam_loop_module()

    parsed = module.parse_flags(argv=argv)

    for key, value in expected.items():
        assert getattr(parsed, key) == value
    if "foreman_model" not in expected:
        assert parsed.foreman_model is None
    if "session_models" not in expected:
        assert parsed.session_models == ()


def test_unexpected_exception_reports_fail_type_without_traceback():
    module = caam_loop_module()
    out: list[str] = []

    code = module.main(
        argv=[],
        stdout=out.append,
        pass_runner=lambda *, flags: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert code == 2
    assert out == ["FAIL RuntimeError: boom"]


def test_empty_vault_fails_loud_and_saves_state(*, tmp_path: Path):
    module = caam_loop_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []

    result = module.run_pass(
        flags=module.parse_flags(argv=["--scheduled"]),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        save_state=lambda *, state, state_path: saved.append(dict(state)),
    )

    assert result == 2
    assert out == ["FAIL no profiles found in the caam vault for claude"]
    assert saved == [{}]


def test_active_usage_unreadable_prints_table_then_source_fail(*, tmp_path: Path):
    module = caam_loop_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []
    for name in ("active", "target"):
        (tmp_path / ".local/share/caam/vault/claude" / name).mkdir(parents=True)

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now
        if creds_path == tmp_path / ".claude/.credentials.json":
            return None, "HTTP 429"
        return usage(five_hour=30.0, seven_day=40.0), None

    result = module.run_pass(
        flags=module.parse_flags(argv=["--scheduled"]),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: saved.append(dict(state)),
    )

    assert result == 2
    assert any("PROFILE" in line for line in out)
    assert any(line.startswith("active") and "dark: HTTP 429" in line for line in out)
    assert any(line.startswith("target") and "live" in line for line in out)
    assert out[-1] == "FAIL cannot read usage for active profile active"
    assert next(index for index, line in enumerate(out) if line.startswith("PROFILE")) < out.index(
        "FAIL cannot read usage for active profile active"
    )
    assert saved


def test_unverified_live_rows_are_not_considered_and_get_revive_note(*, tmp_path: Path):
    module = caam_loop_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []
    for name in ("active", "dark"):
        (tmp_path / ".local/share/caam/vault/claude" / name).mkdir(parents=True)

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now
        if creds_path == tmp_path / ".claude/.credentials.json":
            return usage(five_hour=90.0, seven_day=20.0), None
        return None, "no token in snapshot"

    result = module.run_pass(
        flags=module.parse_flags(argv=["--scheduled"]),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: saved.append(dict(state)),
        enforce_models=lambda **kwargs: [],
    )

    assert result == 0
    assert any(
        line
        == (
            "note: dark could not be verified live and were not considered. "
            "Revive with: caam activate claude <name>; claude -p ok; caam backup claude <name>"
        )
        for line in out
    )
    assert saved


def test_dark_profile_is_revived_reprobed_and_becomes_eligible(*, tmp_path: Path):
    module = caam_loop_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []
    write_snapshot(home=tmp_path, name="active", credential="active", expires_at_s=30_000.0)
    write_snapshot(home=tmp_path, name="dark", credential="old-dark", expires_at_s=1_000.0)
    write_creds(
        path=tmp_path / ".claude" / ".credentials.json",
        bearer="active",
        expires_at_s=30_000.0,
    )
    agent = RefreshingAgent(refreshed_credential="new-dark", after_expires_at_s=30_000.0)
    seen_fetches: list[Path] = []

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now
        seen_fetches.append(creds_path)
        token = json.loads(creds_path.read_text(encoding="utf-8"))["claudeAiOauth"]["accessToken"]
        if token == "active":
            return usage(five_hour=90.0, seven_day=90.0), None
        if token == "new-dark":
            return usage(five_hour=10.0, seven_day=10.0), None
        return None, "token expired 0.3h ago"

    result = module.run_pass(
        flags=module.parse_flags(argv=["--force"]),
        home=tmp_path,
        now=2_000.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: saved.append(dict(state)),
        agent_runner=agent,
        switch_account=lambda *, request: module.SwitchResult(
            exit_code=0,
            lines=(f"SWITCHED {request.active_name} -> {request.target.name}",),
        ),
        enforce_models=lambda **kwargs: [],
    )

    assert result == 0
    assert agent.calls == [
        (
            ("claude", "-p", "ok"),
            tmp_path / ".local" / "state" / "caam-usage-rotate" / "warm" / "dark",
            180.0,
        )
    ]
    assert any(line == "revive: dark refreshed, +7.8h" for line in out)
    assert out[-1] == "SWITCHED active -> dark"
    assert (
        seen_fetches.count(tmp_path / ".local/share/caam/vault/claude/dark/.credentials.json") == 2
    )
    assert saved


def test_revive_attempts_only_already_dark_profiles(*, tmp_path: Path):
    module = caam_loop_module()
    out: list[str] = []
    write_snapshot(home=tmp_path, name="active", credential="active", expires_at_s=30_000.0)
    write_snapshot(home=tmp_path, name="idle", credential="idle", expires_at_s=1_000.0)
    write_creds(
        path=tmp_path / ".claude" / ".credentials.json",
        bearer="active",
        expires_at_s=30_000.0,
    )
    agent = RefreshingAgent(refreshed_credential="new-idle", after_expires_at_s=30_000.0)

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now, creds_path
        return usage(five_hour=20.0, seven_day=20.0), None

    result = module.run_pass(
        flags=module.parse_flags(argv=["--scheduled"]),
        home=tmp_path,
        now=2_000.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: None,
        agent_runner=agent,
        enforce_models=lambda **kwargs: [],
    )

    assert result == 0
    assert agent.calls == []
    assert not any(line.startswith("revive:") for line in out)


def test_failed_revive_leaves_dark_profile_unverified(*, tmp_path: Path):
    module = caam_loop_module()
    out: list[str] = []
    _ = write_snapshot(home=tmp_path, name="active", credential="active", expires_at_s=30_000.0)
    _ = write_snapshot(home=tmp_path, name="dark", credential="old-dark", expires_at_s=1_000.0)
    write_creds(
        path=tmp_path / ".claude" / ".credentials.json",
        bearer="active",
        expires_at_s=30_000.0,
    )
    agent = StaticAgent(stderr="OAuth session expired and could not be refreshed\n")

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now
        token = json.loads(creds_path.read_text(encoding="utf-8"))["claudeAiOauth"]["accessToken"]
        if token == "active":
            return usage(five_hour=90.0, seven_day=90.0), None
        return None, "token expired 0.3h ago"

    result = module.run_pass(
        flags=module.parse_flags(argv=["--force"]),
        home=tmp_path,
        now=2_000.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: None,
        agent_runner=agent,
        enforce_models=lambda **kwargs: [],
    )

    assert result == 0
    assert len(agent.calls) == 1
    assert any(
        line == "revive: dark no refresh -- OAuth session expired and could not be refreshed"
        for line in out
    )
    assert any(
        line
        == (
            "note: dark could not be verified live and were not considered. "
            "Revive with: caam activate claude <name>; claude -p ok; caam backup claude <name>"
        )
        for line in out
    )


def test_revive_success_with_failed_reprobe_leaves_profile_unverified(*, tmp_path: Path):
    module = caam_loop_module()
    out: list[str] = []
    _ = write_snapshot(home=tmp_path, name="active", credential="active", expires_at_s=30_000.0)
    _ = write_snapshot(home=tmp_path, name="dark", credential="old-dark", expires_at_s=1_000.0)
    write_creds(
        path=tmp_path / ".claude" / ".credentials.json",
        bearer="active",
        expires_at_s=30_000.0,
    )
    agent = RefreshingAgent(refreshed_credential="new-dark", after_expires_at_s=30_000.0)

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now
        token = json.loads(creds_path.read_text(encoding="utf-8"))["claudeAiOauth"]["accessToken"]
        if token == "active":
            return usage(five_hour=90.0, seven_day=90.0), None
        return None, "HTTP 429"

    result = module.run_pass(
        flags=module.parse_flags(argv=["--force"]),
        home=tmp_path,
        now=2_000.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: None,
        agent_runner=agent,
        enforce_models=lambda **kwargs: [],
    )

    assert result == 0
    assert len(agent.calls) == 1
    assert any(line == "revive: dark refreshed, +7.8h" for line in out)
    assert any(
        line
        == (
            "note: dark could not be verified live and were not considered. "
            "Revive with: caam activate claude <name>; claude -p ok; caam backup claude <name>"
        )
        for line in out
    )


def test_dry_run_returns_zero_and_saves_state(*, tmp_path: Path):
    module = caam_loop_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []
    for name in ("active", "target"):
        (tmp_path / ".local/share/caam/vault/claude" / name).mkdir(parents=True)

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now
        if creds_path == tmp_path / ".claude/.credentials.json":
            return usage(five_hour=90.0, seven_day=20.0), None
        return usage(five_hour=20.0, seven_day=10.0), None

    result = module.run_pass(
        flags=module.parse_flags(argv=["--dry-run"]),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: saved.append(dict(state)),
        enforce_models=lambda **kwargs: [],
    )

    assert result == 0
    assert any(line.startswith("DRY-RUN would switch active -> target") for line in out)
    assert saved


def test_switch_path_returns_switch_result_and_preserves_switch_save(*, tmp_path: Path):
    module = caam_loop_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []
    for name in ("active", "target"):
        (tmp_path / ".local/share/caam/vault/claude" / name).mkdir(parents=True)

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now
        if creds_path == tmp_path / ".claude/.credentials.json":
            return usage(five_hour=90.0, seven_day=20.0), None
        return usage(five_hour=20.0, seven_day=10.0), None

    result = module.run_pass(
        flags=module.parse_flags(argv=["--force"]),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: saved.append(dict(state)),
        switch_account=lambda *, request: module.SwitchResult(
            exit_code=0,
            lines=("SWITCHED active -> target",),
        ),
        enforce_models=lambda **kwargs: [],
    )

    assert result == 0
    assert out[-1] == "SWITCHED active -> target"
    assert saved
