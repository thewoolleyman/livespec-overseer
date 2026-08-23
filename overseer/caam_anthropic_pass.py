"""Top-level caam account-rotation pass orchestration."""
# livespec-lloc-soft-band-owner: overseer-hgq4wi

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, cast

from _caam_switch_host import caam_activate
from caam_anthropic_decide import DecisionSeams, SwitchAccount, UsageFetcher, decide
from caam_anthropic_finish import LineWriter, SaveState, finish
from caam_anthropic_flags import Flags
from caam_anthropic_revive import revive_pass_profiles
from caam_anthropic_status import EnforceModels, write_status
from caam_decision import ProfileUsage
from caam_enforcement import enforce_models as default_enforce_models
from caam_profile_state import (
    caam_vault,
    load_state,
    poll_profiles,
    profile_names,
)
from caam_profile_state import (
    save_state as default_save_state,
)
from caam_profile_state import (
    state_path as caam_state_path,
)
from caam_profiles import CaamRunner, active_profile
from caam_protected_accounts import apply_protected_accounts
from caam_rendering import RenderableProfileUsage, render_table
from caam_switch import switch_account as default_switch_account
from caam_usage import fetch_usage
from caam_warm import (
    AgentProcess,
    Logger,
    ResnapshotRunner,
    WarmConfig,
    keep_warm,
    resnapshot_active,
)

__all__: list[str] = ["AgentRunner", "Flags", "PassContext", "run_pass"]

_EMPTY_VAULT = "FAIL no profiles found in the caam vault for claude"
_ACTIVE_FAIL = "FAIL could not determine active claude profile"


class AgentRunner(Protocol):
    def __call__(
        self,
        *,
        args: tuple[str, ...],
        env: dict[str, str],
        timeout: float,
    ) -> AgentProcess: ...


@dataclass(frozen=True, kw_only=True)
class PassContext:
    flags: Flags
    home: Path
    now: float
    state: dict[str, object]
    state_path: Path
    stdout: LineWriter


def run_pass(
    *,
    flags: Flags,
    home: Path | None = None,
    now: float | None = None,
    stdout: LineWriter,
    **overrides: object,
) -> int:
    caam_runner = cast(CaamRunner | None, overrides.get("caam_runner"))
    fetcher = cast(UsageFetcher, overrides.get("fetcher", fetch_usage))
    save_state = cast(SaveState, overrides.get("save_state", default_save_state))
    switch_account = cast(SwitchAccount, overrides.get("switch_account", default_switch_account))
    enforce_models = cast(EnforceModels, overrides.get("enforce_models", default_enforce_models))
    agent_runner = cast(AgentRunner | None, overrides.get("agent_runner"))
    run_caam = _run_caam if caam_runner is None else caam_runner
    run_agent = _run_agent if agent_runner is None else agent_runner
    run_home = Path.home() if home is None else home
    checked_at = time.time() if now is None else now
    state_path = caam_state_path(home=run_home)
    state = load_state(state_path=state_path)
    vault = caam_vault(home=run_home)
    if not profile_names(vault=vault, active_name=None):
        return finish(
            code=2,
            state=state,
            state_path=state_path,
            save=save_state,
            stdout=stdout,
            lines=(_EMPTY_VAULT,),
        )
    active_name = active_profile(
        live_account_path=run_home / ".claude.json",
        vault_path=vault,
        caam_runner=run_caam,
    )
    if active_name is None:
        return finish(
            code=2,
            state=state,
            state_path=state_path,
            save=save_state,
            stdout=stdout,
            lines=(_ACTIVE_FAIL,),
        )
    return _pass_with_active(
        context=PassContext(
            flags=flags,
            home=run_home,
            now=checked_at,
            state=state,
            state_path=state_path,
            stdout=stdout,
        ),
        active_name=active_name,
        seams=PassSeams(
            fetcher=fetcher,
            save_state=save_state,
            switch_account=switch_account,
            enforce_models=enforce_models,
            agent_runner=run_agent,
            caam_runner=run_caam,
        ),
    )


