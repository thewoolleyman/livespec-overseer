"""Resolve one known-created tmux daemon pane without replay or broad layout edits."""

from __future__ import annotations

from dataclasses import dataclass

import bootstrap
import bootstrap_readiness
import tmuxio_protocols

__all__: list[str] = ["LaunchPolicy", "finish_created_pane"]


@dataclass(frozen=True, kw_only=True)
class LaunchPolicy:
    """Presentation and readiness bounds for one known-created daemon pane."""

    title: str
    timeout_seconds: float
    poll_seconds: float


def finish_created_pane(
    *,
    driver: tmuxio_protocols.BootstrapDriver,
    created: str,
    observe: bootstrap_readiness.DaemonHostObserver,
    policy: LaunchPolicy,
) -> bootstrap.PlacementOutcome:
    """Prove the exact daemon in the allocation-scoped pane `created`."""
    _ = driver.set_pane_title(pane=created, title=policy.title)
    first = observe()

    def pane_is_gone(*, reading: bootstrap.DaemonHostReading) -> bool:
        if not reading.error:
            return False
        return not driver.pane_exists(pane=created)

    reading = bootstrap_readiness.await_exact_daemon(
        observe=observe,
        timeout_seconds=policy.timeout_seconds,
        poll_seconds=policy.poll_seconds,
        initial=first,
        stop=pane_is_gone,
    )
    if not reading.pane_id:
        detail = f"{reading.error} {reading.unresolved}".strip()
        return bootstrap.PlacementOutcome(
            ok=False,
            pane_id=created,
            error=(
                f"the daemon did not stay alive or establish exact daemon process "
                f"readiness in tmux pane {created!r}: {detail}"
            ),
            effect_unknown=True,
        )
    return bootstrap.PlacementOutcome(ok=True, pane_id=created, error="", effect_unknown=False)
