"""Report-only attention for an idle track that has declared nothing, bounded.

`overseer-j2vbcq`. A session can be genuinely human-blocked with no structured
picker — an ordinary free prompt with the question posed in PROSE above it — and
nothing on the attention surface says so. `picker_open` reads false, correctly, and
`human_wait` reads false too, because its three inputs are the visible gate, the
harness's own `waiting` state, and the session's own `blocked:` declaration. A
finished turn at a free prompt sets none of them.

**Two things this module deliberately is not.**

It is NOT a prose-question detector, and that prohibition is structural rather than a
promise: nothing here reads `obs.capture`, and a beside-test pins the absence of that
attribute access in both the source package and its shipped mirror. Sibling
`overseer-i6eu2k` recorded the daemon raising `picker_open` for a session that merely
QUOTED picker markers while describing a PEER's pane, making a healthy seat
unreachable. Recognising an unstructured QUESTION is that same act with no markers to
key on at all, and its false positives would land on escalation records, handoff
entries and research notes — the artifacts this fleet produces when supervision is
working. A false-positive control samples a corpus; it cannot fix a detector whose
errors concentrate on that corpus's best-written members. The full argument is in
`plan/archive/supervision-safety-and-attention-truth/research/prose-question-detector-inversion.md`.

It is also NOT a second nudge ladder, and that cut is recorded rather than left
implicit. The keep-going nudge already keystrokes once per idle episode and already
carries the escape hatch telling a session to write `blocked: <reason>` instead; a
session that ignored that will not be moved by the daemon saying it again, and
`overseer-w2nwx5` records the idle-escalation ladder injecting into
contract-conforming sessions as ITSELF the defect. The countervailing caution — that
report-only surfacing has a measured limit, a seat correctly reporting
ready-uncertifiable for twelve hours while nothing consumed the report — is real, and
the answer to it is a CONSUMER, not a keystroke: this condition is an
`ATTENTION_STATUSES` member, so it reaches the `NEEDS YOU` block and the published
snapshot row rather than sitting in a log nobody reads.

**What it keys on.** Exactly one row status, `idle-with-context-left`, plus the clock.
That status is already the daemon's "idle above threshold and the session has declared
nothing" leaf: `_supervisor_idle.idle_room` reaches it only when the state file is
absent or holds a DAEMON-written token, never a session's own `ready` / `blocked` /
`winding-down`. So the "has not declared" half of the condition is carried by the
status itself, and no second reading of the state file can disagree with the one the
cascade already made.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_config
import _supervisor_liveness
import _supervisor_observe
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = [
    "UNDECLARED_IDLE_CONDITION",
    "UNDECLARED_IDLE_SOURCE_STATUS",
    "UNDECLARED_IDLE_STATUS",
    "UndeclaredIdleRequest",
    "UndeclaredIdleResult",
    "apply_undeclared_idle_attention",
]

UNDECLARED_IDLE_CONDITION = "undeclared-idle"
UNDECLARED_IDLE_STATUS = "undeclared-idle"
# The one row status this monitor promotes from. See the module docstring: it already
# means "idle above threshold with no session declaration".
UNDECLARED_IDLE_SOURCE_STATUS = "idle-with-context-left"


@dataclass(frozen=True, kw_only=True)
class UndeclaredIdleResult:
    status: str
    note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class UndeclaredIdleRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    status: str
    note: str | None
    obs: Observation
    active_conditions: set[str]
    act: bool


def _unchanged(*, request: UndeclaredIdleRequest) -> UndeclaredIdleResult:
    return UndeclaredIdleResult(
        status=request.status,
        note=request.note,
        active_conditions=set(request.active_conditions),
    )


def _note(*, age: float) -> str:
    bound = _supervisor_liveness.age_label(
        seconds=_supervisor_config.UNDECLARED_IDLE_REPORTED_UNTIL
    )
    return (
        f"undeclared {_supervisor_liveness.age_label(seconds=age)}: idle above threshold "
        "with no ready, blocked or winding-down declaration; report-only, reported until "
        f"{bound}"
    )


def _surface(*, request: UndeclaredIdleRequest) -> None:
    """Alert once for the episode, keyed on the FIXED floor rather than the live age.

    An alert re-emits when its own TEXT changes, so quoting the growing streak age here
    would re-alert on every tick and bury the daemon log's history under identical
    lines — the failure invariant 10 records. The floor is fixed; the streak age rides
    the row note, which the table re-renders anyway.
    """
    floor = _supervisor_liveness.age_label(seconds=_supervisor_config.UNDECLARED_IDLE_AFTER)
    request.sup.alert(
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
        pane=request.pane,
        message=(
            f"undeclared idle ({floor}): idle above threshold and the session has "
            "declared neither ready, blocked nor winding-down, so the daemon cannot "
            "tell a pending human decision from an empty queue - inspect that pane; "
            "report-only, no restart authorized; current streak age is in the row note"
        ),
        condition=UNDECLARED_IDLE_CONDITION,
    )


def apply_undeclared_idle_attention(*, request: UndeclaredIdleRequest) -> UndeclaredIdleResult:
    condition_now = request.status == UNDECLARED_IDLE_SOURCE_STATUS
    _supervisor_observe.advance_condition(
        episode=request.obs.istate.undeclared_idle_episode,
        condition_now=condition_now,
        now=request.obs.observed_at,
    )
    since = request.obs.istate.undeclared_idle_episode.since
    if not condition_now or since is None:
        return _unchanged(request=request)

    age = max(0.0, request.obs.observed_at - since)
    if age < _supervisor_config.UNDECLARED_IDLE_AFTER:
        return _unchanged(request=request)
    if age > _supervisor_config.UNDECLARED_IDLE_REPORTED_UNTIL:
        # THE BOUND. The episode clock keeps running — it is only reset by the session
        # going non-idle or declaring — so past this age the condition can never raise
        # again within this episode. That is the whole point: a report that stands
        # forever is a shield, not a signal, and this subject already carries two of
        # those. The alert emitted at the floor remains in the daemon log as history.
        return _unchanged(request=request)

    note = _supervisor_liveness.append_note(note=request.note, extra=_note(age=age))
    if request.act:
        _surface(request=request)
    return UndeclaredIdleResult(
        status=UNDECLARED_IDLE_STATUS,
        note=note,
        active_conditions={*request.active_conditions, UNDECLARED_IDLE_CONDITION},
    )
