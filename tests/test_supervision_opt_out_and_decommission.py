"""Regression coverage for maintainer-managed tracks with no per-plan supervisor."""

from __future__ import annotations

import contextlib
import io as _io

from overseer import registry, supervisor
from overseer.test_supervisor_builders import (
    idle_capture,
    isolate_store,
    make_plan,
    make_supervisor,
    mapped_track,
)
from overseer.test_supervisor_fakes import FakeTmux


def test_supervision_none_sidecar_makes_migrated_epic_track_quiet(*, tmp_path):
    """A maintainer-managed plan can explicitly opt out of a per-plan supervisor.

    The migrated epic file still exists, so this is the structural RED: without the
    per-track opt-out marker, epic presence alone drives Surface B forever.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    plan = repo / "plan" / topic
    (plan / "epic.md").write_text("ledger anchor `overseer-test-epic`\n")
    (plan / ".no-supervisor").write_text("direct foreman management\n")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track=track, act=True)
        listed = sup.evaluate(track=track, act=False)
    assert view.status == "idle-with-context-left"
    assert listed.status == "idle-with-context-left"
    assert "supervisor" not in err.getvalue()


def test_unmarked_migrated_epic_track_still_requires_supervisor(*, tmp_path):
    """The opt-out is per track: an unmarked migrated plan still raises Surface B."""
    repo, topic = make_plan(tmp_path=tmp_path)
    (repo / "plan" / topic / "epic.md").write_text("ledger anchor `overseer-test-epic`\n")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "idle-with-context-left"
    assert f"start tmux session '{session}-supervisor'" in err.getvalue()


def test_cli_remove_operates_on_reserved_entity_topics(*, tmp_path, monkeypatch):
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo = str(tmp_path / "repo")
    registry.append_mapping(
        track=registry.SupervisorSeat(
            repo=repo,
            topic="alpha-supervisor",
            tmux="alpha-supervisor",
            epic="overseer-test-epic",
            supervised_topic="alpha",
        ),
        store_path=store,
    )
    registry.append_mapping(
        track=registry.ForemanSeat(
            repo=repo,
            topic="repo-foreman",
            tmux="repo-foreman",
            epic="overseer-foreman-epic",
        ),
        store_path=store,
    )

    assert supervisor.main(argv=["remove", "--repo", repo, "--topic", "alpha-supervisor"]) == 0
    assert supervisor.main(argv=["remove", "--repo", repo, "--topic", "repo-foreman"]) == 0

    assert registry.read_valid_mapping(store_path=store) == []


def test_cli_unassign_operates_on_reserved_entity_topics(*, tmp_path, monkeypatch):
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo = str(tmp_path / "repo")
    registry.append_mapping(
        track=registry.SupervisorSeat(
            repo=repo,
            topic="alpha-supervisor",
            tmux="alpha-supervisor",
            epic="overseer-test-epic",
            supervised_topic="alpha",
        ),
        store_path=store,
    )

    assert supervisor.main(argv=["unassign", "--repo", repo, "--topic", "alpha-supervisor"]) == 0

    assert registry.read_valid_mapping(store_path=store) == []


def test_cli_add_still_refuses_reserved_worker_topic(*, tmp_path, monkeypatch, capsys):
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    repo_path = tmp_path / "repo"
    (repo_path / "plan" / "orphan-supervisor").mkdir(parents=True)
    repo = str(repo_path)

    assert supervisor.main(argv=["add", "--repo", repo, "--topic", "orphan-supervisor"]) == 1

    assert "worker topics may not end in -supervisor" in capsys.readouterr().err
    assert registry.read_valid_mapping(store_path=store) == []
