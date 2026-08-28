"""Decouple credential-expiry from cache-figure staleness (overseer-54k2za.47).

Revive is gated on a row being "dark", and a row goes dark only once its cached
QUOTA FIGURES age past the reporting ceiling -- up to an hour after the stored
CREDENTIAL has actually expired. These tests pin the decoupled behaviour: the
credential-expired fact is carried onto the polled row the instant it is known, and
revive fires on that fact regardless of whether the cached figures are still fresh
enough to render.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

from caam_decision import ProfileUsage, UsageRecord
from caam_decision_protection import CandidatePolicy, candidate_allowed

__all__: list[str] = []


def profile_state_module() -> ModuleType:
    return importlib.import_module("caam_profile_state")


def revive_module() -> ModuleType:
    return importlib.import_module("caam_anthropic_revive")


def usage(*, five_hour: float = 20.0, seven_day: float = 30.0) -> UsageRecord:
    return UsageRecord(
        five_hour=five_hour,
        seven_day=seven_day,
        five_hour_resets_at="2026-08-22T12:00:00Z",
        seven_day_resets_at="2026-08-24T00:00:00Z",
        fable=10.0,
        fable_resets_at="2026-08-24T00:00:00Z",
    )


def write_creds(*, path: Path, bearer: str, expires_at_s: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    oauth: dict[str, object] = {"accessToken": bearer, "expiresAt": int(expires_at_s * 1000)}
    _ = path.write_text(json.dumps({"claudeAiOauth": oauth}), encoding="utf-8")


def write_snapshot(*, home: Path, name: str, credential: str, expires_at_s: float) -> Path:
    profile = home / ".local" / "share" / "caam" / "vault" / "claude" / name
    write_creds(path=profile / ".credentials.json", bearer=credential, expires_at_s=expires_at_s)
    _ = (profile / ".claude.json").write_text('{"oauthAccount":{}}\n', encoding="utf-8")
    _ = (profile / "settings.json").write_text('{"effortLevel":"high"}\n', encoding="utf-8")
    return profile


class RefreshingAgent:
    def __init__(self, *, refreshed_credential: str, after_expires_at_s: float) -> None:
        self.refreshed_credential = refreshed_credential
        self.after_expires_at_s = after_expires_at_s
        self.calls: list[Path] = []

    def __call__(self, *, args: tuple[str, ...], env: dict[str, str], timeout: float) -> object:
        del args, timeout
        sandbox = Path(env["CLAUDE_CONFIG_DIR"])
        self.calls.append(sandbox)
        write_creds(
            path=sandbox / ".credentials.json",
            bearer=self.refreshed_credential,
            expires_at_s=self.after_expires_at_s,
        )
        return type("Process", (), {"stdout": "ok\n", "stderr": ""})()


def _cache_entry(*, at: float) -> dict[str, object]:
    return {
        "at": at,
        "five_hour": 12.0,
        "seven_day": 34.0,
        "five_hour_resets_at": "2026-08-21T12:00:00Z",
        "seven_day_resets_at": "2026-08-25T12:00:00Z",
        "fable": 10.0,
        "fable_resets_at": "2026-08-25T12:00:00Z",
    }


def test_credential_expired_discriminator_covers_every_reason():
    module = profile_state_module()

    assert module._credential_expired(why="token expired 1.0h ago") is True
    assert module._credential_expired(why="no token in snapshot") is True
    assert module._credential_expired(why="HTTP 429") is False
    assert module._credential_expired(why="no snapshot") is False
    assert module._credential_expired(why=None) is False


def test_expired_credential_with_fresh_cache_is_flagged_credential_expired(*, tmp_path: Path):
    module = profile_state_module()
    write_snapshot(home=tmp_path, name="idle", credential="old", expires_at_s=1000.0)
    state: dict[str, object] = {"profiles": {"idle": _cache_entry(at=3600.0)}}

    def fetcher(*, creds_path: Path, now: float | None = None):
        del creds_path, now
        return None, "token expired 1.0h ago"

    rows = module.poll_profiles(
        active_name="other", state=state, home=tmp_path, now=5400.0, fetcher=fetcher
    )
    idle = next(row for row in rows if row.name == "idle")

    assert idle.source.startswith("cached ")
    assert idle.usage is not None
    assert idle.credential_expired is True


def test_transient_failure_with_fresh_cache_is_not_credential_expired(*, tmp_path: Path):
    module = profile_state_module()
    write_snapshot(home=tmp_path, name="idle", credential="tok", expires_at_s=9_000_000.0)
    state: dict[str, object] = {"profiles": {"idle": _cache_entry(at=3600.0)}}

    def fetcher(*, creds_path: Path, now: float | None = None):
        del creds_path, now
        return None, "HTTP 429"

    rows = module.poll_profiles(
        active_name="other", state=state, home=tmp_path, now=5400.0, fetcher=fetcher
    )
    idle = next(row for row in rows if row.name == "idle")

    assert idle.source.startswith("cached ")
    assert idle.credential_expired is False


def test_revive_fires_on_a_credential_expired_cached_row(*, tmp_path: Path):
    module = revive_module()
    write_snapshot(home=tmp_path, name="idle", credential="old", expires_at_s=1000.0)
    agent = RefreshingAgent(refreshed_credential="fresh", after_expires_at_s=1_000_000.0)
    logged: list[str] = []

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now
        token = json.loads(creds_path.read_text(encoding="utf-8"))["claudeAiOauth"]["accessToken"]
        if token == "fresh":
            return usage(five_hour=5.0, seven_day=5.0), None
        return None, "token expired 1.0h ago"

    cached_row = ProfileUsage(
        name="idle",
        source="cached 0.3h",
        usage=usage(five_hour=12.0, seven_day=34.0),
        credential_expired=True,
    )
    context = module.ReviveContext(
        active_name="active",
        state={},
        home=tmp_path,
        now=2000.0,
        fetcher=fetcher,
        agent_runner=agent,
        logger=logged.append,
    )

    revived = module.revive_dark_profiles(context=context, profiles=(cached_row,))
    idle = next(row for row in revived if row.name == "idle")

    assert agent.calls, "revive must attempt a refresh on a credential-expired cached row"
    assert idle.source == "live"
    assert idle.usage == usage(five_hour=5.0, seven_day=5.0)


def test_credential_expired_cached_row_is_not_a_rotation_candidate():
    row = ProfileUsage(
        name="idle",
        source="cached 0.3h",
        usage=usage(five_hour=5.0, seven_day=5.0),
        credential_expired=True,
    )
    policy = CandidatePolicy(
        current=usage(five_hour=90.0, seven_day=90.0),
        gain_needed=0.01,
        dimension="five_hour",
        enforce_reserve=False,
        weekly_reserve=10.0,
    )

    assert candidate_allowed(profile=row, active_name="active", policy=policy) is False
