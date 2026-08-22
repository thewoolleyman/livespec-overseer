"""Beside-tests for supervisor.py — archive-GC.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import pytest
import registry
import supervisor
from test_supervisor_builders import (
    TEST_EPIC,
    codex_home_with,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# archive-GC.
# --------------------------------------------------------------------------- #


def test_archive_gc_drops_archived_row(*, tmp_path):
    repo = tmp_path / "repo"
    (repo / "plan").mkdir(parents=True)
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.append_mapping(
        track=registry.Track(topic="ghost", repo=str(repo), tmux="repo--ghost"),
        store_path=sup.store_path,
    )
    registry.append_mapping(
        track=registry.Track(topic="live", repo=str(repo), tmux="repo--live"),
        store_path=sup.store_path,
    )
    (repo / "plan" / "live").mkdir()  # 'live' still present

    dropped = sup.archive_gc()
    assert dropped == 1
    remaining = {t.topic for t in registry.read_valid_mapping(store_path=sup.store_path)}
    assert remaining == {"live"}


def test_archive_gc_keeps_row_when_repo_root_missing(*, tmp_path):
    """B6: a transiently-unreachable repo ROOT (unmount / mid-move) must NOT drop
    the row and lose its custom overrides — only a plan gone under an EXISTING
    root is a real deletion."""
    missing_repo = tmp_path / "unmounted"  # does not exist
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.append_mapping(
        track=registry.Track(
            topic="t", repo=str(missing_repo), tmux="unmounted--t", ctx_threshold=30
        ),
        store_path=sup.store_path,
    )
    dropped = sup.archive_gc()
    assert dropped == 0
    rows = registry.read_valid_mapping(store_path=sup.store_path)
    assert [(r.topic, r.ctx_threshold) for r in rows] == [("t", 30)]  # override preserved


# --------------------------------------------------------------------------- #
# Whole-tick integration: discovery ⋈ mapping renders unassigned + mapped rows.
# --------------------------------------------------------------------------- #


def test_tick_builds_unassigned_and_mapped_rows(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path, topic="mapped")
    (repo / "plan" / "unmapped").mkdir(parents=True)
    (repo / "plan" / "unmapped" / "handoff.md").write_text("h\n")
    session = registry.tmux_id(repo=str(repo), topic="mapped")
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic="mapped", session=session), store_path=sup.store_path
    )

    views = sup.tick(act=True)
    by_topic = {v.topic: v for v in views}
    # Idle at 73% (above threshold) with no declaration → nudged to keep going.
    assert by_topic["mapped"].status == "idle-with-context-left"
    assert by_topic["unmapped"].status == "unassigned"
    assert by_topic["unmapped"].tmux is None


def test_list_command_is_read_only(*, tmp_path):
    """`list` (act=False) must derive status but never inject/restart NOR mutate
    the store (no archive-GC, no auto-link) — B6."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=40)
    )  # below threshold — would warn if acting
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )

    views = sup.tick(act=False)
    assert views[0].status == "warned"  # status still derived
    assert not fake.has(method="paste")  # but NO side effect
    assert not fake.has(method="respawn")


def test_list_does_not_auto_link_or_gc(*, tmp_path):
    """B6: a read-only `list` over an unassigned discovered plan must NOT create a
    mapping row (auto-link is a store mutation)."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)])
    # no mapping row appended → discovered plan is unassigned
    sup.tick(act=False)
    assert registry.read_valid_mapping(store_path=sup.store_path) == []  # list did NOT auto-link


# --------------------------------------------------------------------------- #
# Reboot recovery (startup-only).
# --------------------------------------------------------------------------- #


def test_recover_recreates_missing_mapped_session(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()  # session absent → must be recreated
    fake.panes[session] = idle_capture()  # post-launch: empty box so submit confirms
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )

    recovered = sup.recover_missing_sessions()
    assert recovered == [session]
    assert ("new", session, str(repo)) in fake.calls
    assert (
        "respawn",
        session,
        str(repo),
        f"claude --dangerously-skip-permissions -n {topic}",
        {
            "ANTHROPIC_MODEL": None,
            "ANTHROPIC_SMALL_FAST_MODEL": None,
            "CLAUDE_CODE_DISABLE_1M_CONTEXT": None,
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS": None,
        },
    ) in fake.calls
    assert supervisor.plan_epic_resume(repo=str(repo), epic=TEST_EPIC) in fake.paste_texts()


def test_recover_skips_when_new_session_fails(*, tmp_path):
    """Codex re-review #3: if `new-session` fails to create the exact session,
    recovery must NOT proceed to `_do_launch`/`respawn` (which could target a
    prefix-matched live sibling) — it surfaces and skips."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()  # session absent
    fake.new_session_ok = False  # new-session fails to create it
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )

    recovered = sup.recover_missing_sessions()
    assert recovered == []
    assert not fake.has(method="respawn")  # never respawned a prefix-matched sibling


def test_recover_still_recreates_a_claude_track_as_claude(*, tmp_path):
    """A topic absent from the codex index (even when OTHER topics are indexed) is a Claude
    track — recovered with the claude command, exactly as before the #5 dispatch."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.panes[session] = idle_capture()  # post-launch empty box so the resume submit confirms
    # A codex index that names a DIFFERENT topic — the dispatch must not match this track.
    home = codex_home_with(
        tmp_path=tmp_path,
        topic="a-different-codex-topic",
        session_id="aaaaaaaa-bbbb-cccc-dddd-ffffffffffff",
    )
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, codex_home=str(home))
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )

    recovered = sup.recover_missing_sessions()
    assert recovered == [session]
    # Build the expected from `_launch_command` (parallel to the codex test's use of
    # `_codex_launch_command`) so this stays correct through any future change to
    # how `_launch_command` shapes the spawn — no hardcoded command string to drift.
    expected = supervisor.Supervisor._launch_command(
        track=mapped_track(repo=repo, topic=topic, session=session)
    )
    assert (
        "respawn",
        session,
        str(repo),
        expected,
        {
            "ANTHROPIC_MODEL": None,
            "ANTHROPIC_SMALL_FAST_MODEL": None,
            "CLAUDE_CODE_DISABLE_1M_CONTEXT": None,
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS": None,
        },
    ) in fake.calls
