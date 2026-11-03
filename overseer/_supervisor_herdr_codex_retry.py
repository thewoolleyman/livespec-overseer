"""Exact-payload Enter-only retry for durable Codex replacement prompts."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import _herdr_replacement_store
import pane_router_submit_signals
import signals
from _supervisor_config import SUBMIT_MAX_ENTERS, SUBMIT_POLL

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["retry_pending"]


class PendingEnterRetry(Protocol):
    def __call__(
        self,
        *,
        session: str,
        text: str,
        sleep: Callable[[float], None],
    ) -> tuple[bool, bool]: ...


def _resume_turn_started(*, capture: str) -> bool:
    """Whether the successor visibly began a turn without inspecting a rollout.

    Session identity proves which Codex successor occupies the pane, not that it
    accepted this resume.  Only active pane evidence proves a turn began; this keeps
    an idle fresh successor eligible for a bounded re-paste after a lost first paste.
    """
    return signals.is_busy(capture_text=capture)


def retry_pending(
    *,
    sup: Supervisor,
    target: str,
    current: dict[str, object],
    record_path: Path,
    key: str,
) -> tuple[bool, str]:
    """Resume one exact durable payload without treating transcript text as input."""
    text = current.get(key)
    attempts_key = f"{key}_retry_attempts"
    attempts = current.get(attempts_key, 0)
    if not isinstance(text, str) or not text:
        return False, f"durable Codex {key} payload is absent or malformed"
    capture = sup.tmux.capture_pane(session=target)
    if key == "resume" and _resume_turn_started(capture=capture):
        current["resume_submitted"] = True
        _herdr_replacement_store.durable_write(path=record_path, value=current)
        return True, ""
    exact = pane_router_submit_signals.codex_composer_text(capture=capture) == text
    empty = pane_router_submit_signals.codex_composer_empty(capture=capture)
    if signals.is_structured_gate(capture_text=capture) or not (exact or empty):
        return False, f"pending Codex {key} is absent, gated, or differs from durable text"
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts >= SUBMIT_MAX_ENTERS:
        return False, f"pending Codex {key} Enter retry budget is exhausted or malformed"
    current[attempts_key] = attempts + 1
    _herdr_replacement_store.durable_write(path=record_path, value=current)
    if empty:
        _ = sup.tmux.bracketed_paste(session=target, text=text)
        capture = sup.tmux.capture_pane(session=target)
        if pane_router_submit_signals.codex_composer_text(capture=capture) != text:
            return False, f"pending Codex {key} re-paste was not confirmed"
    native = cast(PendingEnterRetry | None, getattr(sup.tmux, "retry_prompt_enter_once", None))
    if native is not None:
        submitted, unknown = native(session=target, text=text, sleep=sup.sleep)
    else:
        sent = sup.tmux.send_keys(session=target, keys="Enter")
        sup.sleep(SUBMIT_POLL)
        submitted = sent and pane_router_submit_signals.submitted(
            capture=sup.tmux.capture_pane(session=target)
        )
        unknown = sent and not submitted
    return (
        (True, "")
        if submitted
        else (
            False,
            (
                f"pending Codex {key} Enter outcome is unknown"
                if unknown
                else f"pending Codex {key} Enter was not confirmed"
            ),
        )
    )
