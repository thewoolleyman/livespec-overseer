"""Archive cleanup is gated on runtime evidence, and retention is reported once.

Maintainer ruling 2026-09-12: plan archival ends live-plan DISCOVERY; it does not end
supervision of a session that is still running. `create-agent-cockpit-repo` stayed a
live tmux/agent session after its plan was archived, but archive-only discovery took it
out of the daemon snapshot AND out of the mapping — so the running session had no
tracked row, and the daemon could no longer read its context, inject a wind-down, or
complete a ready-gated restart.

This module owns the CLEANUP half of that ruling — when the mapping and its derivable
sidecars may finally go, and how an operator is told a row is being retained on purpose.
The per-harness supervision half (a Claude and a Codex archived-live track each carried
through a whole ready-gated restart) is beside the code in
`overseer/test_supervisor_archived_live.py`.

Every test drives the PUBLIC daemon surface (`tick` / `archive_gc`) rather than the
retention predicate, because the defect was never in one predicate: it was in what the
tick's row set CONTAINED, and a predicate-level test would have passed against a daemon
that still dropped the row.

``import registry`` resolves via `tests/conftest.py`, which puts `overseer/` on
`sys.path` exactly as `overseer/conftest.py` does for the beside-tests.
"""

from __future__ import annotations

import contextlib
import io as _io
import json
import shutil

import registry
from test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _archive_plan(*, repo, topic):
    """`git mv plan/<topic> plan/archive/<topic>` — the move the daemon must survive."""
    archive = repo / "plan" / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    _ = shutil.move(str(repo / "plan" / topic), str(archive / topic))


def _mapped_live_track(*, tmp_path):
    """A mapped plan track whose recorded tmux session is live, ready to be archived."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=80))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )
    return repo, topic, session, fake, sup


def test_archive_cleanup_waits_for_runtime_evidence_before_clearing_sidecars(*, tmp_path):
    """Cleanup is gated on authoritative runtime evidence — while the recorded session
    still exists the mapping AND its derivable sidecars are held; once the runtime is
    gone the same GC pass drops both."""
    repo, topic, session, fake, sup = _mapped_live_track(tmp_path=tmp_path)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    _archive_plan(repo=repo, topic=topic)

    with contextlib.redirect_stderr(_io.StringIO()):
        assert sup.archive_gc() == 0
    assert [track.topic for track in registry.read_valid_mapping(store_path=sup.store_path)] == [
        topic
    ]
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == 1000.0
    )

    assert fake.kill_session(session=session)
    with contextlib.redirect_stderr(_io.StringIO()):
        assert sup.archive_gc() == 1
    assert registry.read_valid_mapping(store_path=sup.store_path) == []
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )


def test_archived_live_retention_is_reported_once_in_the_event_history(*, tmp_path):
    """The daemon log is an EVENT history: entering retention is ONE line, not one line
    per tick — and it names the track, so an operator can tell an intentionally retained
    archived row from a stale unarchived one."""
    repo, topic, _session, _fake, sup = _mapped_live_track(tmp_path=tmp_path)
    _archive_plan(repo=repo, topic=topic)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        for _ in range(3):
            _ = sup.tick(act=True)

    events = [json.loads(line) for line in err.getvalue().splitlines()]
    retained = [event for event in events if event["event"] == "archived-live-retained"]
    assert [event["topic"] for event in retained] == [topic]


def test_archived_plan_with_no_mapping_and_no_runtime_produces_no_rows(*, tmp_path):
    """CONTROL. Without this leg the retention could be an unconditional "keep archived
    plans", which would resurrect every retired plan directory in every watched repo as
    a row — and a row the daemon may act on."""
    repo = tmp_path / "repo"
    (repo / "plan" / "archive" / "retired").mkdir(parents=True)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])

    with contextlib.redirect_stderr(_io.StringIO()):
        views = sup.tick(act=True)

    assert views == []
    assert registry.read_valid_mapping(store_path=sup.store_path) == []
    assert not fake.has(method="respawn")
    assert not fake.has(method="new")


def test_unreachable_repo_root_is_not_read_as_an_archived_live_track(*, tmp_path):
    """CONTROL. A repo root that is transiently unreachable (unmount, mid-move) is not
    evidence of ARCHIVAL, so the row is still held untouched by GC (B6) — but it must
    not be joined back in as a retained row either, which would claim a supervision the
    daemon has no plan directory, and no discovery, to support."""
    missing = tmp_path / "unmounted"
    fake = FakeTmux()
    fake.serve(session="ghost", repo=missing, capture=idle_capture(ctx=80))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(missing)])
    registry.append_mapping(
        track=mapped_track(repo=missing, topic="ghost", session="ghost"),
        store_path=sup.store_path,
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        views = sup.tick(act=True)

    assert views == []
    assert [track.topic for track in registry.read_valid_mapping(store_path=sup.store_path)] == [
        "ghost"
    ]


def test_archived_live_retention_never_reaches_a_supervisor_seat(*, tmp_path):
    """CONTROL. A `-supervisor` seat whose worker thread was archived is RETIRED by
    design (overseer-y26): its binder is gone on purpose. Retention is a plan-row rule,
    and a live seat session must not resurrect the seat as one."""
    repo = tmp_path / "repo"
    (repo / "plan").mkdir(parents=True)
    fake = FakeTmux()
    fake.serve(session="worker-supervisor", repo=repo, capture=idle_capture(ctx=80))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=registry.Track(
            topic="worker-supervisor",
            repo=str(repo),
            tmux="worker-supervisor",
            epic="overseer-worker",
        ),
        store_path=sup.store_path,
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        assert sup.archive_gc() == 1
    assert registry.read_valid_mapping(store_path=sup.store_path) == []
