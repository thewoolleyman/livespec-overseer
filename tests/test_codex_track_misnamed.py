"""A live Codex thread named around its topic is surfaced as misnamed (overseer-uzvcbn.6).

Measured 2026-10-26: a Codex seat relaunched by hand (not by the daemon) was auto-titled
`Resume <topic>` by Codex, because the `/rename <topic>` binding is a daemon-only step.
Adoption joins a Codex track only on an EXACT thread-name match, so the live seat was
invisible and its row read `session-gone` -- indistinguishable from a dead seat.

Containment of the topic is evidence for the OPERATOR, never an identity, so the daemon
surfaces a distinct `codex-track-misnamed` row with the exact repair and acts on nothing;
exact-name adoption stays the only way a session becomes a track.

The edges cover a thread already bound to another track, a seat found only through the
identity chain (a Codex 0.16x carrier holding no rollout, its persistence in a shared
app-server) and named by its qualified Herdr pane, and a done track keeping its quiet status.

The subject module is checked for on disk first, so the Red moment is a genuine assertion
failure rather than a collection error that would only prove it unimportable.
"""

from __future__ import annotations

import contextlib
import io
import json
import sqlite3
from pathlib import Path

import herdr_identity
import pytest
import registry
from test_codex_sessions_fakes import ID_A, ID_B, fake_index, fake_rollout
from test_supervisor_builders import (
    codex_idle_capture,
    declare,
    make_plan,
    make_supervisor,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

pytestmark = pytest.mark.integration

_PACKAGE = Path(__file__).resolve().parent.parent / "overseer"
STATUS = "codex-track-misnamed"
PANE = "live-codex"
DEAD = "dead-topic"
ID_C = "019fc714-beaa-7992-aedf-039091f6d94a"
CARRIER_PID = 9100
APP_SERVER_PID = 9200
OPERATOR_PID = 9300


def build(*, tmp_path, threads, plans=("topic",), mapped=("topic",), cwds=None):
    """One repo, one live Codex pane per thread; every mapped track's own tmux is dead.

    ``threads`` is ``[(session id, thread name)]``; thread ``i`` runs as pid ``9000 + i``
    in pane ``live-codex`` (``live-codex1`` ...). ``cwds`` overrides a pid's cwd.
    """
    assert (_PACKAGE / "_supervisor_codex_misnamed.py").is_file(), "not implemented yet"
    repo, _ = make_plan(tmp_path=tmp_path, topic=plans[0])
    for plan in plans[1:]:
        _ = make_plan(tmp_path=tmp_path, topic=plan)
    home = fake_index(tmp_path=tmp_path, records=threads)
    fake = FakeTmux()
    pids = {9000 + i: i for i in range(len(threads))}
    names = {i: PANE + (str(i) if i else "") for i in pids.values()}
    for pane in names.values():
        fake.serve(session=pane, repo=repo, capture=codex_idle_capture(ctx=40), cmd="bun")
    fake.pane_pids = {7000 + i: pane for i, pane in names.items()}
    cwd_of = {pid: str((cwds or {}).get(pid, repo)) for pid in pids}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        watch_repos=[str(repo)],
        codex_home=str(home),
        codex_pids_of_comm=lambda *, comm: list(pids) if comm == "codex" else [],
        codex_fd_targets_of=lambda *, pid: [fake_rollout(session_id=threads[pids[pid]][0])]
        if pid in pids
        else [],
        codex_cwd_of=lambda *, pid: cwd_of.get(pid),
        ppid_of=lambda *, pid: 7000 + pids[pid] if pid in pids else None,
    )
    for topic in mapped:
        registry.append_mapping(
            track=registry.PlanTrack(
                topic=topic,
                repo=str(repo),
                tmux=DEAD if topic == "topic" else f"dead-{topic}",
                epic="overseer-test-epic",
                model_profile={"harness": "claude", "model": "claude-fable-5-1", "wrapper": None},
            ),
            store_path=sup.store_path,
            added_at="2026-10-26T00:00:00Z",
        )
    return repo, home, fake, sup


def tick(*, sup, act=True):
    """One round; returns (rows by topic, the daemon's structured event lines)."""
    log = io.StringIO()
    with contextlib.redirect_stderr(log):
        views = sup.tick(act=act)
    events = [json.loads(line) for line in log.getvalue().splitlines() if line.startswith("{")]
    return {view.topic: view for view in views}, events


def misnamed_events(*, events):
    return [event for event in events if event.get("event") == STATUS]


