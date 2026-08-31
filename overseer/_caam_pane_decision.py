"""One caam model-enforcement decision about one pane, as one span record.

This is the vocabulary and the record shape; ``caam_sessions`` owns the branching
that reaches each decision, and ``_caam_span`` owns putting the record on the wire.
Keeping the three apart is what lets the decision names be asserted by a test
without a collector, and lets the wire format change without touching enforcement.

WHY THE VOCABULARY IS EXPLICIT rather than derived from the operator message.
The messages enforcement already returns are written for a human reading a pane:
several decisions produce NO message at all (a pane already on the wanted model,
a suppressed pane, a spent unknown-verify), and the three that do share a shape
that a query cannot reliably split. The 2026-08-30/31
"livespec-overseer-foreman unknown->fable" incident turned on exactly the
distinctions the messages drop -- so the decision is named at the point it is
made, not reconstructed afterwards.

ATTRIBUTE NAMES. ``caam.*`` for the subject (which pane, which session id, which
transcript) and the outcome (decision, driven, picker outcome); ``model.*`` for
the models themselves (what was read, from which source, what was wanted). The
split is deliberate: a Honeycomb reader filtering on `model.read = unknown`
should see every rotation subject that read unknown, whatever decided it.

Absent values are named, never omitted. A missing attribute and an attribute
reading "none" are different queries, and a span whose key set varies by branch
cannot be grouped -- so ``caam.transcript.path``, ``model.read`` and
``caam.picker.outcome`` each carry an explicit placeholder instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

import _caam_span

__all__: list[str] = [
    "DECISION_BUSY",
    "DECISION_DRIVE",
    "DECISION_OPERATOR_SET_KEPT",
    "DECISION_SKIP_ALREADY_SET",
    "DECISION_SKIP_RECENTLY_SET",
    "DECISION_SKIP_UNKNOWN_VERIFIED",
    "DECISION_WOULD",
    "MODEL_READ_UNKNOWN",
    "PANE_DECISION_EVENT",
    "PICKER_OUTCOME_ERROR",
    "PICKER_OUTCOME_NONE",
    "TRANSCRIPT_NONE",
    "PaneEventEmitter",
    "PaneOutcome",
    "PaneSubject",
    "pane_decision_record",
]

PANE_DECISION_EVENT: Final = "caam.enforcement.pane"

DECISION_SKIP_ALREADY_SET: Final = "skip-already-set"
DECISION_SKIP_RECENTLY_SET: Final = "skip-recently-set"
DECISION_SKIP_UNKNOWN_VERIFIED: Final = "skip-unknown-verified"
DECISION_OPERATOR_SET_KEPT: Final = "operator-set-kept"
DECISION_BUSY: Final = "busy"
DECISION_WOULD: Final = "would"
DECISION_DRIVE: Final = "drive"

MODEL_READ_UNKNOWN: Final = "unknown"
TRANSCRIPT_NONE: Final = "none"
PICKER_OUTCOME_NONE: Final = "none"
PICKER_OUTCOME_ERROR: Final = "error"


class PaneEventEmitter(Protocol):
    """Where a finished decision record goes.

    Deliberately narrower than the seam it is usually bound to: an emitter answers
    nothing, because enforcement must not be able to branch on whether telemetry
    reached a collector.
    """

    def __call__(self, *, record: Mapping[str, object]) -> None: ...


@dataclass(frozen=True, kw_only=True)
class PaneSubject:
    """WHICH pane the record is about, and what the pass read for it."""

    session: str
    session_id: str
    transcript: str | None
    model_read: str | None
    read_source: str


@dataclass(frozen=True, kw_only=True)
class PaneOutcome:
    """WHAT the pass decided about that pane, and what came of it."""

    want: str
    decision: str
    driven: bool
    picker_outcome: str | None


def pane_decision_record(
    *, subject: PaneSubject, outcome: PaneOutcome, at: float
) -> dict[str, object]:
    """The one record a pass emits about one pane."""

    return {
        "ts": _caam_span.iso_timestamp(at=at),
        "event": PANE_DECISION_EVENT,
        "caam.session": subject.session,
        "caam.session_id": subject.session_id,
        "caam.transcript.path": _named(value=subject.transcript, absent=TRANSCRIPT_NONE),
        "model.read": _named(value=subject.model_read, absent=MODEL_READ_UNKNOWN),
        "model.read.source": subject.read_source,
        "model.want": outcome.want,
        "caam.decision": outcome.decision,
        "caam.driven": outcome.driven,
        "caam.picker.outcome": _named(value=outcome.picker_outcome, absent=PICKER_OUTCOME_NONE),
    }


def _named(*, value: str | None, absent: str) -> str:
    return absent if value is None else value
