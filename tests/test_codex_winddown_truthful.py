"""Codex wind-down prompt truthfulness regression."""

import contextlib
import io as _io

import _supervisor_prompts as prompts
import codex_sessions
import registry
import signals
from test_supervisor_builders import (
    adopt_sup,
    codex_busy_capture,
    codex_idle_capture,
    make_plan,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_prompt_builder_public_branches_stay_covered(*, tmp_path) -> None:
    repo = str(tmp_path / "repo")
    worker = registry.Track(topic="worker", repo=repo, tmux="worker", epic="overseer-epic")
    supervisor = registry.Track(
        topic=signals.supervisor_entity_topic(topic="worker"),
        repo=repo,
        tmux="worker-supervisor",
        epic="overseer-epic",
    )
    no_epic = registry.Track(topic="missing", repo=repo, tmux="missing", epic=None)

    assert prompts.plan_state_locator(repo=repo, epic=None)
    assert prompts.plan_state_locator(repo=repo, epic="overseer-epic")
    assert prompts.plan_epic_resume(repo=repo, epic="overseer-epic")
    assert prompts.resume_for_track(track=worker)
    assert prompts.resume_for_track(track=supervisor)
    assert prompts.resume_for_track(track=no_epic) is None
    assert prompts.launch_resume(track=worker)
    assert prompts.launch_resume(track=no_epic)
    assert "STOP AND WIND DOWN NOW" in prompts.wrapup_message(
        remaining=20, repo=repo, topic="worker", epic="overseer-epic"
    )
    worker_wrap = prompts.wrapup_message(
        remaining=40, repo=repo, topic="worker", epic="overseer-epic"
    )
    assert "Writing that line is the declaration" in worker_wrap
    assert "Pane text" in worker_wrap
    assert "never a declaration channel" in worker_wrap
    assert "Writing that line is the declaration" in prompts.supervisor_wrapup_message(
        remaining=40, repo=repo, topic="worker"
    )
    assert "Writing that line is the declaration" in prompts.expiry_notice_message(
        repo=repo,
        topic="worker",
    )
    assert "NO plan epic id is recorded" in prompts.wrapup_message(
        remaining=40, repo=repo, topic="worker", epic=None
    )
    assert prompts.supervisor_handoff_path(repo=repo, topic="worker")
    assert prompts.supervisor_resume(repo=repo, topic="worker")
    assert prompts.supervisor_wrapup_message(remaining=40, repo=repo, topic="worker")
    assert prompts.idle_nudge_message(
        remaining=60, threshold=50, repo=repo, topic="worker", epic="overseer-epic"
    )
    assert prompts.supervisor_idle_nudge_message(
        remaining=60, threshold=50, repo=repo, topic="worker"
    )
    assert prompts.pair_stall_nudge_message(
        repo=repo,
        topic="worker",
        epic=None,
        worker_session="worker",
        worker_pane=None,
        stalled_seconds=3600,
    )


def test_codex_low_context_wrapup_discloses_same_rollout_resume(*, tmp_path) -> None:
    test_prompt_builder_public_branches_stay_covered(tmp_path=tmp_path)
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session,
        repo=repo,
        capture=[codex_idle_capture(ctx=40)] * 4 + [codex_busy_capture(ctx=40)],
        cmd="bun",
    )
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sup = adopt_sup(tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir, ppid={}, starttimes={})
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=4242,
            name=topic,
            cwd=str(repo),
            session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8",
        )
    }

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "warned"
    text = " ".join(fake.paste_texts())
    assert "reattaches this same Codex rollout" in text
    assert "fresh session" not in text
