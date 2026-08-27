"""State dispatch capacity from a verdict, or state that it is unknown.

Ratified by v035 in `SPECIFICATION/spec.md`, in its relay and escalation floors:
any statement the foreman makes about dispatch CAPACITY — in a tick report, an
escalation, a panel dossier, or any other surface it authors — MUST be sourced
from a capacity verdict, either the one carried by the attention view it
composes or the equivalent verdict the dispatch machinery itself reports. Where
no such verdict is available the foreman MUST state that capacity is unknown and
MUST NOT substitute an inference.

THE MOTIVATING INCIDENT IS WHY THIS IS A MODULE RATHER THAN A SENTENCE. Three
surfaces asserted the same wrong thing about capacity because each re-derived it
from raw work-item statuses, and agreement between observers sharing a mistake
reads as corroboration rather than as the single error it was. So there is
exactly ONE statement here, and every surface renders that same statement: a
surface cannot disagree with another, because there is nothing of its own for it
to disagree with.

NO WORK-ITEM STATUS IS READ HERE, AND NONE MAY BE ADDED. A count of rows reading
`active` is not a capacity verdict: it does not know the cap, it does not know
what the dispatch machinery is actually holding, and in this fleet an `active`
row is routinely a phantom claim behind which no run exists. That count is
precisely the derivation the incident performed. The attention view this reads
carries those rows in the SAME document as the verdict, and they are passed over
deliberately.

UNAVAILABILITY IS AN ANSWER, NOT A FAULT, AND EVERYTHING FAILS TOWARD UNKNOWN.
An absent view, a view carrying no capacity report, a report whose fields cannot
be read as slot counts, and a journal carrying no capacity report all resolve
UNKNOWN with the reason recorded. An UNKNOWN statement asserts nothing about any
slot: its free-slot count is absent rather than zero, because zero is itself the
claim that the queue is closed.

NO RECENCY BOUND IS APPLIED, AND ITS ABSENCE IS DELIBERATE. A verdict is
available or it is not; how recent one must be to be worth stating is a
maintainer-owned judgement of the same kind as the UNROUTED-PLAN BOUND, which
the same ratified contract says the foreman never chooses for itself. Inventing
a window here would be this module choosing exactly such a value. The verdict's
own observation instant rides on every statement instead, so a reader can weigh
its age against a bound this module never guesses at.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import jsonio
import streams
from _supervisor_snapshot import DEFAULT_STATUS_PATH
from foreman_gather_collect import compose_document

__all__: list[str] = [
    "ATTENTION_VIEW",
    "AVAILABLE",
    "CAPACITY_STAGES",
    "DISPATCH_MACHINERY",
    "NO_VERDICT_AVAILABLE",
    "SATURATED",
    "SURFACES",
    "UNKNOWN",
    "CapacityStatement",
    "CapacityVerdict",
    "attention_view_verdict",
    "capacity_statement",
    "capacity_verdict",
    "dispatch_machinery_verdict",
    "main",
]

AVAILABLE: Final[str] = "available"
SATURATED: Final[str] = "saturated"
UNKNOWN: Final[str] = "unknown"
ATTENTION_VIEW: Final[str] = "attention_view"
DISPATCH_MACHINERY: Final[str] = "dispatch_machinery"
NO_VERDICT_AVAILABLE: Final[str] = "no_capacity_verdict_available"
# Every surface the ratified clause names, and the fourth case it closes with:
# any other surface the foreman authors renders this same statement too.
SURFACES: Final[tuple[str, ...]] = ("escalation", "panel-dossier", "tick-report")
# The stages under which the dispatch machinery reports its own capacity. A
# stage outside this set carries no verdict, however many slot-shaped fields it
# happens to have.
CAPACITY_STAGES: Final[frozenset[str]] = frozenset({"capacity", "capacity-deferred"})
_ACTIVE_COUNT_KEY: Final[str] = "active_count"
_AT_KEY: Final[str] = "at"
_CAPACITY_KEY: Final[str] = "capacity"
_FREE_SLOTS_KEY: Final[str] = "free_slots"
_JOURNAL_KEY: Final[str] = "dispatch_journal"
_NEEDS_ATTENTION_KEY: Final[str] = "needs_attention"
_OBSERVED_AT_KEY: Final[str] = "observed_at"
_STAGE_KEY: Final[str] = "stage"
_WIP_CAP_KEY: Final[str] = "wip_cap"
_UNKNOWN_SENTENCE: Final[str] = (
    "dispatch capacity is unknown: no capacity verdict is available from the "
    "attention view or from the dispatch machinery, so no slot is asserted "
    "occupied or free"
)


@dataclass(frozen=True, kw_only=True)
class CapacityVerdict:
    """A capacity report some source made, and which source made it."""

    free_slots: int
    observed_at: str | None
    report: dict[str, object]
    source: str


@dataclass(frozen=True, kw_only=True)
class CapacityStatement:
    """The one capacity statement the foreman authors, and what sourced it."""

    free_slots: int | None
    observed_at: str | None
    sentence: str
    source: str | None
    statement: str
    unknown_reason: str | None
    verdict: dict[str, object] | None

    def document(self) -> dict[str, object]:
        return {
            "free_slots": self.free_slots,
            "observed_at": self.observed_at,
            "sentence": self.sentence,
            "source": self.source,
            "statement": self.statement,
            # One sentence, rendered for every surface. The incident was three
            # surfaces each authoring their own; this is what makes that shape
            # unavailable rather than merely discouraged.
            "surfaces": {surface: self.sentence for surface in SURFACES},
            "unknown_reason": self.unknown_reason,
            "verdict": self.verdict,
        }


def _slot_count(*, value: object) -> int | None:
    """Read a slot count, refusing the bool that `isinstance(value, int)` admits."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _free_slots(*, report: dict[str, object]) -> int | None:
    """The free-slot count the SOURCE reported, directly or as its own cap minus its own count."""
    direct = _slot_count(value=report.get(_FREE_SLOTS_KEY))
    if direct is not None:
        return direct
    active = _slot_count(value=report.get(_ACTIVE_COUNT_KEY))
    cap = _slot_count(value=report.get(_WIP_CAP_KEY))
    if active is None or cap is None:
        return None
    return max(cap - active, 0)


