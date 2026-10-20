"""Retiring a dead-generation replacement voids ONLY its predecessor's own `ready`.

The retirement (overseer-nztq44) may replace exactly the declaration that authorized
the retired replacement. A later declaration the track wrote for itself is not that
one, and it survives the retirement untouched.
"""

from __future__ import annotations

import os
from pathlib import Path

import _herdr_replacement_store
import _supervisor_herdr_stall
import signals
from test_herdr_dead_generation_replacement import (
    _LIVE_PID,
    _READY_MTIME,
    _coordinate,
    _setup,
)

__all__: list[str] = []


def test_a_later_declaration_survives_the_retirement(*, tmp_path: Path) -> None:
    sup, track, scratch = _setup(tmp_path=tmp_path, running={_LIVE_PID: f"start-{_LIVE_PID}"})
    state = signals.state_path(repo=track.repo, topic=track.topic)
    _ = state.write_text("blocked: waiting on the maintainer\n", encoding="utf-8")
    os.utime(state, (_READY_MTIME + 60.0, _READY_MTIME + 60.0))

    _ = _supervisor_herdr_stall.reconcile_and_alert(
        sup=sup, track=track, target=_coordinate(pid=_LIVE_PID), act=True, alert=True
    )

    assert not (scratch / _herdr_replacement_store.RECORD_NAME).exists()
    after = signals.read_state(repo=track.repo, topic=track.topic)
    assert after is not None
    assert (after.token, after.detail) == (signals.STATE_BLOCKED, "waiting on the maintainer")
