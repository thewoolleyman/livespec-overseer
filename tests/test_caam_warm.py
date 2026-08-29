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


class Caam:
    def __init__(
        self,
        *,
        home: Path,
        replacement_credential: str = "live",
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.home = home
        self.replacement_credential = replacement_credential
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *, args: tuple[str, ...]) -> object:
        self.calls.append(args)
        if self.returncode == 0:
            write_creds(
                path=(
                    self.home
                    / ".local"
                    / "share"
                    / "caam"
                    / "vault"
                    / "claude"
                    / args[2]
                    / ".credentials.json"
                ),
                bearer=self.replacement_credential,
                expires_at_s=9000.0,
            )
        return type(
            "Process",
            (),
            {"returncode": self.returncode, "stdout": self.stdout, "stderr": self.stderr},
        )()


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


def test_resnapshot_active_updates_only_active_vault_snapshot(*, tmp_path: Path):
    module = caam_warm_module()
    assert hasattr(module, "resnapshot_active")
    active = write_snapshot(
        home=tmp_path, name="active", credential="old-active", expires_at_s=1000.0
    )
    idle = write_snapshot(home=tmp_path, name="idle", credential="old-idle", expires_at_s=1000.0)
    live = tmp_path / ".claude" / ".credentials.json"
    write_creds(path=live, bearer="live-active", expires_at_s=9000.0)
    caam = Caam(home=tmp_path, replacement_credential="live-active")
    logs: list[str] = []

    module.resnapshot_active(
        active_name="active",
        home=tmp_path,
        dry_run=False,
        caam_runner=caam,
        logger=logs.append,
    )

    assert caam.calls == [("backup", "claude", "active")]
    assert module.read_creds(path=active / ".credentials.json") == ("live-active", 9000.0)
    assert module.read_creds(path=idle / ".credentials.json") == ("old-idle", 1000.0)
    assert module.read_creds(path=live) == ("live-active", 9000.0)
    assert logs == [
        "resnapshot: active refreshed its token since the last snapshot; vault "
        "updated (prevents orphaning on the next switch)"
    ]


def test_resnapshot_active_skips_dry_run_missing_vault_missing_live_and_matching_snapshot(
    *, tmp_path: Path
):
    module = caam_warm_module()
    assert hasattr(module, "resnapshot_active")
    caam = Caam(home=tmp_path)
    logs: list[str] = []

    module.resnapshot_active(
        active_name="active",
        home=tmp_path,
        dry_run=False,
        caam_runner=caam,
        logger=logs.append,
    )

    _ = write_snapshot(home=tmp_path, name="active", credential="snapshot", expires_at_s=1000.0)
    module.resnapshot_active(
        active_name="active",
        home=tmp_path,
        dry_run=True,
        caam_runner=caam,
        logger=logs.append,
    )
    module.resnapshot_active(
        active_name="active",
        home=tmp_path,
        dry_run=False,
        caam_runner=caam,
        logger=logs.append,
    )
    write_creds(
        path=tmp_path / ".claude" / ".credentials.json",
        bearer="snapshot",
        expires_at_s=9000.0,
    )
    module.resnapshot_active(
        active_name="active",
        home=tmp_path,
        dry_run=False,
        caam_runner=caam,
        logger=logs.append,
    )

    assert caam.calls == []
    assert logs == []


def test_resnapshot_active_logs_failed_backup_without_copying_or_retrying(*, tmp_path: Path):
    module = caam_warm_module()
    assert hasattr(module, "resnapshot_active")
    active = write_snapshot(
        home=tmp_path, name="active", credential="old-active", expires_at_s=1000.0
    )
    live = tmp_path / ".claude" / ".credentials.json"
    write_creds(path=live, bearer="live-active", expires_at_s=9000.0)
    caam = Caam(
        home=tmp_path,
        returncode=1,
        stdout="stdout fallback",
        stderr="backup failed with a long diagnostic that should be clipped after the source's "
        "one hundred and twenty character limit",
    )
    logs: list[str] = []

    module.resnapshot_active(
        active_name="active",
        home=tmp_path,
        dry_run=False,
        caam_runner=caam,
        logger=logs.append,
    )

    assert caam.calls == [("backup", "claude", "active")]
    assert module.read_creds(path=active / ".credentials.json") == ("old-active", 1000.0)
    assert module.read_creds(path=live) == ("live-active", 9000.0)
    assert logs == [
        "resnapshot: FAILED for active -- "
        "backup failed with a long diagnostic that should be clipped after the source's one "
        "hundred and twenty character limit"
    ]


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


