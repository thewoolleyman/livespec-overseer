"""Tests for the file-backed peer-input provenance store."""

from __future__ import annotations

import json

import input_provenance

__all__: list[str] = []


def test_latest_is_negative_when_file_is_missing_or_malformed(*, tmp_path):
    path = tmp_path / "input-provenance.json"

    assert input_provenance.latest(path=path, session="worker") == {
        "peer_injected": False,
        "target_session": "worker",
    }

    path.write_text("{not json", encoding="utf-8")
    assert input_provenance.latest(path=path, session="worker") == {
        "peer_injected": False,
        "target_session": "worker",
    }

    path.write_text("[]", encoding="utf-8")
    assert input_provenance.latest(path=path, session="worker") == {
        "peer_injected": False,
        "target_session": "worker",
    }


def test_record_peer_filters_malformed_rows_and_clear_removes_only_target(*, tmp_path):
    path = tmp_path / "input-provenance.json"
    path.write_text(
        json.dumps(
            {
                "other": {
                    "peer_injected": True,
                    "target_session": "other",
                },
                "bad": "not-a-record",
                4: {
                    "peer_injected": True,
                },
            }
        ),
        encoding="utf-8",
    )

    input_provenance.record_peer(path=path, session="worker", sending_seat="foreman")
    worker = input_provenance.latest(path=path, session="worker")
    assert worker == {
        "peer_injected": True,
        "sending_seat": "foreman",
        "target_session": "worker",
        "delivery": "bracketed-paste",
        "recorded_at": worker["recorded_at"],
    }
    assert input_provenance.latest(path=path, session="other") == {
        "peer_injected": True,
        "target_session": "other",
    }

    input_provenance.clear(path=path, session="worker")

    assert input_provenance.latest(path=path, session="worker") == {
        "peer_injected": False,
        "target_session": "worker",
    }
    assert input_provenance.status(path=path, session=None) == {
        "peer_injected": False,
        "target_session": None,
    }
    assert input_provenance.status(path=path, session="other") == {
        "peer_injected": True,
        "target_session": "other",
    }
    input_provenance.clear(path=path, session="absent")
    assert input_provenance.latest(path=path, session="other") == {
        "peer_injected": True,
        "target_session": "other",
    }


def test_record_peer_write_failure_is_fail_soft(*, tmp_path, capsys):
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("", encoding="utf-8")

    input_provenance.record_peer(
        path=parent_file / "input-provenance.json",
        session="worker",
        sending_seat="foreman",
    )

    assert "overseer.input_provenance: write failed:" in capsys.readouterr().err
