"""Peer-input provenance tests for the tmux write boundary."""

from __future__ import annotations

from test_tmuxio_fakes import io as _io

__all__: list[str] = []


def test_peer_bracketed_paste_records_input_provenance():
    tmux, fake = _io()
    assert (
        tmux.peer_bracketed_paste(
            session="worker-pane",
            text="1",
            sending_seat="livespec-overseer-foreman",
        )
        is True
    )

    assert tmux.latest_input_provenance(session="worker-pane") == {
        "peer_injected": True,
        "sending_seat": "livespec-overseer-foreman",
        "target_session": "worker-pane",
        "delivery": "bracketed-paste",
    }
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


def test_plain_bracketed_paste_does_not_report_peer_injection():
    tmux, _ = _io()
    assert tmux.bracketed_paste(session="worker-pane", text="maintainer answer") is True
    assert tmux.latest_input_provenance(session="worker-pane") == {
        "peer_injected": False,
        "target_session": "worker-pane",
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
