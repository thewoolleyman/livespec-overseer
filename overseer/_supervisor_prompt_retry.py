"""Enter-only completion of a daemon-retained prompt payload."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, cast

import herdr_identity
import pane_router_submit_signals
from _supervisor_config import SUBMIT_POLL

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["NativeEnterRetry", "retained_prompt_visible", "retry_prompt_enter_once"]


class NativeEnterRetry(Protocol):
    def __call__(
        self,
        *,
        session: str,
        text: str,
        sleep: Callable[[float], None],
    ) -> tuple[bool, bool]: ...


def retained_prompt_visible(*, sup: Supervisor, target: str, text: str) -> bool:
    """Whether the daemon's exact retained prompt is still in this composer."""
    return pane_router_submit_signals.prompt_pending(
        capture=sup.tmux.capture_pane(session=target), text=text
    )


def retry_prompt_enter_once(*, sup: Supervisor, target: str, text: str) -> tuple[bool, bool]:
    """Attempt ONE Enter for retained prompt text, without ever pasting it again."""
    native = cast(NativeEnterRetry | None, getattr(sup.tmux, "retry_prompt_enter_once", None))
    if target.startswith(herdr_identity.HERDR_SCHEME) and native is not None:
        return native(session=target, text=text, sleep=sup.sleep)
    if not retained_prompt_visible(sup=sup, target=target, text=text):
        return False, False
    if not sup.tmux.send_keys(session=target, keys="Enter"):
        return False, False
    sup.sleep(SUBMIT_POLL)
    capture = sup.tmux.capture_pane(session=target)
    submitted = pane_router_submit_signals.delivered(capture=capture)
    return submitted, not submitted
