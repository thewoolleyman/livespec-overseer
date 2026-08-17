"""Command construction for the deterministic foreman actuator."""

from __future__ import annotations

import re
import sys
from contextlib import suppress
from pathlib import Path
from typing import Final

import jsonio
import signals
from _supervisor_prompts import (
    foreman_resume,
    plan_epic_resume,
    supervisor_epic_path,
    supervisor_resume,
)
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
_LEDGER_ANCHOR: Final[re.Pattern[str]] = re.compile(
    r"(?:[Ll]edger(?: epic)?|[Ee]pic) anchor:?\*{0,2}[^\n`]*\n?[^\n`]*"
    r"`([a-z0-9-]+(?:\.[0-9]+)?)`"
)


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


def _supervisor_pair_epic(*, repo: str, topic: str) -> str | None:
    path = supervisor_epic_path(repo=repo, topic=topic)
    epic: str | None = None
    with suppress(OSError, ValueError):
        epic = next(iter(_LEDGER_ANCHOR.findall(path.read_text(encoding="utf-8"))), None)
    return epic


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


def _supervisor_pair_start_command(*, payload: dict[str, object]) -> list[str] | None:
    repo = _str_field(payload=payload, key="repo")
    topic = _str_field(payload=payload, key="topic")
    session_name = _str_field(payload=payload, key="session_name")
    if (
        repo is None or topic is None or session_name is None or not Path(repo).is_absolute()
    ):  # pragma: no cover
        return None
    prompt = supervisor_resume(
        repo=repo,
        topic=topic,
        epic=_supervisor_pair_epic(repo=repo, topic=topic),
    )
    return [
        "tmux",
        "new-session",
        "-d",
        "-s",
        session_name,
        "-c",
        repo,
        "claude",
        "--dangerously-skip-permissions",
        "-n",
        session_name,
        prompt,
    ]


def _resume_prompt(*, repo: str, topic: str, brief: str | None, epic: str | None) -> str:
    """The one prompt handed to a resumed codex session.

    Three shapes, in precedence order. A ``brief`` is the bounded one-shot work-item
    session's own file under the repository's gitignored ``tmp/overseer/foreman/``
    scratch area — never a plan-tree path — and it wins because that session exists only
    to complete that brief. Otherwise a recorded plan ``epic`` gives the same
    ledger-held read-first locator the daemon's own restart uses, so the two surfaces can
    never point a session at different sources.

    The last shape names no source at all, and that is deliberate rather than a
    degradation: ``codex resume <id>`` restores the FULL prior conversation, so a session
    resumed this way already holds its own context and needs a continuation kick, not a
    pointer. Naming a plausible-looking file here — which is what this branch used to do —
    was the failure mode, since the file may never have existed.
    """
    if signals.is_foreman_topic(topic=topic):
        return foreman_resume(repo=repo, epic=epic)
    if brief is not None:
        return f"read {brief} and complete this bounded one-shot work-item session"
    if epic is not None:
        return plan_epic_resume(repo=repo, epic=epic)
    return f"continue the plan {topic} work in repository {repo} from your restored session"


def resume_command_from_payload(*, payload: dict[str, object]) -> list[str] | None:
    runtime = _str_field(payload=payload, key="runtime")
    repo = _str_field(payload=payload, key="repo")
    topic = _str_field(payload=payload, key="topic")
    session_id = _str_field(payload=payload, key="session_id")
    brief = _str_field(payload=payload, key="handoff_path")
    epic = _str_field(payload=payload, key="epic")
    if (
        runtime != "codex" or repo is None or topic is None or session_id is None
    ):  # pragma: no cover
        return None
    prompt = _resume_prompt(repo=repo, topic=topic, brief=brief, epic=epic)
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
        if action_id == SUPERVISOR_PAIR_START:
            return _supervisor_pair_start_command(payload=start)
        return _start_command(payload=start)
    resume = _typed_resume(proposal=proposal)
    if action_id != QUALIFYING_SESSION_RESUME:  # pragma: no cover
        return None
    if resume is None or not _matches_coordinates(  # pragma: no cover
        payload=resume, proposal=proposal
    ):
        return None
    return resume_command_from_payload(payload=resume)
