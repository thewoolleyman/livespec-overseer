"""Bounded one-shot work-item session lifecycle for foreman-act."""
# livespec-lloc-soft-band-owner: overseer-hgq4wi.4

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import jsonio
import registry
from foreman_act_commands import resume_command_from_payload
from foreman_act_types import (
    WORK_ITEM_SESSION_FINISH,
    WORK_ITEM_SESSION_RESUME,
    WORK_ITEM_SESSION_START,
    ActionId,
    ActResult,
)

__all__: list[str] = ["WorkItemRunner", "act_work_item_session", "is_work_item_session_action"]

_TERMINAL_STATUSES = ("completed", "evicted", "failed")


class WorkItemRunner(Protocol):
    def __call__(self, *, argv: list[str]) -> int: ...


def is_work_item_session_action(*, action_id: ActionId) -> bool:
    return action_id in (
        WORK_ITEM_SESSION_FINISH,
        WORK_ITEM_SESSION_RESUME,
        WORK_ITEM_SESSION_START,
    )


def _result(*, action_id: ActionId, outcome: str, reason: str, mutated: bool) -> ActResult:
    return {"action_id": action_id, "mutated": mutated, "outcome": outcome, "reason": reason}


def _refused(*, action_id: ActionId, reason: str) -> ActResult:
    return _result(action_id=action_id, outcome="refused", reason=reason, mutated=False)


def _acted(*, action_id: ActionId, reason: str) -> ActResult:
    return _result(action_id=action_id, outcome="acted", reason=reason, mutated=True)


def _str_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value != "" else None


def _payload(*, proposal: dict[str, object]) -> dict[str, object] | None:
    return jsonio.as_object(value=proposal.get("work_item_session"))


def _state_dir(*, repo: Path, work_item_id: str) -> Path:
    return repo / "tmp" / "overseer" / "foreman" / "work-items" / work_item_id


def _read_json(*, path: Path) -> dict[str, object] | None:
    try:
        return jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    except OSError:
        return None


