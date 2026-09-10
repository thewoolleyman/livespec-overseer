"""`supervisor.py start` dispatches a dead track on evidence, never on the Claude path.

The deliberate operator surface used to enter `do_launch_result` unconditionally, so a
dead mapped track carrying an exact `codex:<uuid>` identity was respawned with the Claude
launcher — the one destructive cross-runtime failure the daemon's own restart arm is
designed against. These pin the dispatch, the refusal, and the retained Claude behavior.
"""

import dataclasses

import pytest
import registry
import supervisor
from test_supervisor_builders import (
    codex_dead_track,
    codex_home_with,
    codex_idle_capture,
    idle_capture,
    isolate_store,
    make_plan,
    make_supervisor,
    mapped_track,
    verify_codex_respawn,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

SID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    claude = tmp_path / "bin" / "claude"
    claude.parent.mkdir()
    claude.write_text("#!/bin/sh\n", encoding="utf-8")
    claude.chmod(0o755)
    monkeypatch.setenv("PATH", str(claude.parent))


def wire_start(*, tmp_path, monkeypatch, fake, codex_home):
    """Point the `start` CLI at ``fake`` and at a Supervisor with a hermetic ``codex_home``.

    `_start_handler` resolves both factories at call time, so patching them here is what
    lets a CLI-level `start` run against a fake tmux and a fake `~/.codex`. The Supervisor
    is built BEFORE the class is patched out, and returned so a test can model what the
    respawned pane becomes.
    """
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, codex_home=str(codex_home))
    monkeypatch.setattr(supervisor.tmuxio, "TmuxIO", lambda: fake)
    monkeypatch.setattr(supervisor, "Supervisor", lambda *, tmux: sup)
    return sup


def respawns(*, fake):
    return [call for call in fake.calls if call[0] == "respawn"]


def codex_start(*, tmp_path, monkeypatch, rollout=True, **verify_kwargs):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    registry.append_mapping(
        track=codex_dead_track(repo=repo, topic=topic, session=session, session_id=SID),
        store_path=store,
    )
    fake = FakeTmux()
    sup = wire_start(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        fake=fake,
        codex_home=codex_home_with(tmp_path=tmp_path, topic=topic, session_id=SID, rollout=rollout),
    )
    verify_codex_respawn(
        sup=sup, fake=fake, plan=(repo, topic, session), session_id=SID, **verify_kwargs
    )
    return repo, topic, session, fake


def test_start_resumes_a_dead_codex_track_under_its_own_runtime_and_identity(
    *, tmp_path, monkeypatch, capsys
):
    """The former wrong-runtime launch: `launched=True` plus a Claude respawn for a Codex row."""
    repo, topic, session, fake = codex_start(tmp_path=tmp_path, monkeypatch=monkeypatch)

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 0

    assert len(respawns(fake=fake)) == 1
    command = respawns(fake=fake)[0][3]
    assert command.startswith(f"codex resume --dangerously-bypass-approvals-and-sandbox {SID} ")
    assert "claude" not in command
    assert f"started {repo}::{topic}" in capsys.readouterr().out
    assert [row.topic for row in registry.read_valid_mapping(store_path=None)] == [topic]


def test_start_refuses_a_topic_only_codex_namesake_before_creating_any_session(
    *, tmp_path, monkeypatch, capsys
):
    """A stale namesake is reported, and reported BEFORE a single tmux mutation."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=store
    )
    fake = FakeTmux()
    wire_start(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        fake=fake,
        codex_home=codex_home_with(tmp_path=tmp_path, topic=topic, session_id=SID),
    )

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 1

    err = capsys.readouterr().err
    assert "reason=ambiguous_runtime" in err
    assert "topic-only guess" in err
    assert not fake.has(method="new")
    assert not fake.has(method="respawn")


def test_start_refuses_a_recorded_codex_identity_with_no_surviving_rollout(
    *, tmp_path, monkeypatch, capsys
):
    repo, topic, _session, fake = codex_start(
        tmp_path=tmp_path, monkeypatch=monkeypatch, rollout=False
    )

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 1

    assert "reason=ambiguous_runtime" in capsys.readouterr().err
    assert not fake.has(method="new")
    assert not fake.has(method="respawn")


def test_start_keeps_the_claude_default_for_a_brand_new_mapped_plan(
    *, tmp_path, monkeypatch, capsys
):
    repo, topic = make_plan(tmp_path=tmp_path)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    fake = FakeTmux()
    fake.panes[registry.tmux_id(repo=str(repo), topic=topic)] = idle_capture()
    wire_start(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        fake=fake,
        codex_home=tmp_path / "no-codex-home",
    )

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 0

    assert " --dangerously-skip-permissions -n " in respawns(fake=fake)[0][3]
    assert f"started {repo}::{topic}" in capsys.readouterr().out
    assert len(registry.read_valid_mapping(store_path=store)) == 1


def test_start_keeps_claude_for_an_evidence_proven_claude_track(*, tmp_path, monkeypatch, capsys):
    """A `claude:` identity is proof, and it outranks a same-topic Codex index namesake."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    store = isolate_store(tmp_path=tmp_path, monkeypatch=monkeypatch)
    registry.append_mapping(
        track=dataclasses.replace(
            mapped_track(repo=repo, topic=topic, session=session),
            observed_session_identity=f"claude:{session}:{topic}",
        ),
        store_path=store,
    )
    fake = FakeTmux()
    fake.panes[session] = idle_capture()
    wire_start(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        fake=fake,
        codex_home=codex_home_with(tmp_path=tmp_path, topic=topic, session_id=SID),
    )

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 0

    assert " --dangerously-skip-permissions -n " in respawns(fake=fake)[0][3]
    assert f"started {repo}::{topic}" in capsys.readouterr().out


def test_start_does_not_report_a_codex_start_that_came_up_on_a_picker(
    *, tmp_path, monkeypatch, capsys
):
    repo, topic, _session, _fake = codex_start(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        capture="Resume a previous session\n\n› 1. Choose a session\n  2. Start a new\n",
    )

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 1

    assert "reason=codex_resume_picker" in capsys.readouterr().err


def test_start_does_not_report_a_codex_start_running_in_another_repository(
    *, tmp_path, monkeypatch, capsys
):
    repo, topic, _session, _fake = codex_start(
        tmp_path=tmp_path, monkeypatch=monkeypatch, live=(tmp_path / "somewhere-else", SID)
    )

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 1

    assert "reason=codex_live_process_missing" in capsys.readouterr().err


def test_start_does_not_report_a_codex_start_whose_resume_kick_never_submitted(
    *, tmp_path, monkeypatch, capsys
):
    repo, topic, _session, _fake = codex_start(
        tmp_path=tmp_path, monkeypatch=monkeypatch, capture=codex_idle_capture()
    )

    assert supervisor.main(argv=["start", "--repo", str(repo), "--topic", topic]) == 1

    assert "reason=codex_resume_kick_unconfirmed" in capsys.readouterr().err
