"""Lane D pair-stall detection and supervisor nudge ladder."""

import contextlib
import io as _io

import pytest
import registry
import signals
from test_supervisor_builders import (
    busy_capture,
    codex_idle_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

PAIR_NUDGE_SENTINEL = "Your worker/supervisor pair has shown no progress"
PAIR_FAILED_SENTINEL = "autonomous supervisor nudge already failed"
PAIR_FLOOR = 2 * 60 * 60


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def paired_supervisor(*, tmp_path, worker_capture, supervisor_capture, now):
    repo, topic = make_plan(tmp_path=tmp_path)
    (repo / "plan" / topic / "supervisor-handoff.md").write_text("supervise this\n")
    worker_session = registry.tmux_id(repo=str(repo), topic=topic)
    supervisor_session = signals.supervisor_entity_topic(topic=worker_session)
    fake = FakeTmux()
    fake.serve(session=worker_session, repo=repo, capture=worker_capture)
    fake.serve(session=supervisor_session, repo=repo, capture=supervisor_capture)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)], now=now)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=worker_session),
        store_path=sup.store_path,
    )
    return sup, fake, repo, topic, worker_session, supervisor_session


def pair_nudge_count(*, fake):
    return len([text for text in fake.paste_texts() if PAIR_NUDGE_SENTINEL in text])


def test_pair_stall_is_content_immune_and_escalates_after_second_nudged_episode(*, tmp_path):
    """A Claude supervisor full of pasted spinner text still counts as no-progress when
    its registry status is only shell, so the pair nudges once and then reports after
    the second consecutive nudged episode."""
    clock = {"t": 1000.0}
    spinner_text_pasted_by_supervisor = busy_capture(ctx=77)
    sup, fake, _repo, _topic, worker_session, supervisor_session = paired_supervisor(
        tmp_path=tmp_path,
        worker_capture=idle_capture(ctx=82),
        supervisor_capture=spinner_text_pasted_by_supervisor,
        now=lambda: clock["t"],
    )
    sup.claude_status_by_session = {
        worker_session: "idle",
        supervisor_session: "shell",
    }

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        _ = sup.tick(act=True)
        clock["t"] += PAIR_FLOOR + 1
        _ = sup.tick(act=True)
        assert pair_nudge_count(fake=fake) == 1
        clock["t"] += 1
        _ = sup.tick(act=True)  # the nudge-answering turn counts as supervisor progress
        clock["t"] += PAIR_FLOOR + 1
        _ = sup.tick(act=True)
        clock["t"] += PAIR_FLOOR + 1
        _ = sup.tick(act=True)

    assert pair_nudge_count(fake=fake) == 1
    assert PAIR_FAILED_SENTINEL in err.getvalue()
    assert supervisor_session in err.getvalue()
    assert worker_session in err.getvalue()


def test_worker_progress_resets_consecutive_nudged_episode_ladder(*, tmp_path):
    clock = {"t": 1000.0}
    sup, fake, _repo, _topic, worker_session, supervisor_session = paired_supervisor(
        tmp_path=tmp_path,
        worker_capture=idle_capture(ctx=82),
        supervisor_capture=idle_capture(ctx=77),
        now=lambda: clock["t"],
    )
    sup.claude_status_by_session = {
        worker_session: "idle",
        supervisor_session: "idle",
    }

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        _ = sup.tick(act=True)
        clock["t"] += PAIR_FLOOR + 1
        _ = sup.tick(act=True)
        assert pair_nudge_count(fake=fake) == 1
        fake.panes[worker_session] = idle_capture(ctx=81)  # worker ctx movement is real progress
        clock["t"] += 1
        _ = sup.tick(act=True)
        fake.panes[worker_session] = idle_capture(ctx=81)
        clock["t"] += PAIR_FLOOR + 1
        _ = sup.tick(act=True)

    assert pair_nudge_count(fake=fake) == 2
    assert PAIR_FAILED_SENTINEL not in err.getvalue()


