"""Authoritative sources for final-ruling attention.

THE SEAT'S ANSWER IS READ FROM THE LIVE LEDGER. :func:`ledger_comment_moved`
used to read ``<repo>/tmp/overseer/ledger-items/<item-id>.json``; measured
2026-08-30 (work-item ``overseer-764a.9``) NOTHING in this repository writes
that file and it exists in none of the fourteen watched repositories, so the
check answered ``False`` for every seat and the caller's "unheeded" predicate
collapsed to "the branch did not move" — a seat that ANSWERED a final ruling on
the ledger was reported as ignoring it. It now reads live comments through the
:class:`ledger_comments.CommentReader` seam ``foreman_relay_strikes`` already
adopted, which is the same store the ruling was relayed against.

AN UNREADABLE LEDGER IS NOT "NO ANSWER". :func:`ledger_comment_moved` answers a
:class:`LedgerAnswer` carrying the source beside the verdict, so a ledger that
could not be read at all stays its own condition instead of rendering exactly
like a seat that was read and said nothing. A bare ``False`` cannot hold that
distinction, and losing it is how a missing input reads as evidence.

TWO EXEMPTIONS WERE RETIRED WITH THAT FILE RATHER THAN REWIRED, so
:func:`exemption_label` emits two labels and not four.

``infra-external`` read ``metadata.blocked_reason`` out of the same
producerless ledger-item file. Nothing wrote it, so the branch was unreachable.

``caam-quota-exhausted`` read ``<repo>/tmp/overseer/caam-quota.json``, which
nothing writes either, and it is not merely missing a producer: CAAM keeps its
state host-wide under ``$HOME/.local/state/caam-usage-rotate/state.json`` and
projects nothing per repository, and this reader carried no recency floor — so a
file dropped there once would have exempted the seat forever. Removal is right
on the merits; do not give it a producer.

``credential-exhaustion`` and ``factory-host-failure`` read the dispatch journal
and the detached-dispatch logs, both of which this repository does write. They
are unchanged.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import jsonio
import ledger_comments

__all__: list[str] = [
    "FinalRelay",
    "LedgerAnswer",
    "branch_moved",
    "exemption_label",
    "ledger_comment_moved",
    "read_journal",
    "relay_from_record",
    "timestamp",
]

_GIT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True, kw_only=True)
class FinalRelay:
    at: float
    item_id: str
    session_identity: str | None
    branch: str | None
    branch_head: str | None
    latest_plan_comment_at: float | None


@dataclass(frozen=True, kw_only=True)
class LedgerAnswer:
    """Whether the seat answered on the ledger, and whether the ledger was read.

    ``source`` is one of ``ledger_comments.SOURCE_LEDGER`` /
    ``ledger_comments.SOURCE_UNAVAILABLE``; see the module docstring on why
    ``moved`` alone is not enough.
    """

    moved: bool
    source: str


def relay_from_record(
    *, record: dict[str, object], fallback_item_id: str | None
) -> FinalRelay | None:
    _ = fallback_item_id
    if record.get("final") is not True:
        return None
    at = timestamp(value=record.get("at"))
    item_id = string_value(value=record.get("work_item_id"))
    if at is None or item_id is None:
        return None
    return FinalRelay(
        at=at,
        item_id=item_id,
        session_identity=string_value(value=record.get("session_identity")),
        branch=string_value(value=record.get("branch")),
        branch_head=string_value(value=record.get("branch_head")),
        latest_plan_comment_at=timestamp(value=record.get("latest_plan_comment_at")),
    )


def exemption_label(*, repo: Path, item_id: str, floor_at: float) -> str | None:
    """The reachable reason a final ruling went unanswered, or None.

    Only two labels remain; the module docstring records which two were retired
    and why re-adding a producer for either would be the wrong repair.
    """
    if credential_exhaustion_refusal(repo=repo, item_id=item_id, floor_at=floor_at):
        return "credential-exhaustion"
    if factory_host_failure(repo=repo, item_id=item_id):
        return "factory-host-failure"
    return None


def branch_moved(*, repo: Path, relay: FinalRelay) -> bool:
    if relay.branch is None or relay.branch_head is None:
        return False
    try:
        completed = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo), "rev-parse", relay.branch],  # noqa: S607
            capture_output=True,
            check=False,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and completed.stdout.strip() != relay.branch_head


def ledger_comment_moved(
    *,
    repo: Path,
    relay: FinalRelay,
    comments: ledger_comments.CommentReader | None = None,
) -> LedgerAnswer:
    """Whether the seat commented on its item after the final ruling was relayed.

    ``comments`` defaults to the live reader, resolved at CALL time so a caller
    — or a test — can substitute the seam without reaching past this module.
    """
    reader = ledger_comments.read_comments if comments is None else comments
    recorded = reader(repo=repo, work_item_id=relay.item_id)
    if recorded is None:
        return LedgerAnswer(moved=False, source=ledger_comments.SOURCE_UNAVAILABLE)
    latest = timestamp(value=ledger_comments.latest_comment_at(comments=recorded))
    floor = relay.latest_plan_comment_at if relay.latest_plan_comment_at is not None else relay.at
    return LedgerAnswer(
        moved=latest is not None and latest > floor,
        source=ledger_comments.SOURCE_LEDGER,
    )


def credential_exhaustion_refusal(*, repo: Path, item_id: str, floor_at: float) -> bool:
    records = read_journal(repo=repo) or ()
    matches = tuple(
        record
        for record in records
        if (record_at := timestamp(value=record.get("at"))) is not None
        and record_at >= floor_at
        and dispatch_outcome_item_id(record=record) == item_id
        and dispatch_outcome_status(record=record) in {"refused", "failed"}
    )
    if not matches:
        return False
    reason = dispatch_outcome_detail(record=matches[-1]) or ""
    return "429" in reason and "exhaust" in reason.lower()


def dispatch_outcome(*, record: dict[str, object]) -> dict[str, object] | None:
    if record.get("stage") != "outcome":
        return None
    return jsonio.as_object(value=record.get("outcome"))


def dispatch_outcome_item_id(*, record: dict[str, object]) -> str | None:
    outcome = dispatch_outcome(record=record) or {}
    return string_value(value=outcome.get("work_item_id"))


def dispatch_outcome_status(*, record: dict[str, object]) -> str | None:
    outcome = dispatch_outcome(record=record) or {}
    return string_value(value=outcome.get("status"))


def dispatch_outcome_detail(*, record: dict[str, object]) -> str | None:
    outcome = dispatch_outcome(record=record) or {}
    return string_value(value=outcome.get("detail"))


def factory_host_failure(*, repo: Path, item_id: str) -> bool:
    root = repo / "tmp" / "overseer" / "detached-dispatch"
    try:
        logs = tuple(root.glob(f"{item_id}-*/output.log"))
    except OSError:
        return False
    for log in logs:
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "fabro-run" in text and ("ENOSPC" in text or "No space left on device" in text):
            return True
    return False


def read_journal(*, repo: Path) -> tuple[dict[str, object], ...] | None:
    path = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    records: list[dict[str, object]] = []
    for line in lines:
        parsed = jsonio.parse_object_line(line=line)
        if not jsonio.is_parse_failure(result=parsed):
            record = parsed.unwrap()
            if record is not None:
                records.append(record)
    return tuple(records)


def timestamp(*, value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def string_value(*, value: object) -> str | None:
    return value if isinstance(value, str) and value else None
