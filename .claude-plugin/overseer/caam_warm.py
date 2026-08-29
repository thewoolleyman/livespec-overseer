"""Keep idle caam profiles warm enough to remain switchable."""
# livespec-lloc-soft-band-owner: overseer-54k2za.52

from __future__ import annotations

import os
import shutil
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Protocol, cast

from caam_profile_state import STATE_REL, caam_vault, live_creds_path
from caam_usage import read_creds

__all__: list[str] = [
    "AgentProcess",
    "AgentRunner",
    "Logger",
    "ResnapshotProcess",
    "ResnapshotRunner",
    "WarmConfig",
    "WarmResult",
    "emit_next_warm_wake",
    "idle_snapshot_expiries",
    "keep_warm",
    "next_warm_wake",
    "read_creds",
    "resnapshot_active",
    "token_of",
    "warm_profile",
    "warm_retry_s",
    "warm_wake_delay_s",
]

_WARM_RETRY_DEFAULT_S = "3600"
_WARM_WAKE_DELAY_DEFAULT_S = "15"
_AGENT_TIMEOUT_S = 180.0
_TOOL: Final = "claude"
_LIVE_CHANGED = (
    "FAIL keep-warm altered the LIVE credential -- this must never happen; "
    "investigate before trusting the next rotation"
)


class AgentProcess(Protocol):
    stdout: str
    stderr: str


class AgentRunner(Protocol):
    def __call__(
        self,
        *,
        args: tuple[str, ...],
        env: dict[str, str],
        timeout: float,
    ) -> AgentProcess: ...


class ResnapshotProcess(Protocol):
    returncode: int
    stdout: str
    stderr: str


class ResnapshotRunner(Protocol):
    def __call__(self, *, args: tuple[str, ...]) -> ResnapshotProcess: ...


class Logger(Protocol):
    def __call__(self, message: str) -> None: ...


@dataclass(frozen=True, kw_only=True)
class WarmConfig:
    active_name: str
    home: Path
    dry_run: bool
    no_warm: bool


@dataclass(frozen=True, kw_only=True)
class WarmResult:
    ok: bool
    detail: str


def warm_retry_s() -> float:
    return float(os.environ.get("CAAM_ROTATE_WARM_RETRY_S", _WARM_RETRY_DEFAULT_S))


def warm_wake_delay_s() -> float:
    return float(os.environ.get("CAAM_ROTATE_WARM_WAKE_DELAY_S", _WARM_WAKE_DELAY_DEFAULT_S))


def token_of(*, path: Path) -> str | None:
    token, _ = read_creds(path=path)
    return token


def resnapshot_active(
    *,
    active_name: str,
    home: Path,
    dry_run: bool,
    caam_runner: ResnapshotRunner,
    logger: Logger,
) -> None:
    """Keep the ACTIVE profile's snapshot equal to the live credential."""

    vault = caam_vault(home=home)
    if dry_run or not vault.is_dir():
        return
    live = token_of(path=live_creds_path(home=home))
    snap = token_of(path=vault / active_name / ".credentials.json")
    if live is None or live == snap:
        return
    result = caam_runner(args=("backup", _TOOL, active_name))
    if result.returncode == 0:
        logger(
            f"resnapshot: {active_name} refreshed its token since the last snapshot; vault "
            "updated (prevents orphaning on the next switch)"
        )
    else:
        detail = (result.stderr or result.stdout).strip()[:120]
        logger(f"resnapshot: FAILED for {active_name} -- {detail}")


def _is_idle_profile(*, name: str, active_name: str) -> bool:
    return not name.startswith("_") and name != active_name


def keep_warm(
    *,
    state: dict[str, object],
    config: WarmConfig,
    agent_runner: AgentRunner,
    logger: Logger,
    now: float | None = None,
) -> None:
    """Refresh idle snapshots whose access token has EXPIRED, so they stay switchable.

    The refresh is EXPIRY-GATED, never pre-expiry: the delegated agent renews only
    an already-expired credential, so an attempt on a still-valid token cannot
    refresh it and merely burns an inference request (overseer-54k2za.47). A valid
    snapshot is therefore skipped and left for the wake scheduled at its own expiry
    (`next_warm_wake`). An expired snapshot is refreshed subject only to the
    per-account rate backoff (`warm_retry_s`) that spec.md's actively-maintained
    clause requires so a persistently unrefreshable account is neither abandoned
    nor retried without limit on the rate.
    """

    vault = caam_vault(home=config.home)
    if config.no_warm or config.dry_run or not vault.is_dir():
        return

    checked_at = time.time() if now is None else now
    memo = _warm_memo(state=state)
    for profile_path in sorted(vault.iterdir(), key=lambda path: path.name):
        name = profile_path.name
        if not _is_idle_profile(name=name, active_name=config.active_name):
            continue
        _, expires_at = read_creds(path=profile_path / ".credentials.json")
        if expires_at is not None and expires_at > checked_at:
            continue
        last = _last_attempt_at(memo=memo, name=name)
        if checked_at - last < warm_retry_s():
            continue
        result = warm_profile(
            name=name,
            home=config.home,
            now=checked_at,
            agent_runner=agent_runner,
            logger=logger,
        )
        memo[name] = {"at": checked_at, "ok": result.ok}
        logger(f"warm: {name} {result.detail if result.ok else 'FAILED -- ' + result.detail}")


