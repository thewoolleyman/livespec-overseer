"""Launch-statusline baseline storage must not fabricate round records."""

from __future__ import annotations

import json
from pathlib import Path

import _supervisor_ready_fresh
import registry
import signals
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _key(*, repo: str, topic: str) -> str:
    return f"{registry.norm(repo=repo)}\t{topic}"


def _read_sidecar(*, path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_none_launch_statusline_baseline_does_not_create_round_record(*, tmp_path: Path) -> None:
    stamp = tmp_path / "stamps.json"
    repo = str(tmp_path / "repo")
    topic = "topic"

    registry.record_launch_statusline_baseline(
        repo=repo,
        topic=topic,
        model=None,
        stamp_path=stamp,
    )

    assert _key(repo=repo, topic=topic) not in _read_sidecar(path=stamp)
    record = registry.read_round_record(repo=repo, topic=topic, stamp_path=stamp)
    assert record.at is None
    assert record.malformed_reason is None


def test_launch_statusline_baseline_string_round_trips(*, tmp_path: Path) -> None:
    stamp = tmp_path / "stamps.json"
    repo = str(tmp_path / "repo")
    topic = "topic"

    registry.record_launch_statusline_baseline(
        repo=repo,
        topic=topic,
        model="claude-sonnet-4-20250514",
        stamp_path=stamp,
    )

    assert (
        registry.read_launch_statusline_baseline(repo=repo, topic=topic, stamp_path=stamp)
        == "claude-sonnet-4-20250514"
    )


def test_none_launch_statusline_baseline_preserves_existing_round_record(*, tmp_path: Path) -> None:
    stamp = tmp_path / "stamps.json"
    repo = str(tmp_path / "repo")
    topic = "topic"
    registry.write_injection_stamp(
        repo=repo,
        topic=topic,
        ts=1234.5,
        session_identity="claude:session:topic",
        stamp_path=stamp,
    )
    registry.add_notified_band(repo=repo, topic=topic, band=45, stamp_path=stamp)
    before = _read_sidecar(path=stamp)

    registry.record_launch_statusline_baseline(
        repo=repo,
        topic=topic,
        model=None,
        stamp_path=stamp,
    )

    assert _read_sidecar(path=stamp) == before


def test_launch_only_sidecar_entry_allows_fresh_ready_without_round(*, tmp_path: Path) -> None:
    stamp = tmp_path / "stamps.json"
    repo = str(tmp_path / "repo")
    topic = "topic"
    stamp.write_text(
        json.dumps({_key(repo=repo, topic=topic): {"launch_statusline_model": None}}),
        encoding="utf-8",
    )
    record = registry.read_round_record(repo=repo, topic=topic, stamp_path=stamp)

    assert record.at is None
    assert record.malformed_reason is None
    assert _supervisor_ready_fresh.fresh_ready_without_round_candidate(
        declared=signals.TrackState(token=signals.STATE_READY, detail="", mtime=1001.0),
        round_record=record,
        session_identity="claude:session:topic",
        history=_supervisor_ready_fresh.ObservationHistory(
            mapped=True,
            session_identity="claude:session:topic",
            added_at="2026-08-16T23:45:00Z",
        ),
    )


def test_unreadable_launch_statusline_still_allows_fresh_ready_without_round(
    *, tmp_path: Path
) -> None:
    stamp = tmp_path / "stamps.json"
    repo = str(tmp_path / "repo")
    topic = "topic"
    registry.record_launch_statusline_baseline(
        repo=repo,
        topic=topic,
        model=None,
        stamp_path=stamp,
    )
    record = registry.read_round_record(repo=repo, topic=topic, stamp_path=stamp)

    assert _supervisor_ready_fresh.fresh_ready_without_round_candidate(
        declared=signals.TrackState(token=signals.STATE_READY, detail="", mtime=1001.0),
        round_record=record,
        session_identity="claude:session:topic",
        history=_supervisor_ready_fresh.ObservationHistory(
            mapped=True,
            session_identity="claude:session:topic",
            added_at="2026-08-16T23:45:00Z",
        ),
    )


def test_malformed_round_record_still_refuses_fresh_ready_candidate(*, tmp_path: Path) -> None:
    stamp = tmp_path / "stamps.json"
    repo = str(tmp_path / "repo")
    topic = "topic"
    stamp.write_text(
        json.dumps({_key(repo=repo, topic=topic): {"at": "later"}}),
        encoding="utf-8",
    )
    record = registry.read_round_record(repo=repo, topic=topic, stamp_path=stamp)

    assert record.malformed_reason == "missing or non-numeric injection stamp"
    assert not _supervisor_ready_fresh.fresh_ready_without_round_candidate(
        declared=signals.TrackState(token=signals.STATE_READY, detail="", mtime=1001.0),
        round_record=record,
        session_identity="claude:session:topic",
        history=_supervisor_ready_fresh.ObservationHistory(
            mapped=True,
            session_identity="claude:session:topic",
            added_at="2026-08-16T23:45:00Z",
        ),
    )


def test_malformed_round_note_names_non_numeric_injection_stamp(*, tmp_path: Path) -> None:
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    stamp_path = Path(sup.stamp_path)
    stamp_path.write_text(
        json.dumps({_key(repo=str(repo), topic=topic): {"at": "later", "bands": []}}),
        encoding="utf-8",
    )
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1.0)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "ready-uncertifiable"
    assert view.note is not None
    assert "ready cannot certify: missing or non-numeric injection stamp" in view.note
    assert "no supervision round open" not in view.note
