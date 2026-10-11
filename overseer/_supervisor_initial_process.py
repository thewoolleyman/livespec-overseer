"""Backend-aware initial agent launch and process-observation finalization."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol, cast

import herdr_identity
import registry
from _supervisor_cli_start_types import NativeMutation
from _supervisor_launch_profile import ClaudeLaunchPlan, CodexLaunchPlan

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "InitialProcessAttempt",
    "finish_initial_process",
    "start_initial_process",
]


class NativeLauncher(Protocol):
    def launch_initial_agent(
        self,
        *,
        session: str,
        cwd: str,
        command: str,
        env: object,
        expected_process: str,
    ) -> NativeMutation: ...


class NativeFinisher(Protocol):
    def finish_initial_agent(self, *, repo: str, session: str, unresolved: bool) -> None: ...


def _observed_native_cwd(*, sup: Supervisor, target: str, expected: str) -> str:
    reader = cast(
        Callable[..., str | None] | None,
        getattr(sup.tmux, "pane_current_path", None),
    )
    if reader is None:
        return expected
    return reader(session=target) or ""


@dataclass(frozen=True, kw_only=True)
class InitialProcessAttempt:
    launched: bool
    reason: str
    effect_unknown: bool
    native: bool


def start_initial_process(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    launch: ClaudeLaunchPlan | CodexLaunchPlan,
    expected_process: str,
    failure_reason: str,
) -> InitialProcessAttempt:
    """Launch only through the target backend's initial-process operation."""
    native = herdr_identity.decode_herdr_target(value=target) is not None
    if native:
        mutation = cast(NativeLauncher, sup.tmux).launch_initial_agent(
            session=target,
            cwd=track.repo,
            command=launch.command,
            env=launch.env,
            expected_process=expected_process,
        )
        return InitialProcessAttempt(
            launched=mutation.ok,
            reason=mutation.error or failure_reason,
            effect_unknown=mutation.effect_unknown,
            native=True,
        )
    launched = sup.tmux.respawn_pane(
        session=target,
        cwd=track.repo,
        command=launch.command,
        env=launch.env,
    )
    return InitialProcessAttempt(
        launched=launched,
        reason=failure_reason,
        effect_unknown=False,
        native=False,
    )


def finish_initial_process(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    attempt: InitialProcessAttempt,
    confirmed: bool,
) -> InitialProcessAttempt:
    """Settle an intent only after the expected process is freshly observed."""
    fully_confirmed = confirmed and (
        (not attempt.native)
        or registry.norm(repo=_observed_native_cwd(sup=sup, target=target, expected=track.repo))
        == registry.norm(repo=track.repo)
    )
    unresolved = attempt.effect_unknown or (
        attempt.native and attempt.launched and not fully_confirmed
    )
    if attempt.native and hasattr(sup.tmux, "finish_initial_agent"):
        cast(NativeFinisher, sup.tmux).finish_initial_agent(
            repo=track.repo,
            session=target,
            unresolved=unresolved,
        )
    unconfirmed = replace(
        attempt,
        launched=False,
        effect_unknown=unresolved,
    )
    return {True: attempt, False: unconfirmed}[fully_confirmed]
