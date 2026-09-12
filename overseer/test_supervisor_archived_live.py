"""Beside-tests — plan ARCHIVAL does not end supervision of a session that is still live.

Maintainer ruling 2026-09-12: archival ends live-plan DISCOVERY; it does not end
supervision of a session that is still running. `create-agent-cockpit-repo` stayed a
live tmux/agent session after its plan was archived, but archive-only discovery took it
out of the daemon snapshot AND out of the mapping — so the running session had no
tracked row, and the daemon could no longer read its context, inject a wind-down, or
complete a ready-gated restart.

This module owns the PER-HARNESS supervision half of that ruling: a Claude and a Codex
archived-live track each carried through a whole ready-gated restart. When the mapping
and its derivable sidecars may finally go — and how retention is reported once — is
`tests/test_archived_live_cleanup.py`.

These tests drive the PUBLIC daemon surface (`tick`) rather than the retention predicate
directly, because the defect was never in one predicate: it was in what the tick's row
set CONTAINED. A test that called the predicate would have passed against a daemon that
still dropped the row.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io
import json
import shutil
from pathlib import Path

import codex_sessions
import pytest
import registry
from test_codex_sessions_fakes import ID_A, ID_B, fake_host, fake_index, fake_rollout
from test_supervisor_builders import (
    TEST_EPIC,
    arm_ready_marker,
    codex_busy_capture,
    codex_idle_capture,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    write_session,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _archive_plan(*, repo, topic):
    """`git mv plan/<topic> plan/archive/<topic>` — the move the daemon must survive."""
    archive = repo / "plan" / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    _ = shutil.move(str(repo / "plan" / topic), str(archive / topic))


def _snapshot_rows(*, sup):
    return json.loads(Path(sup.status_path).read_text(encoding="utf-8"))["rows"]


def _mapped_claude_supervisor(*, tmp_path, ctx=40):
    """A mapped Claude track the whole TICK can drive, registry join included.

    The Claude session registry is real here rather than pre-seeded on the Supervisor,
    because `build_rows` recomputes `claude_status_by_session` from `sessions_dir` at
    the top of every tick — a pre-seeded map is overwritten, and a track with no live
    Claude status never reaches the wrap-up at all.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=200, name=topic, cwd=repo)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=ctx))
    fake.pane_pids = {100: session}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        watch_repos=[str(repo)],
        sessions_dir=sessions_dir,
        ppid_of=lambda *, pid: {200: 100}.get(pid),
        starttime_of=lambda *, pid: {200: "pt"}.get(pid),
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )
    return repo, topic, session, fake, sup


def _mapped_codex_supervisor(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="codex-track")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    codex_home = fake_index(tmp_path=tmp_path, records=[(ID_A, "some-other-topic")])
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=codex_idle_capture(ctx=40, topic=topic), cmd="bun"
    )
    fake.pane_pids = {7001: session}
    host = fake_host(comms={9000: codex_sessions.CODEX_COMM}, cwds={9000: str(repo)})

    def rollout_fds(*, pid):
        """The rollout this pane's Codex holds — a fresh one once it has been restarted."""
        if pid != 9000:
            return []
        restarted = any(call[0] == "respawn" for call in fake.calls)
        return [fake_rollout(session_id=ID_A if restarted else ID_B)]

    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        watch_repos=[str(repo)],
        codex_home=str(codex_home),
        codex_pids_of_comm=host["pids_of_comm"],
        codex_fd_targets_of=rollout_fds,
        codex_cwd_of=host["cwd_of"],
        ppid_of=lambda *, pid: {9000: 7001}.get(pid),
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )
    return repo, topic, session, fake, sup