def test_warm_profile_treats_still_valid_snapshot_as_success(*, tmp_path: Path):
    """A sandbox token still valid into the future and no newer than the snapshot is
    reported as already valid without copying, keyed on `now` rather than a margin.
    """
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


def test_the_pre_expiry_warm_margin_is_retired(*, tmp_path: Path):
    """The pre-expiry warm-margin gate is gone: `warm_margin_s` no longer exists.

    Its removal is what stops the wasted refresh of a still-valid token
    (overseer-54k2za.47/.52). A lingering `warm_margin_s` would mean the old
    pre-expiry attempt survived somewhere.
    """
    module = caam_warm_module()
    assert not hasattr(module, "warm_margin_s")
    assert "warm_margin_s" not in module.__all__


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


def test_keep_warm_skips_a_still_valid_snapshot_inside_the_old_margin(*, tmp_path: Path):
    """DISCRIMINATOR: a token still valid but within the OLD two-hour margin is now
    SKIPPED, not refreshed.

    Under the retired margin gate an idle snapshot expiring less than two hours out
    was refreshed pre-emptively -- an attempt that cannot renew a valid token and
    only burns an inference request. The expiry-gated rule leaves it for the wake
    scheduled at its own expiry.
    """
    module = caam_warm_module()
    write_creds(
        path=tmp_path / ".claude" / ".credentials.json", bearer="live", expires_at_s=99_000.0
    )
    _ = write_snapshot(home=tmp_path, name="active", credential="active", expires_at_s=99_000.0)
    # Expires one hour out: valid now, but well inside the old 7200s pre-expiry margin.
    _ = write_snapshot(home=tmp_path, name="soon", credential="old", expires_at_s=13_600.0)
    agent = Agent(refreshed_credential="new", after_expires_at_s=40_000.0)
    logs: list[str] = []
    state: dict[str, object] = {}

    module.keep_warm(
        state=state,
        config=warm_config(module=module, active_name="active", home=tmp_path),
        now=10_000.0,
        agent_runner=agent,
        logger=logs.append,
    )

    assert agent.calls == [], "a still-valid snapshot must not be refreshed pre-expiry"
    assert state.get("warm", {}) == {}
    assert logs == []


def test_keep_warm_refreshes_an_expired_snapshot_and_backs_off(*, tmp_path: Path):
    """An idle snapshot whose token has EXPIRED is refreshed, then rate-limited."""
    module = caam_warm_module()
    write_creds(
        path=tmp_path / ".claude" / ".credentials.json", bearer="live", expires_at_s=99_000.0
    )
    _ = write_snapshot(home=tmp_path, name="active", credential="active", expires_at_s=99_000.0)
    _ = write_snapshot(home=tmp_path, name="expired", credential="old", expires_at_s=9_000.0)
    agent = Agent(refreshed_credential="new", after_expires_at_s=40_000.0)
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
        now=10_500.0,
        agent_runner=agent,
        logger=logs.append,
    )

    assert [call[1].name for call in agent.calls] == ["expired"]
    assert state["warm"] == {"expired": {"at": 10_000.0, "ok": True}}
    assert logs == ["warm: expired refreshed, +8.3h"]


def test_keep_warm_attempts_at_the_expiry_boundary_and_skips_just_before_it(*, tmp_path: Path):
    """The gate turns exactly at expiry: expires == now is attempted; a hair before
    it is skipped.
    """
    module = caam_warm_module()
    write_creds(
        path=tmp_path / ".claude" / ".credentials.json", bearer="live", expires_at_s=99_000.0
    )
    _ = write_snapshot(home=tmp_path, name="active", credential="active", expires_at_s=99_000.0)
    _ = write_snapshot(home=tmp_path, name="at-expiry", credential="old", expires_at_s=10_000.0)
    _ = write_snapshot(home=tmp_path, name="not-yet", credential="old", expires_at_s=10_000.1)
    agent = Agent(refreshed_credential="new", after_expires_at_s=40_000.0)
    state: dict[str, object] = {}

    module.keep_warm(
        state=state,
        config=warm_config(module=module, active_name="active", home=tmp_path),
        now=10_000.0,
        agent_runner=agent,
        logger=ignore_log,
    )

    assert [call[1].name for call in agent.calls] == ["at-expiry"]


def test_keep_warm_skips_active_underscore_and_backed_off_profiles(*, tmp_path: Path):
    module = caam_warm_module()
    write_creds(
        path=tmp_path / ".claude" / ".credentials.json", bearer="live", expires_at_s=99_000.0
    )
    _ = write_snapshot(home=tmp_path, name="active", credential="active", expires_at_s=1000.0)
    _ = write_snapshot(home=tmp_path, name="_backup", credential="backup", expires_at_s=1000.0)
    _ = write_snapshot(home=tmp_path, name="valid", credential="valid", expires_at_s=50_000.0)
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


