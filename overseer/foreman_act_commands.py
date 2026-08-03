"""Command construction for the deterministic foreman actuator."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

import jsonio
from _supervisor_prompts import default_resume
from foreman_act_types import (
    PLAN_START,
    QUALIFYING_SESSION_RESUME,
    QUALIFYING_SESSION_START,
    SUPERVISOR_PAIR_START,
    ActionId,
)

__all__: list[str] = ["command_for", "resume_command_from_payload"]

_START_ACTIONS: Final[tuple[ActionId, ...]] = (
    PLAN_START,
    QUALIFYING_SESSION_START,
    SUPERVISOR_PAIR_START,
)
_HERE: Final[Path] = Path(__file__).resolve().parent


def _str_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _classifier_payload(*, proposal: dict[str, object]) -> dict[str, object] | None:
    return jsonio.as_object(value=proposal.get("classifier"))


def _typed_start(*, proposal: dict[str, object]) -> dict[str, object] | None:
    classifier = _classifier_payload(proposal=proposal)
    if classifier is None or classifier.get("action") != "start":  # pragma: no cover
        return None
    return jsonio.as_object(value=classifier.get("start"))


def _typed_resume(*, proposal: dict[str, object]) -> dict[str, object] | None:
    classifier = _classifier_payload(proposal=proposal)
    if classifier is None or classifier.get("action") != "exact_resume":  # pragma: no cover
        return None
    return jsonio.as_object(value=classifier.get("resume"))


def _matches_coordinates(*, payload: dict[str, object], proposal: dict[str, object]) -> bool:
    return (
        payload.get("repo") == proposal.get("repo")
        and payload.get("topic") == proposal.get("topic")
        and payload.get("session_name") == proposal.get("session_name")
    )


def _start_command(*, payload: dict[str, object]) -> list[str] | None:
    repo = _str_field(payload=payload, key="repo")
    topic = _str_field(payload=payload, key="topic")
    if repo is None or topic is None or not Path(repo).is_absolute():  # pragma: no cover
        return None
    return [
        sys.executable,
        str(_HERE / "supervisor.py"),
        "start",
        "--repo",
        repo,
        "--topic",
        topic,
    ]


def resume_command_from_payload(*, payload: dict[str, object]) -> list[str] | None:
    runtime = _str_field(payload=payload, key="runtime")
    repo = _str_field(payload=payload, key="repo")
    topic = _str_field(payload=payload, key="topic")
    session_id = _str_field(payload=payload, key="session_id")
    handoff = _str_field(payload=payload, key="handoff_path")
    if (
        runtime != "codex" or repo is None or topic is None or session_id is None
    ):  # pragma: no cover
        return None
    prompt = (
        f"read {handoff} and complete this bounded one-shot work-item session"
        if handoff is not None
        else default_resume(repo=repo, topic=topic)
    )
    return [
        "codex",
        "resume",
        "--dangerously-bypass-approvals-and-sandbox",
        session_id,
        prompt,
    ]


def command_for(*, action_id: ActionId, proposal: dict[str, object]) -> list[str] | None:
    if action_id in _START_ACTIONS:
        start = _typed_start(proposal=proposal)
        if start is None or not _matches_coordinates(  # pragma: no cover
            payload=start, proposal=proposal
        ):
            return None
        return _start_command(payload=start)
    resume = _typed_resume(proposal=proposal)
    if action_id != QUALIFYING_SESSION_RESUME:  # pragma: no cover
        return None
    if resume is None or not _matches_coordinates(  # pragma: no cover
        payload=resume, proposal=proposal
    ):
        return None
    return resume_command_from_payload(payload=resume)
