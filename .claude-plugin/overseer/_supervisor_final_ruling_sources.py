"""Authoritative sources for final-ruling attention.

THE PLAN-EPIC COMMENT CHANNEL IS READ LIVE, NOT FROM A CACHE. A predecessor
sourced a seat's answer from ``<repo>/tmp/overseer/ledger-items/<item-id>.json``
and its quota exemption from ``<repo>/tmp/overseer/caam-quota.json``. Measured
2026-08-30 (work-item ``overseer-764a.8``): NOTHING in the tracked tree — no
module, script, plugin bin or prose — has ever written either path, and neither
existed in any of the fourteen watched repositories on the supervising host
after weeks of live supervision. Both reads failed closed, so three shipped
behaviours were structurally unreachable:

* :func:`ledger_comment_moved` answered ``False`` for every seat, every ruling
  and every epic, which meant ANSWERING A FINAL RULING ON THE LEDGER — the
  documented way to respond — could never count as heeding it. Only a moved
  branch could clear the condition.
* :func:`exemption_label` could emit only two of its four labels;
  ``infra-external`` and ``caam-quota-exhausted`` read the two dead roots.

The comment channel now goes through :data:`LEDGER_COMMENTS`, the same live
``bd comments`` seam ``foreman_relay_strikes`` adopted for the identical defect
in its own reader, and :func:`ledger_comment_movement` keeps an UNREADABLE
ledger distinguishable from a seat that genuinely never answered — conflating
the two is how a reader with no input at all reported a confident verdict.

THE TWO DEAD EXEMPTION BRANCHES WERE REMOVED RATHER THAN REWIRED, because
neither has a producer to rewire them to.

* ``infra-external`` gated on a work item's ``metadata.blocked_reason``. No live
  item-metadata read is wired into this path, and ``.ai/ledger-valves-and-holds.md``
  records that ``blocked_reason`` is a policy field serialised into an annotating
  label — read only to NAME the reason on a row already ``blocked``, and
  vestigial otherwise. Reinstating the branch means first MEASURING which field
  ``bd show --json`` actually carries it under; writing a reader against a guessed
  wire format is the very defect being repaired here.
* ``caam-quota-exhausted`` gated on a per-repo CAAM quota surface that was
  designed but never built. The thirty-odd ``caam_*`` modules keep their state
  host-wide in ``$HOME/.local/state/caam-usage-rotate/state.json`` and project
  nothing per repository, and the removed reader had no recency floor either, so
  a stale file would have exempted a seat forever.

Their design intent survives in ``plan/foreman-full-autonomy-option/research/``;
``scripts/check-report-only-artifact-producers.py`` now registers both roots as
RETIRED so a future reader of either fails the aggregate rather than shipping
silent again.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import jsonio
import ledger_comments

__all__: list[str] = [
    "LEDGER_COMMENTS",
    "FinalRelay",
    "LedgerMovement",
    "branch_moved",
    "exemption_label",
    "ledger_comment_moved",
    "ledger_comment_movement",
    "read_journal",
    "relay_from_record",
    "timestamp",
]

_GIT_TIMEOUT_SECONDS = 5.0

LEDGER_COMMENTS: ledger_comments.CommentReader = ledger_comments.read_comments
"""The live plan-epic comment read. Patch THIS module's binding to redirect it."""


@dataclass(frozen=True, kw_only=True)
class FinalRelay:
    at: float
    item_id: str
    session_identity: str | None
    branch: str | None
    branch_head: str | None
    latest_plan_comment_at: float | None


@dataclass(frozen=True, kw_only=True)
class LedgerMovement:
    """Whether the seat answered after the ruling, and whether the ledger answered."""

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
    """The closed exemption set, now exactly the branches that have a producer."""
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


def ledger_comment_moved(*, relay: FinalRelay, comments: Sequence[object]) -> bool:
    """Whether ``comments`` carries an answer newer than the ruling's floor.

    A pure predicate over a comment set held in hand, so it can be proven both
    ways without the store the caller happens to read from.
    """
    latest = timestamp(value=ledger_comments.latest_comment_at(comments=comments))
    if latest is None:
        return False
    floor = relay.latest_plan_comment_at if relay.latest_plan_comment_at is not None else relay.at
    return latest > floor


def ledger_comment_movement(*, repo: Path, relay: FinalRelay) -> LedgerMovement:
    """Read the plan epic's comments live, keeping an unreadable ledger its own case."""
    comments = LEDGER_COMMENTS(repo=repo, work_item_id=relay.item_id)
    if comments is None:
        return LedgerMovement(moved=False, source=ledger_comments.SOURCE_UNAVAILABLE)
    return LedgerMovement(
        moved=ledger_comment_moved(relay=relay, comments=comments),
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
