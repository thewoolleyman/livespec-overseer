"""Hermetic launch-profile capture tests for the overseer supervisor."""

from __future__ import annotations

import contextlib
import importlib
import io as _io
import json

import registry
import signals
from test_supervisor_builders import (
    TEST_EPIC,
    adopt_sup,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    write_session,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _nul(*, argv: list[str]) -> bytes:
    return b"\0".join(part.encode() for part in argv) + b"\0"


def _env(*, values: dict[str, str]) -> bytes:
    return b"\0".join(f"{key}={value}".encode() for key, value in values.items()) + b"\0"


def _jsonl_rows(*, store):
    return [json.loads(line) for line in store.read_text().splitlines() if line.strip()]


def test_launch_profile_reader_is_public_to_supervisor_collaborators():
    module = importlib.import_module("_supervisor_launch_profile")

    assert hasattr(module, "read_launch_profile")


def test_reader_captures_local_claude_wrapper_from_exec_surviving_environ():
    module = importlib.import_module("_supervisor_launch_profile")

    assert hasattr(module, "read_launch_profile")
    profile = module.read_launch_profile(
        pid=200,
        harness="claude",
        pane_pid=100,
        cmdline_of=lambda *, pid: {
            200: _nul(argv=["claude", "--dangerously-skip-permissions"]),
            150: _nul(argv=["bash", "-lc", "claude-local-llm"]),
        }.get(pid),
        environ_of=lambda *, pid: {
            200: _env(
                values={
                    "ANTHROPIC_MODEL": "macmini/qwen3-coder-next",
                    "ANTHROPIC_BASE_URL": "http://127.0.0.1:11434",
                }
            )
        }.get(pid),
        ppid_of=lambda *, pid: {200: 150, 150: 100}.get(pid),
    )

    assert profile == {
        "harness": "claude",
        "model": "macmini/qwen3-coder-next",
        "wrapper": "/data/projects/local-llm/bin/claude-local-llm",
    }


def test_reader_captures_local_codex_wrapper_from_exec_surviving_environ():
    module = importlib.import_module("_supervisor_launch_profile")

    assert hasattr(module, "read_launch_profile")
    profile = module.read_launch_profile(
        pid=300,
        harness="codex",
        pane_pid=100,
        cmdline_of=lambda *, pid: {
            300: _nul(argv=["codex", "-m", "macmini/qwen3-coder-next"]),
            150: _nul(argv=["bash", "-lc", "codex-local-llm"]),
        }.get(pid),
        environ_of=lambda *, pid: {
            300: _env(
                values={
                    "ANTHROPIC_BASE_URL": "http://127.0.0.1:11434",
                }
            )
        }.get(pid),
        ppid_of=lambda *, pid: {300: 150, 150: 100}.get(pid),
    )

    assert profile == {
        "harness": "codex",
        "model": "macmini/qwen3-coder-next",
        "wrapper": "/data/projects/local-llm/bin/codex-local-llm",
    }


def test_adopt_sessions_persists_a_cloud_claude_launch_profile(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=200, name=topic, cwd=repo)
    fake = FakeTmux()
    fake.pane_pids = {100: topic}
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={200: 100},
        starttimes={200: "pt"},
        watch_repos=[str(repo)],
        cmdline_of=lambda *, pid: _nul(
            argv=["claude", "--model", "claude-opus-4-1-20250805", "-n", topic]
        )
        if pid == 200
        else None,
    )

    adopted = sup.adopt_sessions()

    assert [track.topic for track in adopted] == [topic]
    assert _jsonl_rows(store=tmp_path / "map.jsonl")[0]["model_profile"] == {
        "harness": "claude",
        "model": "claude-opus-4-1-20250805",
        "wrapper": None,
    }


def test_wrapup_rechecks_launch_profile_and_surfaces_statusline_mismatch(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=200, name=topic, cwd=repo)
    registry.append_mapping(
        track=registry.Track(
            topic=topic,
            repo=str(repo),
            tmux=session,
            epic=TEST_EPIC,
            model_profile={
                "harness": "claude",
                "model": "claude-opus-4-1-20250805",
                "wrapper": None,
            },
        ),
        store_path=tmp_path / "map.jsonl",
    )
    fake = FakeTmux()
    fake.serve(
        session=session,
        repo=repo,
        capture=idle_capture(ctx=40).replace("Opus 4.8", "Sonnet 4.5"),
    )
    fake.pane_pids = {100: session}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid_of=lambda *, pid: {200: 100}.get(pid),
        starttime_of=lambda *, pid: {200: "pt"}.get(pid),
        cmdline_of=lambda *, pid: _nul(
            argv=["claude", "--model=claude-sonnet-4-5-20250929", "-n", topic]
        )
        if pid == 200
        else None,
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "warned"
    assert "launch profile mismatch" in err.getvalue()
    assert _jsonl_rows(store=tmp_path / "map.jsonl")[0]["model_profile"] == {
        "harness": "claude",
        "model": "claude-sonnet-4-5-20250929",
        "wrapper": None,
    }
    assert signals.read_state(repo=str(repo), topic=topic) is None


def test_wrapup_statusline_display_name_does_not_mismatch_unchanged_launch_token(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=200, name=topic, cwd=repo)
    profile = {
        "harness": "claude",
        "model": "claude-opus-4-1-20250805",
        "wrapper": None,
    }
    registry.append_mapping(
        track=registry.Track(
            topic=topic,
            repo=str(repo),
            tmux=session,
            epic=TEST_EPIC,
            model_profile=profile,
        ),
        store_path=tmp_path / "map.jsonl",
    )
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    fake.pane_pids = {100: session}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid_of=lambda *, pid: {200: 100}.get(pid),
        starttime_of=lambda *, pid: {200: "pt"}.get(pid),
        cmdline_of=lambda *, pid: _nul(
            argv=["claude", "--model=claude-opus-4-1-20250805", "-n", topic]
        )
        if pid == 200
        else None,
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "warned"
    assert "launch profile mismatch" not in err.getvalue()
    assert _jsonl_rows(store=tmp_path / "map.jsonl")[0]["model_profile"] == profile


def test_wrapup_records_missing_profile_without_mismatch_alert(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=200, name=topic, cwd=repo)
    registry.append_mapping(
        track=registry.Track(topic=topic, repo=str(repo), tmux=session, epic=TEST_EPIC),
        store_path=tmp_path / "map.jsonl",
    )
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    fake.pane_pids = {100: session}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid_of=lambda *, pid: {200: 100}.get(pid),
        starttime_of=lambda *, pid: {200: "pt"}.get(pid),
        cmdline_of=lambda *, pid: _nul(
            argv=["claude", "--model=claude-opus-4-1-20250805", "-n", topic]
        )
        if pid == 200
        else None,
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "warned"
    assert "launch profile mismatch" not in err.getvalue()
    assert _jsonl_rows(store=tmp_path / "map.jsonl")[0]["model_profile"] == {
        "harness": "claude",
        "model": "claude-opus-4-1-20250805",
        "wrapper": None,
    }
