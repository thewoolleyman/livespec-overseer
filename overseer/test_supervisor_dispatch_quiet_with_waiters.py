"""Beside-tests for aggregate dispatch-quiet-with-waiters attention."""

from __future__ import annotations

import json
from pathlib import Path

import _supervisor_dispatch_quiet as dispatch_quiet
import _supervisor_tick
import registry
from _supervisor_view import RowView
from test_supervisor_builders import idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _write_premise(
    *,
    repo: Path,
    topic: str,
    target_id: str,
    extra: dict[str, object] | None = None,
) -> None:
    directory = repo / "tmp" / "overseer" / topic / "wait-premises"
    directory.mkdir(parents=True)
    payload = {
        "schema_version": 1,
        "kind": "fabro-run",
        "target_id": target_id,
        "evidence_source": "fabro ps -a --json",
        "recorded_at": "2026-08-19T02:30:00Z",
        "recheck_by": "2026-08-19T03:00:00Z",
    }
    if extra is not None:
        payload.update(extra)
    _ = (directory / f"{target_id}.json").write_text(
        json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_local_runs(*, repo: Path, records: list[dict[str, object]]) -> None:
    path = repo / "tmp" / "overseer" / "fabro-ps-a.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(records) + "\n", encoding="utf-8")


def _write_journal(*, repo: Path, records: list[dict[str, object]]) -> None:
    path = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _served_tracks(*, tmp_path: Path, count: int):
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    tracks: list[registry.Track] = []
    repos: list[Path] = []
    topics: list[str] = []
    for index in range(count):
        repo, topic = make_plan(tmp_path=tmp_path, topic=f"dispatch-wait-{index}")
        session = registry.tmux_id(repo=str(repo), topic=topic)
        fake.serve(session=session, repo=repo, capture=idle_capture(ctx=90))
        tracks.append(mapped_track(repo=repo, topic=topic, session=session))
        repos.append(repo)
        topics.append(topic)
    return fake, sup, tracks, repos, topics


def _statuses(*, rows):
    return [row.status for row in rows]


def test_two_failed_wait_premises_raise_one_fleet_level_attention_row(*, tmp_path):
    _fake, sup, tracks, repos, topics = _served_tracks(tmp_path=tmp_path, count=2)
    sup.build_rows = lambda *, act: tracks
    for index, (repo, topic) in enumerate(zip(repos, topics, strict=True)):
        _write_premise(repo=repo, topic=topic, target_id=f"run-{index}")
        _write_local_runs(repo=repo, records=[])

    rows = _supervisor_tick.run_tick(sup=sup, act=True)

    statuses = _statuses(rows=rows)
    assert statuses.count("wait-target-missing") == 2
    assert statuses.count("dispatch-quiet-with-waiters") == 1
    aggregate = next(row for row in rows if row.status == "dispatch-quiet-with-waiters")
    assert aggregate.tmux is None
    assert aggregate.topic == "fleet"
    assert aggregate.note is not None
    assert "failed premise verification" in aggregate.note
    assert "dispatch-wait-0: run-0" in aggregate.note
    assert "dispatch-wait-1: run-1" in aggregate.note


def test_aggregate_clears_when_any_premise_reverifies(*, tmp_path):
    now = 1_000.0
    _fake, sup, tracks, repos, topics = _served_tracks(tmp_path=tmp_path, count=2)
    sup.now = lambda: now
    sup.build_rows = lambda *, act: tracks
    for index, (repo, topic) in enumerate(zip(repos, topics, strict=True)):
        _write_premise(repo=repo, topic=topic, target_id=f"run-{index}")
        _write_local_runs(repo=repo, records=[])

    assert "dispatch-quiet-with-waiters" in _statuses(
        rows=_supervisor_tick.run_tick(sup=sup, act=True)
    )
    _write_local_runs(repo=repos[0], records=[{"id": "run-0", "status": "running"}])
    now += 1.0
    rows = _supervisor_tick.run_tick(sup=sup, act=True)

    assert _statuses(rows=rows).count("wait-target-missing") == 1
    assert "dispatch-quiet-with-waiters" not in _statuses(rows=rows)


def test_remote_delivery_suppresses_aggregate_even_when_local_process_set_is_empty(*, tmp_path):
    _fake, sup, tracks, repos, topics = _served_tracks(tmp_path=tmp_path, count=2)
    sup.build_rows = lambda *, act: tracks
    journal_records: list[dict[str, object]] = []
    for index, (repo, topic) in enumerate(zip(repos, topics, strict=True)):
        run_id = f"remote-run-{index}"
        work_item_id = f"overseer-x{index}"
        _write_premise(
            repo=repo,
            topic=topic,
            target_id=run_id,
            extra={
                "execution_location": "remote",
                "dispatch_factory": "hp",
                "evidence_source": "fabro dispatch journal factory=hp",
                "work_item_id": work_item_id,
                "publish_branch": f"feat/{work_item_id}",
            },
        )
        _write_local_runs(repo=repo, records=[])
        journal_records.extend(
            [
                {
                    "stage": "dispatch-id",
                    "work_item_id": work_item_id,
                    "dispatch_id": run_id,
                    "at": "2026-08-19T02:31:00Z",
                },
                {
                    "stage": "outcome",
                    "outcome": {
                        "work_item_id": work_item_id,
                        "dispatch_id": run_id,
                        "status": "succeeded",
                    },
                    "at": "2026-08-19T02:41:00Z",
                },
            ]
        )
    _write_journal(repo=repos[0], records=journal_records)

    rows = _supervisor_tick.run_tick(sup=sup, act=True)

    assert "wait-target-missing" not in _statuses(rows=rows)
    assert "dispatch-quiet-with-waiters" not in _statuses(rows=rows)


def test_dispatch_quiet_relay_templates_preserve_verbatim_evidence_slots():
    module_path = Path(__file__).resolve().parent / "_supervisor_dispatch_quiet.py"
    assert module_path.is_file()

    import _supervisor_dispatch_quiet as dispatch_quiet

    containment = dispatch_quiet.containment_relay_text(
        evidence="row alpha: run-1 failed\nrow beta: run-2 failed"
    )
    all_clear = dispatch_quiet.all_clear_relay_text(evidence="row alpha: run-1 verified delivered")

    assert "containment supersede-order" in containment
    assert "row alpha: run-1 failed\nrow beta: run-2 failed" in containment
    assert "hold re-dispatch" in containment
    assert "verify forge landings" in containment
    assert "continue non-dispatch work" in containment
    assert "authorizes no restart" in containment
    assert "dispatch-quiet-with-waiters all-clear" in all_clear
    assert "row alpha: run-1 verified delivered" in all_clear
    assert "authorizes no restart" in all_clear


def test_dispatch_quiet_ignores_missing_notes_and_labels_unparsed_evidence():
    rows = [
        RowView(
            topic="alpha",
            repo="/repo",
            tmux="alpha",
            ctx=90,
            status="wait-target-missing",
        ),
        RowView(
            topic="beta",
            repo="/repo",
            tmux="beta",
            ctx=90,
            status="wait-target-missing",
            note="target absent from every mandatory leg",
        ),
        RowView(
            topic="gamma",
            repo="/repo",
            tmux="gamma",
            ctx=90,
            status="wait-target-missing",
            note="target also absent from every mandatory leg",
        ),
    ]

    aggregate = dispatch_quiet.apply_dispatch_quiet_with_waiters(rows=rows)

    assert aggregate is not None
    assert aggregate.note is not None
    assert "alpha" not in aggregate.note
    assert "beta: unknown-target" in aggregate.note
    assert "gamma: unknown-target" in aggregate.note
