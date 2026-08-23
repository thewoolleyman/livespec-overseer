"""Relay strike accounting for full-autonomy foreman rulings."""
# livespec-lloc-soft-band-owner: overseer-3h4s5w.6

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final, cast

import _supervisor_final_ruling_sources
import foreman_valve_policy
import jsonio

__all__: list[str] = [
    "FINAL_RELAY_SENTENCE",
    "RelayPreparation",
    "count_objections",
    "prepare_blocked_answer_relay",
    "prepare_relay",
    "relay_text",
    "ruling_fingerprint",
]

FINAL_RELAY_SENTENCE: Final[str] = (
    "This is the final relay for this ruling; you must now take the action "
    "and must not record a further objection."
)
_MAX_RELAYS: Final[int] = 3
_INCIDENTAL_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "at",
        "final",
        "latest_plan_comment_at",
        "objections_remaining",
        "relay_count",
        "session_identity",
    }
)


@dataclass(frozen=True, kw_only=True)
class RelayPreparation:
    record: dict[str, object]
    fingerprint: str
    objections_remaining: int
    final: bool
    final_sentence: str | None
    refusal: str | None = None


@dataclass(frozen=True, kw_only=True)
class RelayContext:
    repo: Path
    action_id: str
    topic: str
    row: dict[str, object]
    plan_epic_id: str
    fingerprint: str


def ruling_fingerprint(*, payload: dict[str, object]) -> str:
    stable = {key: value for key, value in payload.items() if key not in _INCIDENTAL_FIELDS}
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def prepare_relay(
    *,
    repo: Path,
    action_id: str,
    topic: str,
    row: dict[str, object],
    payload: dict[str, object],
    **options: object,
) -> RelayPreparation:
    full_autonomy = options.get("full_autonomy") is True
    records = _record_sequence(value=options.get("records"))
    fingerprint = ruling_fingerprint(payload=payload)
    plan_epic_id = _plan_epic_id(row=row, topic=topic)
    prior = _prior_relay_count(
        records=records or (),
        plan_epic_id=plan_epic_id,
        fingerprint=fingerprint,
    )
    remaining = max(0, _MAX_RELAYS - prior - 1)
    if prior >= _MAX_RELAYS:
        return RelayPreparation(
            record={},
            fingerprint=fingerprint,
            objections_remaining=0,
            final=False,
            final_sentence=None,
            refusal="relay_strike_limit_reached",
        )
    final = full_autonomy and prior == _MAX_RELAYS - 1
    record = _relay_record(
        context=RelayContext(
            repo=repo,
            action_id=action_id,
            topic=topic,
            row=row,
            plan_epic_id=plan_epic_id,
            fingerprint=fingerprint,
        ),
        objections_remaining=remaining,
        final=final,
    )
    return RelayPreparation(
        record=record,
        fingerprint=fingerprint,
        objections_remaining=remaining,
        final=final,
        final_sentence=FINAL_RELAY_SENTENCE if final else None,
    )


def count_objections(*, repo: Path, plan_epic_id: str, fingerprint: str) -> int:
    item = _read_json_object(
        path=repo / "tmp" / "overseer" / "ledger-items" / f"{plan_epic_id}.json"
    )
    comments = jsonio.as_list(value=None if item is None else item.get("comments")) or []
    return sum(
        1
        for comment in comments
        if _is_matching_objection(comment=comment, fingerprint=fingerprint)
    )


def relay_text(*, answer_text: str, relay: RelayPreparation) -> str:
    suffixes: dict[str | None, str] = {None: ""}
    suffix = suffixes.get(relay.final_sentence, f"\n\n{relay.final_sentence}")
    return f"{answer_text}{suffix}"


def prepare_blocked_answer_relay(
    *,
    document: dict[str, object],
    repo: str,
    topic: str,
    row: dict[str, object],
    payload: dict[str, object],
) -> RelayPreparation:
    _ = document
    repo_path = Path(repo)
    disposition = foreman_valve_policy.effective_valve_disposition(repo=repo_path)
    return prepare_relay(
        repo=repo_path,
        action_id="blocked_session_answer",
        topic=topic,
        row=row,
        payload=payload,
        full_autonomy=disposition.get("full_autonomy") is True,
        records=_supervisor_final_ruling_sources.read_journal(repo=repo_path) or (),
    )


def _relay_record(
    *,
    context: RelayContext,
    objections_remaining: int,
    final: bool,
) -> dict[str, object]:
    record: dict[str, object] = {
        "stage": "foreman-act-relay",
        "action_id": context.action_id,
        "repo": str(context.repo),
        "topic": context.topic,
        "work_item_id": context.plan_epic_id,
        "session_identity": _string_field(payload=context.row, key="session_identity"),
        "ruling_fingerprint": context.fingerprint,
        "objections_remaining": objections_remaining,
        "matching_objections": count_objections(
            repo=context.repo,
            plan_epic_id=context.plan_epic_id,
            fingerprint=context.fingerprint,
        ),
        "latest_plan_comment_at": _latest_plan_comment_at(
            repo=context.repo, plan_epic_id=context.plan_epic_id
        ),
    }
    branch = _string_field(payload=context.row, key="branch")
    branch_head = _string_field(payload=context.row, key="branch_head")
    if branch is not None:
        record["branch"] = branch
    if branch_head is not None:
        record["branch_head"] = branch_head
    if final:
        record["final"] = True
        record["final_sentence"] = FINAL_RELAY_SENTENCE
    return record


def _prior_relay_count(
    *,
    records: list[dict[str, object]] | tuple[dict[str, object], ...],
    plan_epic_id: str,
    fingerprint: str,
) -> int:
    return sum(
        1
        for record in records
        if record.get("stage") == "foreman-act-relay"
        and record.get("work_item_id") == plan_epic_id
        and record.get("ruling_fingerprint") == fingerprint
    )


def _record_sequence(*, value: object) -> tuple[dict[str, object], ...]:
    values = () if value is None else cast(list[dict[str, object]], value)
    return tuple(values)


def _is_matching_objection(*, comment: object, fingerprint: str) -> bool:
    payload = jsonio.as_object(value=comment)
    text = "" if payload is None else _string_field(payload=payload, key="text") or ""
    first = (text.splitlines() or [""])[0]
    return first.startswith(f"OBJECTION {fingerprint}:")


def _latest_plan_comment_at(*, repo: Path, plan_epic_id: str) -> str | None:
    item = _read_json_object(
        path=repo / "tmp" / "overseer" / "ledger-items" / f"{plan_epic_id}.json"
    )
    comments = jsonio.as_list(value=None if item is None else item.get("comments")) or []
    timestamps = tuple(
        value
        for comment in (jsonio.as_object(value=raw) for raw in comments)
        if comment is not None
        and (
            value := _string_field(payload=comment, key="created_at")
            or _string_field(payload=comment, key="at")
        )
        is not None
    )
    return max(timestamps) if timestamps else None


def _plan_epic_id(*, row: dict[str, object], topic: str) -> str:
    return _string_field(payload=row, key="epic") or f"unresolved-plan-epic:{topic}"


def _read_json_object(*, path: Path) -> dict[str, object] | None:
    try:
        parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()


def _string_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None