def _text(*, value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _verdict(
    *, report: dict[str, object], source: str, observed_at: str | None
) -> CapacityVerdict | None:
    free_slots = _free_slots(report=report)
    if free_slots is None:
        return None
    return CapacityVerdict(
        free_slots=free_slots,
        observed_at=observed_at,
        report=report,
        source=source,
    )


def attention_view_verdict(*, attention: object) -> CapacityVerdict | None:
    """The verdict the attention view CARRIES, never one derived from its rows."""
    view = jsonio.as_object(value=attention)
    report = None if view is None else jsonio.as_object(value=view.get(_CAPACITY_KEY))
    if report is None:
        return None
    return _verdict(
        report=report,
        source=ATTENTION_VIEW,
        observed_at=_text(value=report.get(_OBSERVED_AT_KEY)),
    )


def dispatch_machinery_verdict(*, records: object) -> CapacityVerdict | None:
    """The LATEST capacity report the dispatch machinery made in its own journal.

    The journal is append-only and cumulative, so a scan that stops at the first
    matching record answers with the past. Ordering is by the record's own
    instant, and a record carrying none sorts as the oldest thing there is.
    """
    entries = jsonio.as_list(value=records)
    if entries is None:
        return None
    latest: tuple[str, dict[str, object]] | None = None
    for raw in entries:
        record = jsonio.as_object(value=raw)
        if record is None or record.get(_STAGE_KEY) not in CAPACITY_STAGES:
            continue
        at = _text(value=record.get(_AT_KEY)) or ""
        if latest is None or at >= latest[0]:
            latest = (at, record)
    if latest is None:
        return None
    return _verdict(
        report=latest[1],
        source=DISPATCH_MACHINERY,
        observed_at=_text(value=latest[0]),
    )


def capacity_verdict(*, attention: object, journal_records: object) -> CapacityVerdict | None:
    """Prefer the view the foreman composed for THIS tick; fall back to the machinery's own."""
    carried = attention_view_verdict(attention=attention)
    if carried is not None:
        return carried
    return dispatch_machinery_verdict(records=journal_records)


def _sentence(*, verdict: CapacityVerdict, statement: str) -> str:
    observed = "" if verdict.observed_at is None else f", observed at {verdict.observed_at}"
    return (
        f"dispatch capacity is {statement}: {verdict.free_slots} free slots per the "
        f"{verdict.source} capacity verdict{observed}"
    )


def capacity_statement(*, attention: object, journal_records: object) -> CapacityStatement:
    """The one statement every surface renders, sourced from a verdict or stated unknown."""
    verdict = capacity_verdict(attention=attention, journal_records=journal_records)
    if verdict is None:
        return CapacityStatement(
            free_slots=None,
            observed_at=None,
            sentence=_UNKNOWN_SENTENCE,
            source=None,
            statement=UNKNOWN,
            unknown_reason=NO_VERDICT_AVAILABLE,
            verdict=None,
        )
    statement = AVAILABLE if verdict.free_slots > 0 else SATURATED
    return CapacityStatement(
        free_slots=verdict.free_slots,
        observed_at=verdict.observed_at,
        sentence=_sentence(verdict=verdict, statement=statement),
        source=verdict.source,
        statement=statement,
        unknown_reason=None,
        verdict=verdict.report,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foreman-capacity")
    _ = parser.add_argument("--repo", default=str(Path.cwd()))
    _ = parser.add_argument("--snapshot-path", default=str(DEFAULT_STATUS_PATH))
    _ = parser.add_argument("--journal-path", default=None)
    return parser


def main(*, argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    # The attention view is the one the shipped gatherer COMPOSES, and the
    # journal beside it is the dispatch machinery's own record. No snapshot
    # fallback is configured: capacity is not a property of the panes.
    document = compose_document(
        repo=args.repo,
        snapshot_path=args.snapshot_path,
        list_json_command=None,
        journal_path=args.journal_path,
    )
    statement = capacity_statement(
        attention=document.get(_NEEDS_ATTENTION_KEY),
        journal_records=document.get(_JOURNAL_KEY),
    )
    streams.write_stdout(text=json.dumps(statement.document(), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
