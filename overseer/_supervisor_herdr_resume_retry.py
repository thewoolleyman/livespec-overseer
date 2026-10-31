"""Durable retry and transcript-proof completion for a Herdr Claude successor."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import _claude_runtime_model
import _herdr_replacement_process
import _herdr_replacement_store
import claude_sessions
import registry
import signals
from _supervisor_config import SUBMIT_MAX_ENTERS, SUBMIT_POLL

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["retry_recorded_resume"]


class PendingEnterRetry(Protocol):
    def __call__(
        self,
        *,
        session: str,
        text: str,
        sleep: Callable[[float], None],
    ) -> tuple[bool, bool]: ...


def retry_recorded_resume(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    current: dict[str, object],
    successor: _herdr_replacement_process.ProcessObservation,
    record_path: Path,
) -> str | None:
    """Finish a persisted resume, retrying only a visible exact composer payload."""
    recorded_successor = current.get("successor")
    resume = current.get("resume")
    attempts = current.get("resume_retry_attempts", 0)
    capture = sup.tmux.capture_pane(session=target)
    expected = resume.partition("\n")[0].strip() if isinstance(resume, str) else ""
    exact_pending = signals.input_box_text(capture_text=capture) == expected
    if not _herdr_replacement_process.process_identity_matches(
        record=recorded_successor, process=successor
    ):
        return "pending resume successor no longer matches the durable process identity"
    written_at = current.get("resume_written_at")
    if not isinstance(written_at, int | float) or isinstance(written_at, bool):
        written_at = record_path.stat().st_mtime
    delivered = _claude_runtime_model.resume_delivery_evidenced(
        pid=successor.pid,
        resume=cast(str, resume),
        since=float(written_at),
        sessions_dir=sup.sessions_dir or claude_sessions.default_sessions_dir(),
        projects_dir=_claude_runtime_model.default_projects_dir(),
    )
    if delivered:
        _complete_stalled(
            sup=sup,
            track=track,
            target=target,
            current=current,
            record_path=record_path,
            reason="pending resume text was already consumed",
        )
        return None
    if signals.is_structured_gate(capture_text=capture) or not expected or not exact_pending:
        return "pending resume text is absent, gated, or differs from the durable payload"
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts >= SUBMIT_MAX_ENTERS:
        return "pending resume Enter retry budget is exhausted or malformed"
    current["resume_retry_attempts"] = attempts + 1
    _herdr_replacement_store.durable_write(path=record_path, value=current)
    submitted, effect_unknown = _retry_enter(sup=sup, target=target, resume=cast(str, resume))
    if submitted:
        _complete_stalled(
            sup=sup,
            track=track,
            target=target,
            current=current,
            record_path=record_path,
            reason="pending resume text was still in the composer and Enter submitted it",
        )
        return None
    return (
        "pending resume Enter outcome is unknown"
        if effect_unknown
        else "pending resume Enter was not confirmed"
    )


def _complete_stalled(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    current: dict[str, object],
    record_path: Path,
    reason: str,
) -> None:
    current["phase"] = "completed"
    _herdr_replacement_store.durable_write(path=record_path, value=current)
    sup.log(
        message=(
            f"completed stalled Herdr replacement for {track.repo}::{track.topic} at pane "
            f"{target}; reason {reason}; live session "
            f"{sup.claude_identity_by_session[(target, track.topic)]}"
        )
    )


def _retry_enter(*, sup: Supervisor, target: str, resume: str) -> tuple[bool, bool]:
    native = cast(
        PendingEnterRetry | None,
        getattr(sup.tmux, "retry_prompt_enter_once", None),
    )
    if native is not None:
        return native(session=target, text=resume, sleep=sup.sleep)
    sent = sup.tmux.send_keys(session=target, keys="Enter")
    sup.sleep(SUBMIT_POLL)
    submitted = sent and signals.input_box_ready(capture_text=sup.tmux.capture_pane(session=target))
    return submitted, sent and not submitted
