"""Beside-tests for wait-premise target re-verification attention."""

from __future__ import annotations

import contextlib
import io as _io
import json
from collections.abc import Callable
from pathlib import Path

import registry
from test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _write_premise(
    *,
    repo: Path,
    topic: str,
    target_id: str = "run-1",
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
    (directory / f"{target_id}.json").write_text(
        json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
    )


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
    return repo, topic, session, fake, sup, track


def test_local_wait_premise_absent_from_process_view_raises_attention(*, tmp_path):
    repo, topic, _session, fake, sup, track = _served_track(tmp_path=tmp_path)
    _write_premise(repo=repo, topic=topic)
    _write_local_runs(repo=repo, records=[])

    view = sup.evaluate(track=track, act=True)

    assert view.status == "wait-target-missing"
    assert view.note == "fabro-run run-1 absent from every mandatory leg"
    assert len(fake.paste_texts()) == 1
    assert ("respawn",) not in {call[:1] for call in fake.calls}


def test_remote_delivered_run_does_not_raise_when_local_process_view_is_empty(*, tmp_path):
    repo, topic, _session, _fake, sup, track = _served_track(tmp_path=tmp_path)
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
                    "work_item_id": "overseer-x",
                    "status": "succeeded",
                    "publish_branch": "feat/overseer-x",
                },
                "at": "2026-08-19T02:41:00Z",
            },
        ],
    )

    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"


def test_remote_delivered_run_with_deleted_branch_and_absent_journal_uses_forge(
    *, tmp_path, monkeypatch
):
    repo, topic, _session, _fake, sup, track = _served_track(tmp_path=tmp_path)
    _write_premise(
        repo=repo,
        topic=topic,
        target_id="remote-run",
        extra={
            "execution_location": "remote",
            "dispatch_factory": "hp",
            "publish_branch": "feat/overseer-x",
        },
    )
    _write_local_runs(repo=repo, records=[])
    _write_journal(repo=repo, records=[])
    monkeypatch.setattr(
        "_supervisor_wait_target_sources.forge_pull_request_present",
        lambda *, repo, branch: branch == "feat/overseer-x",
        raising=False,
    )

    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"


def test_local_terminal_run_state_raises_with_terminal_discriminator(*, tmp_path):
    repo, topic, _session, _fake, sup, track = _served_track(tmp_path=tmp_path)
    _write_premise(repo=repo, topic=topic)
    _write_local_runs(repo=repo, records=[{"id": "run-1", "status": "failed"}])

    view = sup.evaluate(track=track, act=True)

    assert view.status == "wait-target-missing"
    assert view.note == "fabro-run run-1 present with terminal state failed"


def test_wait_target_missing_alert_is_edge_triggered_and_rearms_after_clear(*, tmp_path):
    tick = 1_000.0
    repo, topic, _session, _fake, sup, track = _served_track(tmp_path=tmp_path, now=lambda: tick)
    _write_premise(repo=repo, topic=topic)
    _write_local_runs(repo=repo, records=[])

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        assert sup.evaluate(track=track, act=True).status == "wait-target-missing"
        assert sup.evaluate(track=track, act=True).status == "wait-target-missing"
        _write_local_runs(repo=repo, records=[{"id": "run-1", "status": "running"}])
        tick += 1.0
        assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
        _write_local_runs(repo=repo, records=[])
        tick += 1.0
        assert sup.evaluate(track=track, act=True).status == "wait-target-missing"

    alert_lines = [
        json.loads(line)
        for line in err.getvalue().splitlines()
        if json.loads(line)["event"] == "wait-target-missing"
    ]
    assert len(alert_lines) == 2


def test_wait_target_reverification_is_cached_per_poll_tick(*, tmp_path):
    now = 1_000.0
    repo, topic, _session, _fake, sup, track = _served_track(tmp_path=tmp_path, now=lambda: now)
    _write_premise(repo=repo, topic=topic)
    _write_local_runs(repo=repo, records=[])

    assert sup.evaluate(track=track, act=True).status == "wait-target-missing"
    (repo / "tmp" / "overseer" / "fabro-ps-a.json").unlink()
    assert sup.evaluate(track=track, act=True).status == "wait-target-missing"