def _write_json(*, path: Path, payload: dict[str, object]) -> None:
    registry.atomic_write(path=path, body=json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _append_event(*, directory: Path, record: dict[str, object]) -> None:
    path = directory / "journal.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        _ = handle.write(json.dumps(record, sort_keys=True) + "\n")


def _snapshot_generation_changed(
    *, proposal: dict[str, object], document: dict[str, object]
) -> str | None:
    expected = jsonio.as_object(value=proposal.get("snapshot"))
    current = jsonio.as_object(value=document.get("snapshot"))
    if expected is None or current is None:  # pragma: no cover
        return "malformed_proposal"
    if document.get("repo") != proposal.get("repo"):
        return "repo_identity_changed"
    if current.get("daemon_instance_id") != expected.get("daemon_instance_id"):
        return "daemon_identity_changed"
    if current.get("tick_generation") != expected.get("tick_generation"):
        return "tick_generation_changed"
    return None


def _has_work_item(*, document: dict[str, object], work_item_id: str) -> bool:
    attention = jsonio.as_object(value=document.get("needs_attention")) or {}
    items = jsonio.as_list(value=attention.get("items")) or []
    objects = [jsonio.as_object(value=item) for item in items]
    return any(item is not None and item.get("id") == work_item_id for item in objects)


def _terminal_status(*, payload: dict[str, object]) -> str | None:
    terminal = jsonio.as_object(value=payload.get("terminal")) or {}
    status = _str_field(payload=terminal, key="status")
    return status if status in _TERMINAL_STATUSES else None


def _coordinates_match(*, proposal: dict[str, object], payload: dict[str, object]) -> bool:
    work_item_id = _str_field(payload=payload, key="work_item_id")
    return (
        work_item_id is not None
        and work_item_id == payload.get("session_name")
        and work_item_id == proposal.get("topic")
        and work_item_id == proposal.get("session_name")
        and "/" not in work_item_id
    )


def _validated_context(
    *, action_id: ActionId, proposal: dict[str, object], document: dict[str, object]
) -> tuple[str | None, Path | None, dict[str, object] | None]:
    repo_text = _str_field(payload=proposal, key="repo")
    payload = _payload(proposal=proposal)
    refusal = _snapshot_generation_changed(proposal=proposal, document=document)
    if refusal is not None:
        return refusal, None, None
    if repo_text is None or payload is None or not Path(repo_text).is_absolute():
        return "malformed_work_item_session", None, None
    work_item_id = _str_field(payload=payload, key="work_item_id")
    if not _coordinates_match(proposal=proposal, payload=payload) or work_item_id is None:
        return "work_item_identity_changed", None, None
    if action_id != WORK_ITEM_SESSION_FINISH and not _has_work_item(
        document=document, work_item_id=work_item_id
    ):
        return "work_item_evidence_missing", None, None
    return None, Path(repo_text), payload


def _handoff_paths(*, repo: Path, work_item_id: str) -> tuple[Path, Path]:
    directory = _state_dir(repo=repo, work_item_id=work_item_id)
    return directory / "handoff.md", directory / "handoff.json"


def _write_handoff(*, repo: Path, payload: dict[str, object]) -> Path | None:
    content = _str_field(payload=payload, key="handoff")
    work_item_id = _str_field(payload=payload, key="work_item_id")
    if content is None or work_item_id is None:
        return None
    handoff, meta = _handoff_paths(repo=repo, work_item_id=work_item_id)
    registry.atomic_write(path=handoff, body=content)
    _write_json(path=meta, payload={"work_item_id": work_item_id, "path": str(handoff)})
    return handoff


def _next_attempt(*, outcome: dict[str, object] | None) -> int:
    if outcome is None or outcome.get("status") == "completed":
        return 1
    value = outcome.get("attempt")
    return value + 1 if isinstance(value, int) else 1


def _start_command(*, repo: Path, session_name: str, handoff: Path) -> list[str]:
    prompt = f"read {handoff} and complete this bounded one-shot work-item session"
    return [
        "tmux",
        "new-session",
        "-d",
        "-s",
        session_name,
        "-c",
        str(repo),
        "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        prompt,
    ]


def _resume_command(*, proposal: dict[str, object], handoff: Path) -> list[str] | None:
    classifier = jsonio.as_object(value=proposal.get("classifier")) or {}
    resume = jsonio.as_object(value=classifier.get("resume"))
    if resume is None:
        return None
    return resume_command_from_payload(
        payload={**resume, "handoff_path": str(handoff), "topic": str(proposal["topic"])}
    )


def _act_start(
    *,
    action_id: ActionId,
    repo: Path,
    proposal: dict[str, object],
    payload: dict[str, object],
    run: WorkItemRunner,
) -> ActResult:
    classifier = jsonio.as_object(value=proposal.get("classifier")) or {}
    if classifier.get("action") != "start":
        return _refused(action_id=action_id, reason="classifier_report_only")
    work_item_id = str(payload["work_item_id"])
    directory = _state_dir(repo=repo, work_item_id=work_item_id)
    claim = directory / "claim.json"
    outcome = _read_json(path=directory / "outcome.json")
    if claim.exists():
        return _refused(action_id=action_id, reason="work_item_claim_active")
    handoff = _write_handoff(repo=repo, payload=payload)
    if handoff is None:
        return _refused(action_id=action_id, reason="missing_handoff")
    attempt = _next_attempt(outcome=outcome)
    claim_payload: dict[str, object] = {
        "attempt": attempt,
        "session_name": work_item_id,
        "work_item_id": work_item_id,
    }
    _write_json(path=claim, payload=claim_payload)
    _append_event(directory=directory, record={"event": "claim", **claim_payload})
    code = run(argv=_start_command(repo=repo, session_name=work_item_id, handoff=handoff))
    if code != 0:  # pragma: no cover
        return _refused(action_id=action_id, reason=f"command_exit_{code}")
    return _acted(action_id=action_id, reason="work_item_session_started")


def _act_resume(
    *,
    action_id: ActionId,
    repo: Path,
    proposal: dict[str, object],
    payload: dict[str, object],
    run: WorkItemRunner,
) -> ActResult:
    classifier = jsonio.as_object(value=proposal.get("classifier")) or {}
    if classifier.get("action") != "exact_resume":
        return _refused(action_id=action_id, reason="classifier_report_only")
    work_item_id = str(payload["work_item_id"])
    handoff, _meta = _handoff_paths(repo=repo, work_item_id=work_item_id)
    if (
        not handoff.exists()
        or not (_state_dir(repo=repo, work_item_id=work_item_id) / "claim.json").exists()
    ):
        return _refused(action_id=action_id, reason="missing_handoff")
    handoff = _write_handoff(repo=repo, payload=payload) or handoff
    command = _resume_command(proposal=proposal, handoff=handoff)
    if command is None:  # pragma: no cover
        return _refused(action_id=action_id, reason="classifier_mismatch")
    code = run(argv=command)
    if code != 0:  # pragma: no cover
        return _refused(action_id=action_id, reason=f"command_exit_{code}")
    return _acted(action_id=action_id, reason="work_item_session_resumed")


def _act_finish(*, action_id: ActionId, repo: Path, payload: dict[str, object]) -> ActResult:
    work_item_id = str(payload["work_item_id"])
    directory = _state_dir(repo=repo, work_item_id=work_item_id)
    claim = directory / "claim.json"
    handoff, _meta = _handoff_paths(repo=repo, work_item_id=work_item_id)
    status = _terminal_status(payload=payload)
    claim_payload = _read_json(path=claim)
    if status is None or claim_payload is None or not handoff.exists():
        return _refused(action_id=action_id, reason="missing_handoff")
    outcome = {**claim_payload, "claim_path": str(claim), "status": status}
    _write_json(path=directory / "outcome.json", payload=outcome)
    _append_event(directory=directory, record={"event": "terminal", **outcome})
    claim.unlink(missing_ok=True)
    return _acted(action_id=action_id, reason=f"work_item_session_{status}")


def act_work_item_session(
    *,
    action_id: ActionId,
    proposal: dict[str, object],
    document: dict[str, object],
    run: WorkItemRunner,
) -> ActResult:
    refusal, repo, payload = _validated_context(
        action_id=action_id, proposal=proposal, document=document
    )
    if refusal is not None or repo is None or payload is None:
        return _refused(action_id=action_id, reason=refusal or "malformed_work_item_session")
    if action_id == WORK_ITEM_SESSION_FINISH:
        return _act_finish(action_id=action_id, repo=repo, payload=payload)
    if action_id == WORK_ITEM_SESSION_RESUME:
        return _act_resume(
            action_id=action_id, repo=repo, proposal=proposal, payload=payload, run=run
        )
    return _act_start(action_id=action_id, repo=repo, proposal=proposal, payload=payload, run=run)
