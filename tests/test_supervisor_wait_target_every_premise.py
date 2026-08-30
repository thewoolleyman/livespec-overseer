"""Whole-pass coverage for verifying EVERY wait premise on a track.

The pass used to return at the first premise that verified missing with a note,
so which premise a track reported was decided by the premise directory's
filename sort — a digest of the target id. These tests pin the four facts that
early return made unreachable: every premise is verified, every missing premise
is relayed, the reported premise is chosen deliberately, and a cache entry for a
premise no longer on disk is evicted.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import _supervisor_wait_target_sources as sources
import registry
from _supervisor_records import InjectState
from test_supervisor_builders import idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _premise(*, target_id: str, recorded_at: str = "2026-08-19T02:30:00Z") -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "fabro-run",
        "target_id": target_id,
        "evidence_source": "fabro ps -a --json",
        "recorded_at": recorded_at,
        "recheck_by": "2026-08-19T03:00:00Z",
    }


def _premise_dir(*, repo: Path, topic: str) -> Path:
    return repo / "tmp" / "overseer" / topic / "wait-premises"


def _write_premise(*, repo: Path, topic: str, name: str, payload: dict[str, object]) -> None:
    """Write one premise under a CHOSEN filename so the read order is controlled.

    ``read_wait_premises`` returns ``sorted(directory.glob(...))``, so naming the
    files here is how a test decides which premise the old early return would
    have reached first.
    """
    directory = _premise_dir(repo=repo, topic=topic)
    directory.mkdir(parents=True, exist_ok=True)
    _ = (directory / name).write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _write_local_runs(*, repo: Path, records: list[dict[str, object]]) -> None:
    path = repo / "tmp" / "overseer" / "fabro-ps-a.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(records) + "\n", encoding="utf-8")


def _served_track(*, tmp_path: Path, now: Callable[[], float] | None = None):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=90))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    if now is not None:
        sup.now = now
    track = mapped_track(repo=repo, topic=topic, session=session)
    return repo, topic, fake, sup, track


def _evidence_targets(*, repo: Path, topic: str) -> list[str]:
    paths = sorted((repo / "tmp" / "overseer" / topic).glob("wait-target-missing-*.json"))
    return sorted(str(json.loads(path.read_text(encoding="utf-8"))["target_id"]) for path in paths)


def test_a_later_sorting_recovered_premise_has_its_relayed_mark_cleared(*, tmp_path):
    repo, topic, _fake, sup, track = _served_track(tmp_path=tmp_path)
    gone = _premise(target_id="run-gone")
    back = _premise(target_id="run-back")
    _write_premise(repo=repo, topic=topic, name="fabro-run-aaaa.json", payload=gone)
    _write_premise(repo=repo, topic=topic, name="fabro-run-zzzz.json", payload=back)
    _write_local_runs(repo=repo, records=[{"id": "run-back", "status": "running"}])
    back_key = sources.cache_key(record=back)
    sup.inject[(str(repo), topic)] = InjectState(wait_target_relayed_keys={back_key})

    view = sup.evaluate(track=track, act=True)

    assert view.status == "wait-target-missing"
    relayed = sup.inject[(str(repo), topic)].wait_target_relayed_keys
    assert back_key not in relayed
    assert sources.cache_key(record=gone) in relayed


def test_the_relay_reaches_every_missing_premise_on_one_track(*, tmp_path):
    repo, topic, fake, sup, track = _served_track(tmp_path=tmp_path)
    _write_premise(
        repo=repo, topic=topic, name="fabro-run-aaaa.json", payload=_premise(target_id="run-one")
    )
    _write_premise(
        repo=repo, topic=topic, name="fabro-run-zzzz.json", payload=_premise(target_id="run-two")
    )
    _write_local_runs(repo=repo, records=[])

    view = sup.evaluate(track=track, act=True)

    assert view.status == "wait-target-missing"
    relays = fake.paste_texts()
    assert len(relays) == 2
    assert sorted(relay.splitlines()[1] for relay in relays) == [
        "premise: fabro-run run-one",
        "premise: fabro-run run-two",
    ]
    assert _evidence_targets(repo=repo, topic=topic) == ["run-one", "run-two"]


def test_the_reported_premise_is_the_oldest_recorded_not_the_first_filename(*, tmp_path):
    repo, topic, _fake, sup, track = _served_track(tmp_path=tmp_path)
    _write_premise(
        repo=repo,
        topic=topic,
        name="fabro-run-aaaa.json",
        payload=_premise(target_id="run-newer", recorded_at="2026-08-19T02:30:00Z"),
    )
    _write_premise(
        repo=repo,
        topic=topic,
        name="fabro-run-zzzz.json",
        payload=_premise(target_id="run-older", recorded_at="2026-08-19T01:00:00Z"),
    )
    _write_local_runs(repo=repo, records=[])

    view = sup.evaluate(track=track, act=True)

    assert view.status == "wait-target-missing"
    assert view.note == "fabro-run run-older absent from every mandatory leg"


def test_a_removed_premises_cache_entry_does_not_survive_the_next_pass(*, tmp_path):
    tick = 1_000.0
    repo, topic, _fake, sup, track = _served_track(tmp_path=tmp_path, now=lambda: tick)
    payload = _premise(target_id="run-1")
    _write_premise(repo=repo, topic=topic, name="fabro-run-aaaa.json", payload=payload)
    _write_local_runs(repo=repo, records=[])

    assert sup.evaluate(track=track, act=True).status == "wait-target-missing"
    assert sources.cache_key(record=payload) in sup.inject[(str(repo), topic)].wait_target_cache

    (_premise_dir(repo=repo, topic=topic) / "fabro-run-aaaa.json").unlink()
    tick += 1.0

    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    assert sup.inject[(str(repo), topic)].wait_target_cache == {}
