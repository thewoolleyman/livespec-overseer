"""Beside-tests for v010 round certification-floor sidecar parsing."""

from __future__ import annotations

import json

import registry

__all__: list[str] = []


def _key(*, repo: str, topic: str) -> str:
    return f"{repo}\t{topic}"


def test_round_record_absent_when_sidecar_missing(*, tmp_path):
    record = registry.read_round_record(
        repo=str(tmp_path / "repo"), topic="topic", stamp_path=tmp_path / "missing.json"
    )
    assert record.at is None
    assert record.certification_floor is None
    assert record.malformed_reason is None


def test_round_record_warns_and_fails_closed_for_unreadable_sidecar(*, tmp_path, capsys):
    path = tmp_path / "stamps.json"
    path.write_text("{not-json", encoding="utf-8")

    record = registry.read_round_record(repo="repo", topic="topic", stamp_path=path)

    assert record.at is None
    assert "unreadable injection-stamp sidecar" in capsys.readouterr().err


def test_round_record_warns_and_fails_closed_for_non_object_sidecar(*, tmp_path, capsys):
    path = tmp_path / "stamps.json"
    path.write_text("[]", encoding="utf-8")

    record = registry.read_round_record(repo="repo", topic="topic", stamp_path=path)

    assert record.at is None
    assert "is not a JSON object" in capsys.readouterr().err


def test_round_record_accepts_legacy_numeric_stamp_but_marks_identity_missing(*, tmp_path):
    path = tmp_path / "stamps.json"
    path.write_text(json.dumps({_key(repo="repo", topic="topic"): 1000.0}), encoding="utf-8")

    record = registry.read_round_record(repo="repo", topic="topic", stamp_path=path)

    assert record.at == 1000.0
    assert record.session_identity is None
    assert record.malformed_reason == "round record missing session identity"


def test_round_record_marks_non_numeric_legacy_stamp_malformed(*, tmp_path, capsys):
    path = tmp_path / "stamps.json"
    path.write_text(json.dumps({_key(repo="repo", topic="topic"): "later"}), encoding="utf-8")

    record = registry.read_round_record(repo="repo", topic="topic", stamp_path=path)

    assert record.at is None
    assert record.malformed_reason == "non-numeric injection stamp"
    assert "non-numeric injection stamp" in capsys.readouterr().err


def test_round_record_names_each_dict_malformed_reason(*, tmp_path):
    path = tmp_path / "stamps.json"
    key = _key(repo="repo", topic="topic")
    path.write_text(json.dumps({key: {"session_identity": "claude:s:t"}}), encoding="utf-8")
    assert (
        registry.read_round_record(repo="repo", topic="topic", stamp_path=path).malformed_reason
        == "missing or non-numeric injection stamp"
    )

    path.write_text(
        json.dumps({key: {"at": 1000.0, "expired_at": "bad", "session_identity": "claude:s:t"}}),
        encoding="utf-8",
    )
    assert (
        registry.read_round_record(repo="repo", topic="topic", stamp_path=path).malformed_reason
        == "non-numeric expiry instant"
    )

    path.write_text(json.dumps({key: {"at": 1000.0}}), encoding="utf-8")
    assert (
        registry.read_round_record(repo="repo", topic="topic", stamp_path=path).malformed_reason
        == "round record missing session identity"
    )


def test_read_round_open_identity_and_missing_expiry_record(*, tmp_path):
    path = tmp_path / "stamps.json"
    registry.write_injection_stamp(
        repo="repo",
        topic="topic",
        ts=1000.0,
        session_identity="claude:s:t",
        stamp_path=path,
    )

    assert (
        registry.read_round_open_identity(repo="repo", topic="topic", stamp_path=path)
        == "claude:s:t"
    )
    assert (
        registry.record_ready_expiry(
            repo="repo", topic="other", expiry_instant=1200.0, stamp_path=path
        )
        is False
    )
