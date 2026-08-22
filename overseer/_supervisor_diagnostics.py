"""_supervisor_diagnostics — daemon event-history and operator alert lines."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import registry
import streams
from _supervisor_config import iso_now, track_key

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["AlertRequest", "alert", "log", "log_claude_build", "surface"]

_REPO_TOPIC_RE = re.compile(r"(?P<repo>\S+)::(?P<topic>[A-Za-z0-9_.-]+)")
_CTX_RE = re.compile(r"\bctx (?P<ctx>\d+)%")
_BANDS_RE = re.compile(r"\bbands \[(?P<bands>[0-9, ]*)\]")
_AGE_RE = re.compile(r"\b(?:age |after |stale )(?P<age>\d+)m\b")
_PID_RE = re.compile(r"\bpid (?P<pid>\d+)\b")
_TICK_RE = re.compile(r"\btick (?P<tick>\d+)\b")
_INTERVAL_RE = re.compile(r"\binterval (?P<interval>\d+(?:\.\d+)?)s\b")


def _slugify_event(*, text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text.lower())
    return "-".join(words[:4]) if words else "daemon-log"


def _int_field(*, match: re.Match[str] | None, name: str) -> int | None:
    if match is None:
        return None
    return int(match.group(name))


def _number_field(*, match: re.Match[str] | None, name: str) -> int | float | None:
    if match is None:
        return None
    raw = match.group(name)
    return float(raw) if "." in raw else int(raw)


def _fields_from_message(*, message: str) -> dict[str, object]:
    fields: dict[str, object] = {}
    ctx = _int_field(match=_CTX_RE.search(message), name="ctx")
    if ctx is not None:
        fields["ctx"] = ctx
    bands = _BANDS_RE.search(message)
    if bands is not None:
        raw_bands = [part.strip() for part in bands.group("bands").split(",")]
        fields["bands"] = [int(part) for part in raw_bands if part]
    age = _int_field(match=_AGE_RE.search(message), name="age")
    if age is not None:
        fields["age_minutes"] = age
    pid = _int_field(match=_PID_RE.search(message), name="pid")
    if pid is not None:
        fields["pid"] = pid
    tick = _int_field(match=_TICK_RE.search(message), name="tick")
    if tick is not None:
        fields["tick"] = tick
    interval = _number_field(match=_INTERVAL_RE.search(message), name="interval")
    if interval is not None:
        fields["interval"] = interval
    if ": " in message and ("FAILED" in message or "could not" in message):
        fields["error"] = message.rsplit(": ", maxsplit=1)[-1]
    return fields


def _repo_topic_from_message(*, message: str) -> tuple[str | None, str | None]:
    match = _REPO_TOPIC_RE.search(message)
    if match is None:
        return None, None
    return match.group("repo").rstrip(".,);"), match.group("topic").rstrip(".,);")


def _event_from_message(*, message: str) -> str:
    repo_topic = _REPO_TOPIC_RE.search(message)
    basis = message if repo_topic is None else message[: repo_topic.start()]
    basis = basis.replace("FAILED", "failed").replace("archive-GC", "archive gc")
    return _slugify_event(text=basis)


@dataclass(frozen=True, kw_only=True)
class AlertRequest:
    sup: Supervisor
    repo: str
    topic: str
    session: str | None
    pane: str | None
    message: str
    condition: str


@dataclass(frozen=True, kw_only=True)
class EventRequest:
    sup: Supervisor | None
    event: str
    severity: str
    message: str
    repo: str | None = None
    topic: str | None = None
    fields: Mapping[str, object] = field(default_factory=dict)


def _public_fields(*, fields: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in fields.items() if value is not None}


def _event_record(*, request: EventRequest) -> dict[str, object]:
    record: dict[str, object] = {
        "ts": iso_now(),
        "event": request.event,
        "severity": request.severity,
        "daemon_instance_id": request.sup.daemon_instance_id
        if request.sup is not None
        else "unknown",
        "tick_generation": request.sup.tick_generation if request.sup is not None else 0,
        "message": request.message,
    }
    if request.repo is not None:
        record["repo"] = registry.repo_slug(repo=request.repo)
    if request.topic is not None:
        record["topic"] = request.topic
    record.update(_public_fields(fields=request.fields))
    return record


def _write_event(*, request: EventRequest) -> None:
    record = _event_record(request=request)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    streams.write_stderr(text=f"{line}\n")


def log(
    *,
    message: str,
    sup: Supervisor | None = None,
    event: str = "daemon-log",
    repo: str | None = None,
    topic: str | None = None,
    fields: Mapping[str, object] | None = None,
) -> None:
    inferred_repo, inferred_topic = _repo_topic_from_message(message=message)
    merged_fields = {**_fields_from_message(message=message)}
    if fields is not None:
        merged_fields.update(fields)
    _write_event(
        request=EventRequest(
            sup=sup,
            event=_event_from_message(message=message) if event == "daemon-log" else event,
            severity="info",
            message=message,
            repo=repo or inferred_repo,
            topic=topic or inferred_topic,
            fields=merged_fields,
        )
    )


def log_claude_build(*, sup: Supervisor, phase: str) -> None:
    version = sup.claude_version_of() or "unavailable"
    log(
        sup=sup,
        event="claude-build",
        message=f"claude build at {phase}: {version}",
        fields={"phase": phase, "version": version},
    )


def surface(
    *,
    message: str,
    sup: Supervisor | None = None,
    event: str = "daemon-alert",
    repo: str | None = None,
    topic: str | None = None,
    fields: Mapping[str, object] | None = None,
) -> None:
    """Surface a DAEMON-level alert to the operator."""
    inferred_repo, inferred_topic = _repo_topic_from_message(message=message)
    merged_fields = {**_fields_from_message(message=message)}
    if fields is not None:
        merged_fields.update(fields)
    _write_event(
        request=EventRequest(
            sup=sup,
            event=event,
            severity="alert",
            message=message,
            repo=repo or inferred_repo,
            topic=topic or inferred_topic,
            fields=merged_fields,
        )
    )


def _alert_identity(*, request: AlertRequest, message: str) -> str:
    fields = _fields_from_message(message=request.message)
    if request.condition == "foreman-heartbeat-stale":
        return json.dumps(
            {"pid": fields.get("pid"), "interval": fields.get("interval")},
            sort_keys=True,
            separators=(",", ":"),
        )
    return message


def alert(*, request: AlertRequest) -> None:
    """Surface a TRACK-scoped alert that always names WHERE to act.

    Every track alert carries the plan topic, its repo, the tmux SESSION and PANE
    holding it, and a copy-pasteable jump command. ``repo::topic`` alone tells the
    operator WHAT is stuck but never WHERE to go — they were left to hunt for the
    session by hand (maintainer 2026-07-14).

    This is load-bearing for the notify-never-block contract (invariant 8): because
    the overseer NEVER prompts on a track's behalf, this line is the operator's ONLY
    handover, so it MUST be self-sufficient. Every new track-scoped alert goes
    through here — never a bare ``surface`` with an f-string of ``repo::topic``.

    EDGE-TRIGGERED: emitted when a track ENTERS a condition (or the condition's text
    changes), NOT once per tick. The log is the daemon's EVENT HISTORY — the surface
    the bottom pane reads to answer "what happened, and when?" — while CURRENT state
    is owned by the re-rendered table + its ``NEEDS YOU`` block. Re-emitting an
    unchanged alert every tick buried that history in thousands of identical lines (a
    track blocked overnight logged ~3,000 of them) and answered a question the table
    already answers better. The re-arm is in :meth:`evaluate`: when a track returns to
    a healthy status its entry is dropped, so the NEXT time it goes bad it reports
    again.
    """
    where = (
        f"tmux session '{request.session}' pane {request.pane}"
        if request.session
        else "no live tmux session"
    )
    jump = f" — jump: tmux switch-client -t {request.session}" if request.session else ""
    line = (
        f"{request.topic} ({registry.repo_slug(repo=request.repo)}) — "
        f"{request.message} [{where}]{jump}"
    )
    key = (*track_key(repo=request.repo, topic=request.topic), request.condition)
    identity = _alert_identity(request=request, message=line)
    if request.sup.alerted.get(key) == identity:
        return
    request.sup.alerted[key] = identity
    surface(
        sup=request.sup,
        event=request.condition,
        message=line,
        repo=request.repo,
        topic=request.topic,
        fields={
            "session": request.session,
            "pane": request.pane,
            **_fields_from_message(message=request.message),
        },
    )
