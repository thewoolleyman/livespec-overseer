"""Claude process-group identity reads for supervisor observation."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import signals
from tmuxio_protocols import PaneDriver

if TYPE_CHECKING:
    from supervisor import Supervisor

__all__: list[str] = ["claude_cwds", "is_managed_claude"]


def claude_cwds(
    *, driver: PaneDriver, target: str, leader_is_claude: bool
) -> tuple[str | None, ...]:
    """Return the leader or exact foreground group's Claude working directories."""
    if leader_is_claude:
        return (driver.pane_current_path(session=target),)
    group_cwds = cast(
        Callable[..., tuple[str, ...]] | None,
        getattr(driver, "pane_claude_cwds", None),
    )
    return group_cwds(session=target) if group_cwds is not None else ()


def is_managed_claude(
    *, sup: Supervisor, target: str, repo: str, topic: str, session: str | None
) -> bool:
    """Whether a pane's leader or group member proves this Claude topic is live."""
    leader_is_claude = signals.pane_is_claude(
        pane_current_command=sup.tmux.pane_current_command(session=target)
    )
    paths = claude_cwds(
        driver=sup.tmux,
        target=target,
        leader_is_claude=leader_is_claude,
    )
    if not any(signals.path_in_repo(pane_current_path=cwd, repo=repo) for cwd in paths):
        return False
    names = sup.claude_names_by_session.get(session or "")
    if not names or topic in names:
        return True
    return signals.topic_reserved_for_supervisor(topic=topic) and session == topic
