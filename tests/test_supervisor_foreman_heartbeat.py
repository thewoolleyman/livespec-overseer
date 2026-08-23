"""Regression tests for the daemon's foreman heartbeat attention row."""

import json
from datetime import datetime, timezone

from overseer import _supervisor_foreman as foreman
from overseer import foreman_stop_state
from overseer._supervisor_view import needs_attention

__all__: list[str] = []


def _write_heartbeat(*, repo, written_at: int, interval: float = 60.0) -> None:
    path = foreman.heartbeat_path(repo=str(repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "written_at": datetime.fromtimestamp(written_at, tz=timezone.utc).isoformat(),
                "pid": 1234,
                "tick_generation": 7,
                "tick_interval_seconds": interval,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_dead_foreman_heartbeat_escalates_and_names_restore_path(*, tmp_path):
    _write_heartbeat(repo=tmp_path, written_at=0)

    stale = foreman.foreman_row(repo=str(tmp_path), now=lambda: (31 * 60))
    escalated = foreman.foreman_row(repo=str(tmp_path), now=lambda: (91 * 60))

    assert stale is not None
    assert stale.status == foreman.FOREMAN_HEARTBEAT_STALE_STATUS
    assert escalated is not None
    assert escalated.status == foreman.FOREMAN_HEARTBEAT_DEAD_STATUS
    assert needs_attention(row=escalated) is True
    assert "foreman-runtime --resume" in (escalated.note or "")
    assert "re-arm the hourly schedule" in (escalated.note or "")


def test_held_foreman_heartbeat_keeps_non_attention_status(*, tmp_path):
    _write_heartbeat(repo=tmp_path, written_at=0)
    hold = foreman_stop_state.foreman_hold_path(repo=tmp_path)
    hold.parent.mkdir(parents=True, exist_ok=True)
    hold.write_text("maintenance window\n", encoding="utf-8")

    row = foreman.foreman_row(repo=str(tmp_path), now=lambda: (91 * 60))

    assert row is not None
    assert row.status == foreman.FOREMAN_HEARTBEAT_HELD_STATUS
    assert needs_attention(row=row) is False