def test_keep_warm_attempts_a_profile_whose_credentials_file_is_absent(*, tmp_path: Path):
    """A snapshot with no credentials file FAILS LOUDLY rather than being skipped.

    The source reads the credentials path unconditionally; an absent file reads as
    an unknown (None) expiry, which is NOT treated as still-valid, so the profile
    is entered, the sandbox preparation fails, and the failure is REPORTED and
    recorded in the backoff memo. A presence guard would turn that into silence,
    hiding exactly the snapshots most likely to need attention. This test pins the
    absence of that guard.
    """

    module = caam_warm_module()
    write_creds(
        path=tmp_path / ".claude" / ".credentials.json", bearer="live", expires_at_s=99_000.0
    )
    _ = write_snapshot(home=tmp_path, name="active", credential="active", expires_at_s=1000.0)
    absent = write_snapshot(home=tmp_path, name="no-creds", credential="old", expires_at_s=1000.0)
    (absent / ".credentials.json").unlink()
    agent = Agent(refreshed_credential="new", after_expires_at_s=30_000.0)
    logs: list[str] = []
    state: dict[str, object] = {}

    module.keep_warm(
        state=state,
        config=warm_config(module=module, active_name="active", home=tmp_path),
        now=10_000.0,
        agent_runner=agent,
        logger=logs.append,
    )

    assert agent.calls == []
    warm_memo = state["warm"]
    assert isinstance(warm_memo, dict)
    assert warm_memo["no-creds"]["ok"] is False
    assert any("no-creds" in line for line in logs)


def test_keep_warm_backoff_applies_after_failure_and_logs_survivable_failure(*, tmp_path: Path):
    module = caam_warm_module()
    write_creds(
        path=tmp_path / ".claude" / ".credentials.json", bearer="live", expires_at_s=99_000.0
    )
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


def test_next_warm_wake_is_the_soonest_future_expiry_plus_the_delay(*, tmp_path: Path):
    """The next maintenance wake is keyed to the soonest FUTURE expiry, so an account
    is refreshed within `delay_s` of its own expiry rather than at a fixed tick.
    """
    module = caam_warm_module()

    wake = module.next_warm_wake(
        expiries=(10_500.0, 10_200.0, None, 20_000.0),
        now=10_000.0,
        delay_s=5.0,
    )

    assert wake == 10_205.0


def test_next_warm_wake_ignores_past_and_unknown_expiries(*, tmp_path: Path):
    """Already-expired and unknown expiries drive no wake: the current pass refreshes
    an expired account, and the recurring backstop covers an unknown one.
    """
    module = caam_warm_module()

    assert (
        module.next_warm_wake(expiries=(9_000.0, None, 10_000.0), now=10_000.0, delay_s=5.0) is None
    )
    assert module.next_warm_wake(expiries=(), now=10_000.0, delay_s=5.0) is None


def test_next_warm_wake_uses_the_configured_delay_default(
    *, tmp_path: Path, monkeypatch: object
) -> None:
    module = caam_warm_module()
    from _pytest.monkeypatch import MonkeyPatch

    assert isinstance(monkeypatch, MonkeyPatch)
    monkeypatch.setenv("CAAM_ROTATE_WARM_WAKE_DELAY_S", "30")

    assert module.warm_wake_delay_s() == 30.0
    assert module.next_warm_wake(expiries=(10_400.0,), now=10_000.0) == 10_430.0


def test_idle_snapshot_expiries_names_only_idle_profiles(*, tmp_path: Path):
    """idle_snapshot_expiries returns each idle snapshot's expiry, excluding the active
    profile and the `_`-prefixed reserved profiles, and None for an unreadable one.
    """
    module = caam_warm_module()
    _ = write_snapshot(home=tmp_path, name="active", credential="a", expires_at_s=5_000.0)
    _ = write_snapshot(home=tmp_path, name="_reserved", credential="r", expires_at_s=6_000.0)
    _ = write_snapshot(home=tmp_path, name="beta", credential="b", expires_at_s=7_000.0)
    gamma = write_snapshot(home=tmp_path, name="gamma", credential="g", expires_at_s=8_000.0)
    (gamma / ".credentials.json").unlink()

    assert module.idle_snapshot_expiries(home=tmp_path, active_name="active") == (7_000.0, None)


def test_idle_snapshot_expiries_is_empty_without_a_vault(*, tmp_path: Path):
    module = caam_warm_module()

    assert module.idle_snapshot_expiries(home=tmp_path, active_name="active") == ()
