"""Evidence-carrying relay coverage for dead wait-premise targets."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import _supervisor_wait_target as wait_target
import registry
from test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def write_premise(
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
    _ = (directory / f"{target_id}.json").write_text(
        json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_local_runs(*, repo: Path, records: list[dict[str, object]]) -> None:
    path = repo / "tmp" / "overseer" / "fabro-ps-a.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(records) + "\n", encoding="utf-8")


def write_journal(*, repo: Path, records: list[dict[str, object]]) -> None:
    path = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def served_track(*, tmp_path: Path, now: Callable[[], float] | None = None):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=90))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    if now is not None:
        sup.now = now
    track = mapped_track(repo=repo, topic=topic, session=session)
    return repo, topic, session, fake, sup, track


def test_wait_target_missing_relays_evidence_to_prose_waiting_pane(*, tmp_path):
    repo, topic, _session, fake, sup, track = served_track(tmp_path=tmp_path)
    sup.claude_status_by_session = {track.tmux or "": "waiting"}
    write_premise(repo=repo, topic=topic)
    write_local_runs(repo=repo, records=[])

    view = sup.evaluate(track=track, act=True)

    assert view.status == "wait-target-missing"
    [relay] = fake.paste_texts()
    assert "wait-target-missing" in relay
    assert "premise: fabro-run run-1" in relay
    assert "re-query: fabro ps -a --json" in relay
    marker = "evidence record: "
    evidence_path = Path(relay.split(marker, maxsplit=1)[1].splitlines()[0])
    assert evidence_path.is_file()
    assert json.loads(evidence_path.read_text(encoding="utf-8")) == {
        "evidence_source": "fabro ps -a --json",
        "note": "fabro-run run-1 absent from every mandatory leg",
        "premise": {
            "evidence_source": "fabro ps -a --json",
            "kind": "fabro-run",
            "recorded_at": "2026-08-19T02:30:00Z",
            "recheck_by": "2026-08-19T03:00:00Z",
            "schema_version": 1,
            "target_id": "run-1",
        },
        "requery_output": [],
        "status": "wait-target-missing",
        "target_id": "run-1",
    }
    assert ("keys", track.tmux, "Enter") in fake.calls
    assert ("respawn",) not in {call[:1] for call in fake.calls}


def test_wait_target_missing_does_not_raw_paste_relay_to_picker_pane(*, tmp_path):
    repo, topic, _session, fake, sup, track = served_track(tmp_path=tmp_path)
    sup.claude_status_by_session = {track.tmux or "": "waiting"}
    fake.panes[track.tmux or ""] = (
        "The run you waited on is gone.\n❯ 1. Continue with evidence\n  2. Stop\n"
        "  Ctx: 90% left\n"
    )
    write_premise(repo=repo, topic=topic)
    write_local_runs(repo=repo, records=[])

    view = sup.evaluate(track=track, act=True)

    assert view.status == "wait-target-missing"
    assert not fake.has(method="paste")
    assert ("keys", track.tmux, "Enter") not in fake.calls
    assert not list((repo / "tmp" / "overseer" / topic).glob("wait-target-missing-*.json"))
    assert ("respawn",) not in {call[:1] for call in fake.calls}


def test_wait_target_missing_does_not_relay_to_non_waiting_pane(*, tmp_path):
    repo, topic, _session, fake, sup, track = served_track(tmp_path=tmp_path)
    write_premise(repo=repo, topic=topic)
    write_local_runs(repo=repo, records=[])

    view = sup.evaluate(track=track, act=True)

    assert view.status == "wait-target-missing"
    assert not fake.has(method="paste")
    assert not list((repo / "tmp" / "overseer" / topic).glob("wait-target-missing-*.json"))


def test_wait_target_missing_relay_records_remote_journal_requery(*, tmp_path):
    repo, topic, _session, fake, sup, track = served_track(tmp_path=tmp_path)
    sup.claude_status_by_session = {track.tmux or "": "waiting"}
    write_premise(
        repo=repo,
        topic=topic,
        target_id="remote-run",
        extra={
            "execution_location": "remote",
            "dispatch_factory": "hp",
            "evidence_source": "fabro dispatch journal factory=hp",
            "work_item_id": "overseer-x",
        },
    )
    write_journal(
        repo=repo,
        records=[
            {
                "stage": "dispatch-id",
                "work_item_id": "overseer-x",
                "dispatch_id": "remote-run",
                "at": "2026-08-19T02:31:00Z",
            }
        ],
    )

    view = sup.evaluate(track=track, act=True)

    assert view.status == "wait-target-missing"
    [relay] = fake.paste_texts()
    evidence_path = Path(relay.split("evidence record: ", maxsplit=1)[1].splitlines()[0])
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["requery_output"] == [
        {
            "at": "2026-08-19T02:31:00Z",
            "dispatch_id": "remote-run",
            "stage": "dispatch-id",
            "work_item_id": "overseer-x",
        }
    ]


def test_wait_target_missing_relay_fail_soft_when_evidence_record_cannot_be_written(
    *, tmp_path, monkeypatch
):
    repo, topic, _session, fake, sup, track = served_track(tmp_path=tmp_path)
    sup.claude_status_by_session = {track.tmux or "": "waiting"}
    write_premise(repo=repo, topic=topic)
    write_local_runs(repo=repo, records=[])
    monkeypatch.setattr(wait_target, "_evidence_path", lambda **_kwargs: repo)

    view = sup.evaluate(track=track, act=True)

    assert view.status == "wait-target-missing"
    assert not fake.has(method="paste")


def test_wait_target_missing_relay_fail_soft_when_paste_fails(*, tmp_path):
    repo, topic, _session, fake, sup, track = served_track(tmp_path=tmp_path)
    sup.claude_status_by_session = {track.tmux or "": "waiting"}
    fake.paste_ok = False
    write_premise(repo=repo, topic=topic)
    write_local_runs(repo=repo, records=[])

    view = sup.evaluate(track=track, act=True)

    assert view.status == "wait-target-missing"
    assert len(fake.paste_texts()) == 1
    assert not sup.inject[(str(repo), topic)].wait_target_relayed_keys


def test_wait_target_missing_relay_fail_soft_when_submit_fails(*, tmp_path):
    repo, topic, _session, fake, sup, track = served_track(tmp_path=tmp_path)
    sup.claude_status_by_session = {track.tmux or "": "waiting"}
    write_premise(repo=repo, topic=topic)
    write_local_runs(repo=repo, records=[])

    def fail_send_keys(*, session: str, keys: str) -> bool:
        fake.calls.append(("keys", session, keys))
        return False

    fake.send_keys = fail_send_keys

    view = sup.evaluate(track=track, act=True)

    assert view.status == "wait-target-missing"
    assert len(fake.paste_texts()) == 1
    assert not sup.inject[(str(repo), topic)].wait_target_relayed_keys
