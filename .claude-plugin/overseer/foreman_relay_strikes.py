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
import ledger_comments

__all__: list[str] = [
    "FINAL_RELAY_SENTENCE",
    "RelayPreparation",
    "count_objections",
    "plan_objections",
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
    comments: ledger_comments.CommentReader


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
            comments=_comment_reader(value=options.get("comments")),
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


def plan_objections(
    *,
    repo: Path,
    plan_epic_id: str,
    fingerprint: str,
    comments: ledger_comments.CommentReader = ledger_comments.read_comments,
) -> ledger_comments.ObjectionTally:
    """Objections against ``fingerprint`` recorded on the plan epic's ledger.

    The tally keeps an unreadable ledger distinguishable from a plan epic that
    carries no objection; a bare count cannot, and conflating them is what let
    a counter with no input at all report a confident zero.
    """
    return ledger_comments.objection_tally(
        comments=comments(repo=repo, work_item_id=plan_epic_id), fingerprint=fingerprint
    )


def count_objections(
    *,
    repo: Path,
    plan_epic_id: str,
    fingerprint: str,
    comments: ledger_comments.CommentReader = ledger_comments.read_comments,
) -> int:
    """How many recorded objections match ``fingerprint``.

    Callers that must act on an unreadable ledger use :func:`plan_objections`,
    which reports the source alongside the count.
    """
    return plan_objections(
        repo=repo, plan_epic_id=plan_epic_id, fingerprint=fingerprint, comments=comments
    ).count


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
    # One ledger read serves both fields; they describe the same comment set,
    # and reading it twice would let them disagree.
    recorded = context.comments(repo=context.repo, work_item_id=context.plan_epic_id)
    tally = ledger_comments.objection_tally(comments=recorded, fingerprint=context.fingerprint)
    record: dict[str, object] = {
        "stage": "foreman-act-relay",
        "action_id": context.action_id,
        "repo": str(context.repo),
        "topic": context.topic,
        "work_item_id": context.plan_epic_id,
        "session_identity": _string_field(payload=context.row, key="session_identity"),
        "ruling_fingerprint": context.fingerprint,
        "objections_remaining": objections_remaining,
        "matching_objections": tally.count,
        "objections_source": tally.source,
        "latest_plan_comment_at": ledger_comments.latest_comment_at(comments=recorded),
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


def _comment_reader(*, value: object) -> ledger_comments.CommentReader:
    if value is None:
        return ledger_comments.read_comments
    return cast("ledger_comments.CommentReader", value)


def _plan_epic_id(*, row: dict[str, object], topic: str) -> str:
    return _string_field(payload=row, key="epic") or f"unresolved-plan-epic:{topic}"


def _string_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None
