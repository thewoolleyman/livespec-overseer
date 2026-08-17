"""Regression tests for picker-stall status snapshot fields."""

import _supervisor_snapshot
import supervisor

__all__: list[str] = []


def test_snapshot_row_exports_picker_open_and_stall_seconds():
    row = supervisor.RowView(
        topic="resume-submit-integrity-supervisor",
        repo="/repo",
        tmux="resume-submit-integrity-supervisor",
        runtime="claude",
        ctx=80,
        status="blocked:human",
        picker_open=True,
        stall_seconds=185,
    )
    payload = _supervisor_snapshot.row_payload(sup=object(), row=row)

    assert payload["picker_open"] is True
    assert payload["stall_seconds"] == 185