def test_claude_archived_live_track_completes_a_ready_gated_restart(*, tmp_path):
    """The whole reported failure, end to end: a mapped Claude track is wrapped up, its
    plan is archived MID-ROUND, and the `ready` it then declares must still restart it —
    from the row's own epic locator, which archival does not touch."""
    repo, topic, _session, fake, sup = _mapped_claude_supervisor(tmp_path=tmp_path)

    with contextlib.redirect_stderr(_io.StringIO()):
        warned = sup.tick(act=True)
    assert [(row.topic, row.status) for row in warned] == [(topic, "warned")]

    _archive_plan(repo=repo, topic=topic)
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    with contextlib.redirect_stderr(_io.StringIO()):
        restarted = sup.tick(act=True)

    assert [(row.topic, row.status) for row in restarted] == [(topic, "restarting")]
    assert [row["topic"] for row in _snapshot_rows(sup=sup)] == [topic]
    assert _snapshot_rows(sup=sup)[0]["archived_live"] is True
    assert any(TEST_EPIC in text for text in fake.paste_texts())  # launch profile intact


def test_codex_archived_live_track_completes_a_ready_gated_restart(*, tmp_path):
    """The Codex twin. A different harness, the same ruling: the runtime is what keeps a
    row supervised, and the daemon must not lose a live Codex session to `git mv`."""
    repo, topic, session, fake, sup = _mapped_codex_supervisor(tmp_path=tmp_path)
    fake.on_paste = lambda target, _text: fake.panes.__setitem__(target, codex_busy_capture(ctx=40))

    with contextlib.redirect_stderr(_io.StringIO()):
        warned = sup.tick(act=True)
    assert [(row.topic, row.runtime, row.status) for row in warned] == [(topic, "codex", "warned")]

    fake.panes[session] = codex_idle_capture(ctx=40, topic=topic)
    _archive_plan(repo=repo, topic=topic)
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    with contextlib.redirect_stderr(_io.StringIO()):
        restarted = sup.tick(act=True)

    assert [(row.topic, row.runtime, row.status) for row in restarted] == [
        (topic, "codex", "restarting")
    ]
    assert _snapshot_rows(sup=sup)[0]["archived_live"] is True


def test_archived_live_successor_stays_supervised_until_its_runtime_exits(*, tmp_path):
    """Retention is keyed on the RUNTIME, not on the session that was running when the
    plan was archived: the fresh successor a restart launches keeps the same retained
    mapping, and only its exit makes cleanup eligible."""
    repo, topic, session, fake, sup = _mapped_claude_supervisor(tmp_path=tmp_path)
    _archive_plan(repo=repo, topic=topic)

    with contextlib.redirect_stderr(_io.StringIO()):
        assert [row.topic for row in sup.tick(act=True)] == [topic]
        assert [row.topic for row in sup.tick(act=True)] == [topic]
    assert [track.topic for track in registry.read_valid_mapping(store_path=sup.store_path)] == [
        topic
    ]

    assert fake.kill_session(session=session)  # the successor runtime exits
    with contextlib.redirect_stderr(_io.StringIO()):
        assert sup.tick(act=True) == []
    assert registry.read_valid_mapping(store_path=sup.store_path) == []


def test_read_only_list_shows_an_archived_live_track_without_mutating_the_store(*, tmp_path):
    """`list` is advertised read-only, so the retention it DISPLAYS must not be a
    retention it PERFORMED — the row is joined back in, and nothing is written."""
    repo, topic, _session, _fake, sup = _mapped_claude_supervisor(tmp_path=tmp_path, ctx=80)
    _archive_plan(repo=repo, topic=topic)

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        views = sup.tick(act=False)

    assert [row.topic for row in views] == [topic]
    assert "archived-live-retained" not in err.getvalue()


def test_a_live_supervisor_seat_is_never_re_admitted_by_archived_live_retention(*, tmp_path):
    """CONTROL, on the DISCOVERY surface. A `-supervisor` seat whose worker thread was
    archived is RETIRED by design (overseer-y26) — its binder is gone on purpose. Its
    session being live must therefore NOT re-admit it to the tick's row set, which is a
    different surface from archive-GC's own keep decision and would otherwise resurrect
    a seat the daemon deliberately stopped supervising."""
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
        views = sup.tick(act=True)

    assert views == []
    assert sup.archived_live == frozenset()
    assert registry.read_valid_mapping(store_path=sup.store_path) == []