def idle_snapshot_expiries(*, home: Path, active_name: str) -> tuple[float | None, ...]:
    """Each idle profile snapshot's stored expiry (None when unreadable/absent).

    The active profile and the `_`-prefixed reserved profiles are excluded, so the
    result names exactly the profiles `keep_warm` maintains. It is the input to
    `next_warm_wake`.
    """

    vault = caam_vault(home=home)
    if not vault.is_dir():
        return ()
    expiries: list[float | None] = []
    for profile_path in sorted(vault.iterdir(), key=lambda path: path.name):
        name = profile_path.name
        if not _is_idle_profile(name=name, active_name=active_name):
            continue
        _, expires_at = read_creds(path=profile_path / ".credentials.json")
        expiries.append(expires_at)
    return tuple(expiries)


def next_warm_wake(
    *,
    expiries: Iterable[float | None],
    now: float,
    delay_s: float | None = None,
) -> float | None:
    """When to next run maintenance so the soonest-expiring idle account is refreshed
    within `delay_s` of its own expiry, rather than up to a full fixed tick later.

    It is the earliest FUTURE expiry plus `delay_s` (a few seconds, so the token is
    certainly expired by the time the wake fires). An already-expired or unknown
    expiry drives no wake here -- an expired account is refreshed by the current
    pass, and an unknown one is covered by the recurring backstop schedule. Returns
    None when no idle account has a future expiry to wake for.
    """

    delay = warm_wake_delay_s() if delay_s is None else delay_s
    future = [expiry for expiry in expiries if expiry is not None and expiry > now]
    if not future:
        return None
    return min(future) + delay


def emit_next_warm_wake(
    *, home: Path, active_name: str, now: float, stdout: Callable[[str], None]
) -> None:
    """Emit the instant to next run maintenance, keyed to the soonest idle-account
    expiry, so the operator surface can schedule a per-account wake there rather
    than waiting for the coarse recurring tick. Silent when no idle account has a
    future expiry to wake for.
    """
    wake = next_warm_wake(
        expiries=idle_snapshot_expiries(home=home, active_name=active_name), now=now
    )
    if wake is not None:
        stamp = datetime.fromtimestamp(wake, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        stdout(f"next-warm-wake: {stamp}")


def warm_profile(
    *,
    name: str,
    home: Path,
    agent_runner: AgentRunner,
    logger: Logger,
    now: float | None = None,
) -> WarmResult:
    """Refresh one idle profile's snapshot in an isolated CLAUDE_CONFIG_DIR."""

    checked_at = time.time() if now is None else now
    vault_profile = caam_vault(home=home) / name
    sandbox = _warm_sandbox(home=home, name=name)
    live_path = live_creds_path(home=home)
    live_before = token_of(path=live_path)
    try:
        _prepare_sandbox(source=vault_profile, sandbox=sandbox)
        process = _run_agent(
            sandbox=sandbox,
            agent_runner=agent_runner,
        )
        said = _first_output_line(process=process)
        _, before = read_creds(path=vault_profile / ".credentials.json")
        _, after = read_creds(path=sandbox / ".credentials.json")
        if after is not None and after > checked_at and (before is None or after <= before):
            return WarmResult(ok=True, detail="already valid, no refresh needed")
        if after is None or (before is not None and after <= before):
            return WarmResult(ok=False, detail=f"no refresh -- {said or 'no output'}")
        shutil.copy(sandbox / ".credentials.json", vault_profile / ".credentials.json")
        (vault_profile / ".credentials.json").chmod(0o600)
        return WarmResult(ok=True, detail="refreshed, +%.1fh" % ((after - checked_at) / 3600))
    except (OSError, ValueError) as exc:
        return WarmResult(ok=False, detail=f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
        if token_of(path=live_path) != live_before:
            logger(_LIVE_CHANGED)


def _warm_memo(*, state: dict[str, object]) -> dict[str, object]:
    memo_value = state.get("warm")
    if isinstance(memo_value, dict):
        return cast(dict[str, object], memo_value)
    memo: dict[str, object] = {}
    state["warm"] = memo
    return memo


def _last_attempt_at(*, memo: dict[str, object], name: str) -> float:
    entry_value = memo.get(name)
    if not isinstance(entry_value, dict):
        return 0.0
    entry: dict[object, object] = entry_value
    value = entry.get("at")
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _warm_sandbox(*, home: Path, name: str) -> Path:
    return home / STATE_REL.parent / "warm" / name


def _prepare_sandbox(*, source: Path, sandbox: Path) -> None:
    if sandbox.is_dir():
        shutil.rmtree(sandbox)
    sandbox.mkdir(mode=0o700, parents=True, exist_ok=True)
    for filename in (".credentials.json", ".claude.json", "settings.json"):
        src = source / filename
        if src.exists():
            shutil.copy(src, sandbox / filename)
    (sandbox / ".credentials.json").chmod(0o600)


def _run_agent(*, sandbox: Path, agent_runner: AgentRunner) -> AgentProcess:
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(sandbox))
    return agent_runner(args=("claude", "-p", "ok"), env=env, timeout=_AGENT_TIMEOUT_S)


def _first_output_line(*, process: AgentProcess) -> str:
    lines = ((process.stdout or "") + (process.stderr or "")).strip().splitlines()
    return lines[0][:120] if lines else ""
