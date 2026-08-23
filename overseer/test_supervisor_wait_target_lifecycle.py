"""Beside-tests for wait-premise target lifecycle cleanup."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import registry
import wait_premises
from test_supervisor_builders import idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _write_premise(
    *,
    repo: Path,
    topic: str,
    target_id: str = "run-1",
    recheck_by: str = "2026-08-19T03:00:00Z",
    extra: dict[str, object] | None = None,
) -> None:
    fields = {
        "kind": "fabro-run",
        "target_id": target_id,
        "evidence_source": "fabro ps -a --json",
        "recorded_at": "2026-08-19T02:30:00Z",
        "recheck_by": recheck_by,
    }
    if extra is not None:
        fields.update({key: str(value) for key, value in extra.items()})
    _ = wait_premises.write_wait_premise(repo=repo, topic=topic, **fields)


def _write_local_runs(*, repo: Path, records: list[dict[str, object]]) -> None:
    path = repo / "tmp" / "overseer" / "fabro-ps-a.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records) + "\n", encoding="utf-8")


def _write_journal(*, repo: Path, records: list[dict[str, object]]) -> None:
    path = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _served_track(*, tmp_path: Path, now: Callable[[], float] | None = None):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=90))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    if now is not None:
        sup.now = now
    track = mapped_track(repo=repo, topic=topic, session=session)
    return repo, topic, sup, track


def _evidence_statuses(*, repo: Path, topic: str) -> list[str]:
    paths = sorted((repo / "tmp" / "overseer" / topic).glob("wait-target-missing-*.json"))
    return [str(json.loads(path.read_text(encoding="utf-8"))["status"]) for path in paths]


def test_satisfied_wait_premise_stops_reporting_and_leaves_evidence_record(*, tmp_path):
    repo, topic, sup, track = _served_track(tmp_path=tmp_path)
    _write_premise(
        repo=repo,
        topic=topic,
        target_id="remote-run",
        extra={
            "execution_location": "remote",
            "dispatch_factory": "hp",
            "work_item_id": "overseer-x",
            "publish_branch": "feat/overseer-x",
        },
    )
    _write_local_runs(repo=repo, records=[])
    _write_journal(
        repo=repo,
        records=[
            {
                "stage": "dispatch-id",
                "work_item_id": "overseer-x",
                "dispatch_id": "remote-run",
                "at": "2026-08-19T02:31:00Z",
            },
            {
                "stage": "outcome",
                "outcome": {
                    "dispatch_id": "remote-run",
                    "work_item_id": "overseer-x",
                    "status": "succeeded",
                },
                "at": "2026-08-19T02:41:00Z",
            },
        ],
    )

    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"

    premise_dir = repo / "tmp" / "overseer" / topic / "wait-premises"
    assert list(premise_dir.glob("*.json")) == []
    assert _evidence_statuses(repo=repo, topic=topic) == ["satisfied"]


def test_expired_wait_premise_stops_reporting_only_after_row_stops_waiting(*, tmp_path):
    repo, topic, sup, track = _served_track(tmp_path=tmp_path)
    _write_premise(repo=repo, topic=topic, recheck_by="2026-08-19T03:00:00Z")
    _write_local_runs(repo=repo, records=[])
    sup.now = lambda: 1_787_500_800.0

    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"

    premise_dir = repo / "tmp" / "overseer" / topic / "wait-premises"
    assert list(premise_dir.glob("*.json")) == []
    assert _evidence_statuses(repo=repo, topic=topic) == ["expired"]


def test_still_valid_wait_premise_is_not_removed_and_keeps_reporting(*, tmp_path):
    repo, topic, sup, track = _served_track(tmp_path=tmp_path)
    _write_premise(repo=repo, topic=topic, recheck_by="2026-08-19T03:00:00Z")
    _write_local_runs(repo=repo, records=[])
    sup.now = lambda: 1_787_000_800.0

    view = sup.evaluate(track=track, act=True)

    premise_dir = repo / "tmp" / "overseer" / topic / "wait-premises"
    assert view.status == "wait-target-missing"
    assert len(list(premise_dir.glob("*.json"))) == 1
