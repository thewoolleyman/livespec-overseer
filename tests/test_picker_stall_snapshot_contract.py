"""Regression tests for picker-stall status snapshot fields."""

from types import SimpleNamespace

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


def test_snapshot_row_falls_back_when_provenance_reader_is_malformed():
    def malformed_reader(*, session):
        return "not-a-record"

    sup = SimpleNamespace(tmux=SimpleNamespace(input_provenance_status=malformed_reader))

    row = supervisor.RowView(
        topic="resume-submit-integrity-supervisor",
        repo="/repo",
        tmux="resume-submit-integrity-supervisor",
        runtime="claude",
        ctx=80,
        status="blocked:human",
    )

    payload = _supervisor_snapshot.row_payload(sup=sup, row=row)

    assert payload["latest_input_provenance"] == {
        "peer_injected": False,
        "target_session": "resume-submit-integrity-supervisor",
    }
