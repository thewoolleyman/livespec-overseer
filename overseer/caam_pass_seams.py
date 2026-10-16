"""The production seams a caam rotation pass binds when a caller injects none.

Split out of ``caam_anthropic_pass`` (work-item overseer-m7qrgp.3), which stood
exactly ON the 250-LLOC hard ceiling and could not carry another line. The cut is
by cohesion rather than by count: everything here is how the pass REACHES THE
HOST -- running `caam`, running an agent, writing a log line -- while the module
it left holds the pass's own shape and ordering.

Every name is PUBLIC because a seam another module binds cannot be a private
helper: pyright strict's ``reportPrivateUsage`` and the repo's ``private_calls``
gate both refuse a cross-module ``_``-prefixed import, and rightly so -- these
four ARE the interface between the pass and the host it runs on.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Final, Protocol, cast

from _caam_switch_host import caam_activate
from caam_anthropic_decide import SwitchAccount, UsageFetcher
from caam_anthropic_finish import LineWriter, SaveState
from caam_anthropic_status import EnforceModels
from caam_capacity import CapacitySource
from caam_capacity_source import read_rate_limit_tier
from caam_enforcement import enforce_models as default_enforce_models
from caam_pass_refusals import TrackedSessionSource, tracked_session_source
from caam_profile_state import save_state as default_save_state
from caam_profiles import CaamRunner
from caam_switch import switch_account as default_switch_account
from caam_usage import fetch_usage
from caam_warm import AgentProcess, Logger, ResnapshotRunner

__all__: list[str] = [
    "AgentRunner",
    "PassSeams",
    "default_agent_runner",
    "default_caam_runner",
    "line_logger",
    "pass_seams",
]

_CAAM_TIMEOUT_S: Final = 60.0


class AgentRunner(Protocol):
    def __call__(
        self,
        *,
        args: tuple[str, ...],
        env: dict[str, str],
        timeout: float,
    ) -> AgentProcess: ...


def default_caam_runner(*, args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return caam_activate(args=args, timeout=_CAAM_TIMEOUT_S)


def line_logger(*, writer: LineWriter) -> Logger:
    return _LineLogger(writer=writer)


@dataclass(frozen=True, kw_only=True)
class _LineLogger:
    writer: LineWriter

    def __call__(self, message: str) -> None:
        self.writer(message)


def default_agent_runner(
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


@dataclass(frozen=True, kw_only=True)
class PassSeams:
    fetcher: UsageFetcher
    capacity_source: CapacitySource
    save_state: SaveState
    switch_account: SwitchAccount
    enforce_models: EnforceModels
    agent_runner: AgentRunner
    caam_runner: ResnapshotRunner
    tracked_sessions: TrackedSessionSource


def pass_seams(*, overrides: dict[str, object]) -> PassSeams:
    """Every seam the pass will use: the caller's where given, production's where not.

    Resolved in ONE place so the pass itself reads as the sequence it performs
    rather than as a list of defaults, and so a seam added later costs one line
    here instead of three there.
    """
    caam_runner = cast(CaamRunner | None, overrides.get("caam_runner"))
    agent_runner = cast(AgentRunner | None, overrides.get("agent_runner"))
    return PassSeams(
        fetcher=cast(UsageFetcher, overrides.get("fetcher", fetch_usage)),
        capacity_source=cast(
            CapacitySource, overrides.get("capacity_source", read_rate_limit_tier)
        ),
        save_state=cast(SaveState, overrides.get("save_state", default_save_state)),
        switch_account=cast(SwitchAccount, overrides.get("switch_account", default_switch_account)),
        enforce_models=cast(EnforceModels, overrides.get("enforce_models", default_enforce_models)),
        agent_runner=default_agent_runner if agent_runner is None else agent_runner,
        caam_runner=default_caam_runner if caam_runner is None else caam_runner,
        tracked_sessions=tracked_session_source(overrides=overrides),
    )
