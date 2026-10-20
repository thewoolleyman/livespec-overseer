"""Retire a durable Herdr replacement whose recorded server generation is gone.

A replacement binds the exact herdr server generation it acts on. When that server
dies — a host power-off, a crash — every process the record names goes with it, so no
later observation can satisfy or refute the record, and it refused its track as
`replacement-failed` on every tick, forever (overseer-nztq44, measured live
2026-10-20). Such a record can do no further harm: nothing it names can be signalled,
launched into or pasted into again. An acting tick therefore RETIRES it, keeping the
whole record as a diagnostic file beside it and voiding the predecessor's own `ready`
so it can never authorize anything, and the track then takes its ordinary
classification.

The generation must be PROVABLY gone — its server pid no longer runs with the
recorded start time — exactly the proof server-restart re-adoption takes
(overseer-rwrkkr). A generation that still runs keeps refusing, as does a malformed or
contended record.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, cast

import _herdr_replacement_store
import _supervisor_launch
import _supervisor_state
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["RETIRED_CONDITION", "retire_dead_generation"]

RETIRED_CONDITION = "herdr-replacement-retired"


def _dead_generation(*, sup: Supervisor, transaction: Mapping[str, object]) -> str | None:
    """The recorded `pid/starttime` when that server generation provably no longer runs."""
    server = cast(dict[str, object], transaction["server"])
    pid = cast(int, server["pid"])
    starttime = cast(str, server["starttime"])
    if sup.starttime_of(pid=pid) == starttime:
        return None
    return f"{pid}/{starttime}"


def _void_own_ready(
    *, sup: Supervisor, track: registry.Track, transaction: Mapping[str, object]
) -> bool:
    """Replace the predecessor's own `ready` with a diagnostic; True when none remains."""
    state = signals.read_state(repo=track.repo, topic=track.topic)
    recorded_round = cast(dict[str, object], transaction["round"])
    if (
        state is None
        or state.token != signals.STATE_READY
        or state.mtime != recorded_round["ready_mtime"]
    ):
        return True
    return _supervisor_state.clear_state(
        sup=sup,
        track=track,
        diagnostic_token=signals.STATE_READY_EXPIRED,
        diagnostic_detail="retired with its Herdr replacement on a dead server generation",
        preserve_round_on_failure=True,
    )


def _retire_locked(
    *, sup: Supervisor, track: registry.Track, scratch: Path
) -> tuple[str, Path] | None:
    record = scratch / _herdr_replacement_store.RECORD_NAME
    transaction = _herdr_replacement_store.read_transaction(path=record)
    if transaction is None or transaction.get("phase") == "completed":
        return None
    generation = _dead_generation(sup=sup, transaction=transaction)
    if generation is None or not _void_own_ready(sup=sup, track=track, transaction=transaction):
        return None
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(sup.now()))
    retired = scratch / f".herdr-replacement.retired-{stamp}.json"
    _ = record.replace(retired)
    return generation, retired


def retire_dead_generation(*, sup: Supervisor, track: registry.Track, target: str) -> bool:
    """Retire this track's unfinished replacement when its server generation is gone."""
    scratch = _herdr_replacement_store.scratch_path(track=track)
    if not (scratch / _herdr_replacement_store.RECORD_NAME).exists():
        return False
    try:
        with _herdr_replacement_store.transaction_lock(
            path=scratch / _herdr_replacement_store.LOCK_NAME
        ):
            retired = _retire_locked(sup=sup, track=track, scratch=scratch)
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        return False
    if retired is None:
        return False
    generation, path = retired
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=_supervisor_launch.session_of(sup=sup, track=track),
        pane=target,
        message=(
            f"retired the unfinished Herdr replacement recorded on dead server generation "
            f"{generation}; record kept at {path.name}"
        ),
        condition=RETIRED_CONDITION,
    )
    return True
