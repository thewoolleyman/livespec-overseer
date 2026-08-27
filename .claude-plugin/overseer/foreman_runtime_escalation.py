"""Foreman runtime writes for non-blocking human-decision escalation."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from _supervisor_foreman_escalation import escalation_path
from foreman_plan_roster import active_plan_names
from foreman_runtime_identity import canonical_session_name
from foreman_runtime_state import atomic_json
from foreman_wait_publication import (
    PICKER_OPEN,
    WaitPublisher,
    WaitState,
    publish_wait_state,
)

__all__: list[str] = [
    "WAIT_PUBLISHER",
    "foreman_session_identity",
    "record_blocking_prompt_escalation",
]

_BLOCKING_PROMPT_REASON = (
    "foreman tick ended with a blocking prompt; the decision must stay on "
    "the non-blocking attention surface so the loop cadence can continue"
)
# The declared seam for the wait publication below. It is a module binding
# rather than a parameter because two of the three raise sites are already at
# the argument ceiling, and a seam that is threaded at only one of the three is
# worse than one shape used at all of them. Read at CALL time, so redirecting it
# on THIS module — the one that reads it — is what takes effect.
WAIT_PUBLISHER: WaitPublisher = publish_wait_state


def record_blocking_prompt_escalation(*, repo: Path, session_identity: str | None = None) -> None:
    topic = canonical_session_name(repo=repo)
    payload: dict[str, object] = {"reason": _BLOCKING_PROMPT_REASON}
    if session_identity is not None:
        payload["session_identity"] = session_identity
    atomic_json(
        path=escalation_path(repo=str(repo), topic=topic),
        payload=payload,
    )
    # The private record above is written FIRST so an unreachable ledger can
    # never cost the escalation itself; the publication is what makes the wait
    # readable without opening the foreman's own pane.
    #
    # PUBLISHED PER GOVERNED PLAN, and the alternative is a no-op. A picker the
    # foreman raises is raised in the foreman's OWN pane, and the loop it parks
    # is the whole per-repo loop — so unlike a convene escalation or a panel,
    # which each carry the plan they were raised for, this wait has no single
    # owning plan. Keying it on `topic` — the foreman's session name — reads as
    # the obvious answer and is the one key that CANNOT resolve: `plan_slug`
    # carries a PLAN's slug, no ledger epic in any tenant carries the foreman
    # session name, so the publication resolved to nothing and the wait reached
    # no epic at all. Every plan the loop governs is waiting on this picker, and
    # every one of those plans has an epic, so each of them is told.
    #
    # `active_plan_names` enumerates `plan/*/` DIRECTORIES and derives no path
    # into one, which is the same read the daemon's own discovery performs; the
    # prohibition on writing under `plan/` is untouched.
    for plan in active_plan_names(repo=repo):
        _ = WAIT_PUBLISHER(
            repo=repo,
            wait=WaitState(kind=PICKER_OPEN, plan=plan, detail=_BLOCKING_PROMPT_REASON),
        )


def foreman_session_identity(*, payload: dict[str, object], repo: Path) -> str | None:
    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, Mapping):
        return None
    rows = cast("Mapping[str, object]", snapshot).get("rows")
    if not isinstance(rows, list):
        return None
    typed_rows = cast("list[object]", rows)
    topic = canonical_session_name(repo=repo)
    for row in typed_rows:
        if not isinstance(row, Mapping):
            continue
        typed_row = cast("Mapping[str, object]", row)
        if typed_row.get("topic") != topic:
            continue
        identity = typed_row.get("session_identity")
        if isinstance(identity, str) and identity.strip():
            return identity.strip()
    return None