@pytest.mark.parametrize(
    ("name", "mutate"),
    [
        pytest.param(
            "identity",
            lambda *, fake, supervisor_session, repo: fake.cmds.__setitem__(
                supervisor_session, "zsh"
            ),
            id="identity",
        ),
        pytest.param(
            "toctou",
            lambda *, fake, supervisor_session, repo: fake.cmds.__setitem__(
                supervisor_session, ["node", "zsh"]
            ),
            id="toctou",
        ),
        pytest.param(
            "settled",
            lambda *, fake, supervisor_session, repo: fake.panes.__setitem__(
                supervisor_session,
                [
                    idle_capture(ctx=77, body="one"),
                    idle_capture(ctx=77, body="two"),
                    idle_capture(ctx=77, body="three"),
                ],
            ),
            id="settled",
        ),
        pytest.param(
            "gate",
            lambda *, fake, supervisor_session, repo: fake.panes.__setitem__(
                supervisor_session,
                "│ Do you want to proceed?\n│ ❯ 1. Yes\n│   2. No\n  Ctx: 77% left\n",
            ),
            id="gate",
        ),
        pytest.param(
            "open-round",
            lambda *, fake, supervisor_session, repo: registry.write_injection_stamp(
                repo=str(repo),
                topic=signals.supervisor_entity_topic(topic="topic"),
                ts=1000.0,
                stamp_path=fake.stamp_path,
            ),
            id="open-round",
        ),
    ],
)
def test_pair_nudge_composes_each_act_guard(*, tmp_path, name, mutate):
    clock = {"t": 1000.0}
    sup, fake, repo, _topic, worker_session, supervisor_session = paired_supervisor(
        tmp_path=tmp_path,
        worker_capture=idle_capture(ctx=82),
        supervisor_capture=idle_capture(ctx=77),
        now=lambda: clock["t"],
    )
    fake.stamp_path = sup.stamp_path
    sup.claude_status_by_session = {
        worker_session: "idle",
        supervisor_session: "idle",
    }
    mutate(fake=fake, supervisor_session=supervisor_session, repo=repo)

    with contextlib.redirect_stderr(_io.StringIO()):
        _ = sup.tick(act=True)
        clock["t"] += PAIR_FLOOR + 1
        _ = sup.tick(act=True)

    assert pair_nudge_count(fake=fake) == 0, name


def test_codex_supervisor_is_not_pair_nudged(*, tmp_path):
    clock = {"t": 1000.0}
    sup, fake, _repo, _topic, worker_session, supervisor_session = paired_supervisor(
        tmp_path=tmp_path,
        worker_capture=idle_capture(ctx=82),
        supervisor_capture=idle_capture(ctx=77),
        now=lambda: clock["t"],
    )
    fake.cmds[supervisor_session] = "bun"
    fake.panes[supervisor_session] = codex_idle_capture(ctx=77, topic=supervisor_session)
    sup.claude_status_by_session = {worker_session: "idle"}

    with contextlib.redirect_stderr(_io.StringIO()):
        _ = sup.tick(act=True)
        clock["t"] += PAIR_FLOOR + 1
        _ = sup.tick(act=True)

    assert pair_nudge_count(fake=fake) == 0


def test_pair_human_wait_suppresses_nudge(*, tmp_path):
    clock = {"t": 1000.0}
    sup, fake, repo, topic, worker_session, supervisor_session = paired_supervisor(
        tmp_path=tmp_path,
        worker_capture=idle_capture(ctx=82),
        supervisor_capture=idle_capture(ctx=77),
        now=lambda: clock["t"],
    )
    declare(repo=repo, topic=topic, value="blocked: needs maintainer")
    sup.claude_status_by_session = {
        worker_session: "idle",
        supervisor_session: "idle",
    }

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        _ = sup.tick(act=True)
        clock["t"] += PAIR_FLOOR + 1
        _ = sup.tick(act=True)

    assert pair_nudge_count(fake=fake) == 0
    assert "needs maintainer" in err.getvalue()
