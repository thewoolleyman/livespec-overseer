"""Keep idle caam profiles warm enough to remain switchable."""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from caam_profile_state import STATE_REL, caam_vault, live_creds_path
from caam_usage import read_creds

__all__: list[str] = [
    "AgentProcess",
    "AgentRunner",
    "Logger",
    "WarmConfig",
    "WarmResult",
    "keep_warm",
    "read_creds",
    "token_of",
    "warm_margin_s",
    "warm_profile",
    "warm_retry_s",
]

_WARM_MARGIN_DEFAULT_S = "7200"
_WARM_RETRY_DEFAULT_S = "3600"
_AGENT_TIMEOUT_S = 180.0
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


def warm_margin_s() -> float:
    return float(os.environ.get("CAAM_ROTATE_WARM_MARGIN_S", _WARM_MARGIN_DEFAULT_S))


def warm_retry_s() -> float:
    return float(os.environ.get("CAAM_ROTATE_WARM_RETRY_S", _WARM_RETRY_DEFAULT_S))


def token_of(*, path: Path) -> str | None:
    token, _ = read_creds(path=path)
    return token


def keep_warm(
    *,
    state: dict[str, object],
    config: WarmConfig,
    agent_runner: AgentRunner,
    logger: Logger,
    now: float | None = None,
) -> None:
    """Refresh idle snapshots that are about to lapse, so they stay switchable."""

    vault = caam_vault(home=config.home)
    if config.no_warm or config.dry_run or not vault.is_dir():
        return

    checked_at = time.time() if now is None else now
    memo = _warm_memo(state=state)
    for profile_path in sorted(vault.iterdir(), key=lambda path: path.name):
        name = profile_path.name
        if name.startswith("_") or name == config.active_name:
            continue
        _, expires_at = read_creds(path=profile_path / ".credentials.json")
        if expires_at is not None and expires_at - checked_at > warm_margin_s():
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
        if (
            after is not None
            and after > checked_at + warm_margin_s()
            and (before is None or after <= before)
        ):
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
