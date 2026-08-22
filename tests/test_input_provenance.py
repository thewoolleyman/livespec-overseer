"""Peer-input provenance tests for the tmux write boundary."""

from __future__ import annotations

import tmuxio
from test_tmuxio_fakes import FakeRun
from test_tmuxio_fakes import io as _io

__all__: list[str] = []


def test_peer_bracketed_paste_records_input_provenance(*, tmp_path):
    provenance_path = tmp_path / "input-provenance.json"
    fake = FakeRun()
    tmux = tmuxio.TmuxIO(run=fake, input_provenance_path=provenance_path)
    assert (
        tmux.peer_bracketed_paste(
            session="worker-pane",
            text="1",
            sending_seat="livespec-overseer-foreman",
        )
        is True
    )

    reader = tmuxio.TmuxIO(run=FakeRun(), input_provenance_path=provenance_path)
    provenance = reader.latest_input_provenance(session="worker-pane")
    assert provenance == {
        "peer_injected": True,
        "sending_seat": "livespec-overseer-foreman",
        "target_session": "worker-pane",
        "delivery": "bracketed-paste",
        "recorded_at": provenance["recorded_at"],
    }
    assert isinstance(provenance["recorded_at"], str)
    assert fake.calls[1]["argv"] == [
        "tmux",
        "paste-buffer",
        "-b",
        fake.calls[0]["argv"][3],
        "-p",
        "-d",
        "-t",
        "worker-pane",
    ]


def test_plain_bracketed_paste_does_not_report_peer_injection(*, tmp_path):
    provenance_path = tmp_path / "input-provenance.json"
    tmux = tmuxio.TmuxIO(run=FakeRun(), input_provenance_path=provenance_path)
    assert (
        tmux.peer_bracketed_paste(
            session="worker-pane",
            text="1",
            sending_seat="livespec-overseer-foreman",
        )
        is True
    )
    assert tmux.bracketed_paste(session="worker-pane", text="maintainer answer") is True

    reader = tmuxio.TmuxIO(run=FakeRun(), input_provenance_path=provenance_path)
    assert reader.latest_input_provenance(session="worker-pane") == {
        "peer_injected": False,
        "target_session": "worker-pane",
    }
    assert reader.input_provenance_status(session=None) == {
        "peer_injected": False,
        "target_session": None,
    }


def test_peer_answering_stalled_picker_still_pastes_and_submits():
    tmux, fake = _io()
    assert (
        tmux.peer_bracketed_paste(
            session="stalled-picker",
            text="1",
            sending_seat="livespec-overseer-foreman",
        )
        is True
    )
    assert tmux.send_keys(session="stalled-picker", keys="Enter") is True

    assert [call["argv"][1] for call in fake.calls] == [
        "load-buffer",
        "paste-buffer",
        "send-keys",
    ]
    assert tmux.latest_input_provenance(session="stalled-picker")["sending_seat"] == (
        "livespec-overseer-foreman"
    )