def test_a_live_thread_named_around_its_topic_is_surfaced_as_misnamed_and_not_acted_on(*, tmp_path):
    repo, _home, fake, sup = build(tmp_path=tmp_path, threads=[(ID_A, "Resume topic")])
    ready = declare(repo=repo, topic="topic", value="ready")

    rows, events = tick(sup=sup)

    row = rows["topic"]
    assert row.status == STATUS
    assert [r.status for r in rows.values()].count("session-gone") == 0
    for fragment in (PANE, ID_A, "Resume topic", "/rename topic"):
        assert fragment in (row.note or "")
    assert f"{STATUS} — " in sup.out.getvalue()
    assert [event["topic"] for event in misnamed_events(events=events)] == ["topic"]
    mapped = registry.read_valid_mapping(store_path=sup.store_path)
    assert [(track.topic, track.tmux) for track in mapped] == [("topic", DEAD)]
    assert ready.read_text() == "ready\n"
    assert [call[0] for call in fake.calls if call[0] in {"respawn", "paste", "send_keys"}] == []


def test_a_read_only_round_reports_the_row_without_notifying(*, tmp_path):
    _repo, _home, _fake, sup = build(tmp_path=tmp_path, threads=[(ID_A, "Resume topic")])

    rows, events = tick(sup=sup, act=False)

    assert rows["topic"].status == STATUS
    assert misnamed_events(events=events) == []


def test_the_row_replaces_session_gone_even_when_the_recorded_harness_is_stale(*, tmp_path):
    """The mapped row records `harness: claude`; the CANDIDATE's own runtime is Codex."""
    _repo, _home, _fake, sup = build(tmp_path=tmp_path, threads=[(ID_A, "Resume topic")])
    track = registry.read_valid_mapping(store_path=sup.store_path)[0]
    assert (track.model_profile or {}).get("harness") == "claude"

    rows, _events = tick(sup=sup)

    assert rows["topic"].status == STATUS


def test_every_candidate_is_named_with_one_repair_line(*, tmp_path):
    _repo, _home, _fake, sup = build(
        tmp_path=tmp_path, threads=[(ID_A, "Resume topic"), (ID_B, "topic follow-up")]
    )

    rows, _events = tick(sup=sup)

    note = rows["topic"].note or ""
    for fragment in (ID_A, "Resume topic", ID_B, "topic follow-up", PANE, PANE + "1"):
        assert fragment in note
    assert note.count("/rename topic") == 1


def test_the_operator_is_notified_once_per_condition_and_candidate_set(*, tmp_path):
    _repo, home, _fake, sup = build(tmp_path=tmp_path, threads=[(ID_A, "Resume topic")])

    _, first = tick(sup=sup)
    _, second = tick(sup=sup)
    fake_index(tmp_path=tmp_path, records=[(ID_A, "topic, resumed")])
    _, renamed = tick(sup=sup)

    assert len(misnamed_events(events=first)) == 1
    assert misnamed_events(events=second) == []
    assert misnamed_events(events=renamed) == []
    assert home.is_dir()


def test_the_notification_rearms_when_the_candidate_set_changes_or_the_condition_clears(
    *, tmp_path
):
    _repo, _home, _fake, sup = build(
        tmp_path=tmp_path, threads=[(ID_A, "Resume topic"), (ID_B, "unrelated")]
    )
    _ = tick(sup=sup)

    fake_index(tmp_path=tmp_path, records=[(ID_A, "Resume topic"), (ID_B, "topic again")])
    _, widened = tick(sup=sup)
    fake_index(tmp_path=tmp_path, records=[(ID_A, "unrelated"), (ID_B, "unrelated")])
    rows, cleared = tick(sup=sup)
    fake_index(tmp_path=tmp_path, records=[(ID_A, "Resume topic"), (ID_B, "unrelated")])
    _, recurred = tick(sup=sup)

    assert len(misnamed_events(events=widened)) == 1
    assert rows["topic"].status == "session-gone"
    assert misnamed_events(events=cleared) == []
    assert len(misnamed_events(events=recurred)) == 1


def test_the_session_is_adopted_on_the_round_after_it_is_renamed_to_its_topic(*, tmp_path):
    _repo, _home, _fake, sup = build(tmp_path=tmp_path, threads=[(ID_A, "Resume topic")])
    assert tick(sup=sup)[0]["topic"].status == STATUS

    fake_index(tmp_path=tmp_path, records=[(ID_A, "topic")])
    rows, events = tick(sup=sup)

    assert rows["topic"].status not in {STATUS, "session-gone"}
    mapped = registry.read_valid_mapping(store_path=sup.store_path)
    assert [(track.topic, track.tmux) for track in mapped] == [("topic", PANE)]
    assert misnamed_events(events=events) == []