@dataclass(frozen=True, kw_only=True)
class PassSeams:
    fetcher: UsageFetcher
    save_state: SaveState
    switch_account: SwitchAccount
    enforce_models: EnforceModels
    agent_runner: AgentRunner
    caam_runner: ResnapshotRunner


def _pass_with_active(
    *,
    context: PassContext,
    active_name: str,
    seams: PassSeams,
) -> int:
    resnapshot_active(
        active_name=active_name,
        home=context.home,
        dry_run=context.flags.dry_run,
        caam_runner=seams.caam_runner,
        logger=_logger(writer=context.stdout),
    )
    profiles = poll_profiles(
        active_name=active_name,
        state=context.state,
        home=context.home,
        now=context.now,
        fetcher=seams.fetcher,
    )
    profiles = _probe_snapshotless_profiles(
        context=context, profiles=profiles, fetcher=seams.fetcher
    )
    profiles = revive_pass_profiles(
        active_name=active_name, context=context, profiles=profiles, seams=seams
    )
    protected_accounts = apply_protected_accounts(
        state=context.state,
        requested_accounts=context.flags.protected_accounts,
    )
    current = next((profile.usage for profile in profiles if profile.name == active_name), None)
    if current is None:
        return finish(
            code=2,
            state=context.state,
            state_path=context.state_path,
            save=seams.save_state,
            stdout=context.stdout,
            lines=(
                *_table_lines(context=context, profiles=profiles, active_name=active_name),
                f"FAIL cannot read usage for active profile {active_name}",
            ),
        )
    write_status(
        context=context,
        profiles=profiles,
        active_name=active_name,
        current=current,
        enforce_models=seams.enforce_models,
        extra_messages=protected_accounts.messages,
    )
    keep_warm(
        state=context.state,
        config=WarmConfig(
            active_name=active_name,
            home=context.home,
            dry_run=context.flags.dry_run,
            no_warm=context.flags.no_warm,
        ),
        agent_runner=seams.agent_runner,
        logger=_logger(writer=context.stdout),
        now=context.now,
    )
    return decide(
        context=context,
        profiles=profiles,
        active_name=active_name,
        current=current,
        protection_floors=protected_accounts.values,
        seams=DecisionSeams(
            fetcher=seams.fetcher,
            save_state=seams.save_state,
            switch_account=seams.switch_account,
        ),
    )


def _table_lines(
    *, context: PassContext, profiles: tuple[ProfileUsage, ...], active_name: str
) -> tuple[str, ...]:
    now_dt = datetime.fromtimestamp(context.now, tz=timezone.utc)
    rows = cast(tuple[RenderableProfileUsage, ...], profiles)
    return tuple(render_table(rows=rows, active_name=active_name, now=now_dt).splitlines())


def _probe_snapshotless_profiles(
    *, context: PassContext, profiles: tuple[ProfileUsage, ...], fetcher: UsageFetcher
) -> tuple[ProfileUsage, ...]:
    return tuple(
        _probe_snapshotless_profile(context=context, profile=profile, fetcher=fetcher)
        for profile in profiles
    )


def _probe_snapshotless_profile(
    *, context: PassContext, profile: ProfileUsage, fetcher: UsageFetcher
) -> ProfileUsage:
    if profile.usage is not None or profile.source != "dark: no snapshot":
        return profile
    usage, _ = fetcher(
        creds_path=caam_vault(home=context.home) / profile.name / ".credentials.json",
        now=context.now,
    )
    if usage is None:
        return profile
    return ProfileUsage(name=profile.name, source="live", usage=usage)


def _run_caam(*, args: tuple[str, ...]):
    return caam_activate(args=args, timeout=60.0)


def _logger(*, writer: LineWriter) -> Logger:
    return _LineLogger(writer=writer)


@dataclass(frozen=True, kw_only=True)
class _LineLogger:
    writer: LineWriter

    def __call__(self, message: str) -> None:
        self.writer(message)


def _run_agent(
    *, args: tuple[str, ...], env: dict[str, str], timeout: float
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        args,
        env=env,
        timeout=timeout,
        check=False,
        capture_output=True,
        text=True,
    )