def test_supervisor_other_track_and_out_of_repository_threads_are_never_candidates(*, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _repo, _home, _fake, sup = build(
        tmp_path=tmp_path,
        threads=[(ID_A, "topic-supervisor"), (ID_B, "topic-two"), (ID_C, "Resume topic")],
        plans=("topic", "topic-two"),
        mapped=("topic",),
        cwds={9002: elsewhere},
    )

    rows, events = tick(sup=sup)

    assert rows["topic"].status == "session-gone"
    assert misnamed_events(events=events) == []
    mapped = registry.read_valid_mapping(store_path=sup.store_path)
    assert [track.topic for track in mapped if track.topic == "topic"] == ["topic"]


def test_a_discovered_but_unassigned_plan_never_raises_a_misnamed_row(*, tmp_path):
    _repo, _home, _fake, sup = build(tmp_path=tmp_path, threads=[(ID_A, "Resume topic")], mapped=())

    rows, events = tick(sup=sup)

    assert rows["topic"].status == "unassigned"
    assert misnamed_events(events=events) == []


def herdr_pane(*, pane_id: str) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/run/herdr.sock",
            server_pid=401,
            server_starttime="2026-10-26T00:00:00Z",
            pane_id=pane_id,
        )
    )


def bind_other_track(*, sup, repo, tmux, identity):
    registry.append_mapping(
        track=registry.PlanTrack(
            topic="other",
            repo=str(repo),
            tmux=tmux,
            epic="overseer-test-epic",
            observed_session_identity=identity,
        ),
        store_path=sup.store_path,
        added_at="2026-10-26T00:00:00Z",
    )


@pytest.mark.parametrize(
    ("tmux", "identity"),
    [(PANE, None), ("dead-other", f"codex:{ID_A}")],
    ids=["bound-by-pane", "bound-by-recorded-identity"],
)
def test_a_thread_already_bound_to_another_track_is_never_a_candidate(*, tmp_path, tmux, identity):
    repo, _home, _fake, sup = build(
        tmp_path=tmp_path, threads=[(ID_A, "Resume topic")], plans=("topic", "other")
    )
    bind_other_track(sup=sup, repo=repo, tmux=tmux, identity=identity)

    rows, events = tick(sup=sup)

    assert rows["topic"].status == "session-gone"
    assert misnamed_events(events=events) == []


def test_a_seat_found_only_through_the_identity_chain_is_named_by_its_herdr_pane(*, tmp_path):
    repo, home, fake, sup = build(tmp_path=tmp_path, threads=[(ID_A, "Resume topic")])
    pane = herdr_pane(pane_id="w2H:p2X")
    fake.serve(session=pane, repo=repo, capture=fake.panes[PANE], cmd="bun")
    fake.pane_pids = {7100: pane}
    sup.codex_pids_of_comm = lambda *, comm: [CARRIER_PID, OPERATOR_PID, APP_SERVER_PID]
    sup.codex_cwd_of = lambda *, pid: str(repo) if pid == CARRIER_PID else "/"
    sup.codex_foreground_pgrp_of = lambda *, pid: None if pid == APP_SERVER_PID else pid
    sup.codex_fd_targets_of = lambda *, pid: (
        [str(home / "sessions" / f"rollout-2026-10-26T00-00-00-{ID_A}.jsonl")]
        if pid == APP_SERVER_PID
        else []
    )
    sup.children_of = lambda *, pid: [APP_SERVER_PID] if pid == OPERATOR_PID else []
    sup.ppid_of = lambda *, pid: 7100 if pid == CARRIER_PID else None
    sup.environ_of = lambda *, pid: b""
    database = sqlite3.connect(home / "state_1.sqlite")
    with database:
        _ = database.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, model TEXT, cwd TEXT)")
        _ = database.execute("INSERT INTO threads VALUES (?, ?, ?)", (ID_A, "gpt-5.6", str(repo)))
    database.close()

    rows, events = tick(sup=sup)

    assert rows["topic"].status == STATUS
    assert rows["topic"].tmux == pane
    assert "pane w2H:p2X" in (rows["topic"].note or "")
    assert [event["topic"] for event in misnamed_events(events=events)] == ["topic"]
    mapped = registry.read_valid_mapping(store_path=sup.store_path)
    assert [(track.topic, track.tmux) for track in mapped] == [("topic", DEAD)]


def test_a_track_that_declared_itself_done_keeps_its_quiet_status(*, tmp_path):
    repo, _home, _fake, sup = build(tmp_path=tmp_path, threads=[(ID_A, "Resume topic")])
    _ = declare(repo=repo, topic="topic", value="done")

    rows, events = tick(sup=sup)

    assert rows["topic"].status == "done"
    assert misnamed_events(events=events) == []
