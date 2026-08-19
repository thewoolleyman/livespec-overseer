"""Edge coverage for launch-profile capture helpers."""

from __future__ import annotations

import contextlib
import io as _io

import _claude_sessions_proc
import _supervisor_discovery
import _supervisor_launch_profile_refresh
import registry
from _supervisor_launch_profile import (
    LaunchProfileProblem,
    read_launch_profile,
    rendered_statusline_model,
)
from _supervisor_launch_profile_sources import CodexProfileReaders, live_profile_sources
from test_codex_sessions_fakes import ID_A, fake_host, fake_index, fake_rollout
from test_supervisor_builders import idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def _nul(*, argv: list[str]) -> bytes:
    return b"\0".join(part.encode() for part in argv) + b"\0"


def _env(*, values: dict[str, str]) -> bytes:
    return b"\0".join(f"{key}={value}".encode() for key, value in values.items()) + b"\0"


def test_proc_environ_returns_bytes_and_empty_as_none(*, monkeypatch):
    class FakePath:
        def __init__(self, _path):
            self.calls = 0

        def read_bytes(self):
            self.calls += 1
            return b"ANTHROPIC_MODEL=claude-opus\0" if self.calls else b""

    fake_path = FakePath
    monkeypatch.setattr(_claude_sessions_proc, "Path", fake_path)

    assert _claude_sessions_proc.proc_environ(pid=123) == b"ANTHROPIC_MODEL=claude-opus\0"


def test_proc_environ_unreadable_is_none(*, monkeypatch):
    class FakePath:
        def __init__(self, _path):
            pass

        def read_bytes(self):
            raise OSError

    monkeypatch.setattr(_claude_sessions_proc, "Path", FakePath)

    assert _claude_sessions_proc.proc_environ(pid=123) is None


def test_reader_uses_parent_wrapper_for_custom_local_harness_and_reports_missing_model(*, tmp_path):
    wrapper = str(tmp_path / "pi-local-llm")
    profile = read_launch_profile(
        pid=300,
        harness="pi",
        pane_pid=100,
        cmdline_of=lambda *, pid: {
            300: _nul(argv=["pi"]),
            200: _nul(argv=["bash", "-lc", "exec wrapper"]),
            150: _nul(argv=[wrapper]),
        }.get(pid),
        environ_of=lambda *, pid: _env(
            values={
                "ANTHROPIC_MODEL": "macmini/qwen3-coder-next",
                "ANTHROPIC_BASE_URL": "http://localhost:11434",
            }
        )
        if pid == 300
        else None,
        ppid_of=lambda *, pid: {300: 200, 200: 150, 150: 100}.get(pid),
    )

    assert profile == {"harness": "pi", "model": "macmini/qwen3-coder-next", "wrapper": wrapper}
    assert isinstance(
        read_launch_profile(
            pid=400,
            harness="claude",
            pane_pid=None,
            cmdline_of=lambda *, pid: _nul(argv=["claude"]) if pid == 400 else None,
            environ_of=lambda *, pid: b"",
            ppid_of=lambda *, pid: None,
        ),
        LaunchProfileProblem,
    )
    assert rendered_statusline_model(capture="body without a footer") is None


def test_reader_handles_short_model_flag_malformed_env_and_cloud_wrapper():
    profile = read_launch_profile(
        pid=300,
        harness="codex",
        pane_pid=100,
        cmdline_of=lambda *, pid: _nul(argv=["codex", "-m", "gpt-5-codex"]) if pid == 300 else None,
        environ_of=lambda *, pid: b"BROKEN\0" if pid == 300 else None,
        ppid_of=lambda *, pid: {300: 100}.get(pid),
    )

    assert profile == {"harness": "codex", "model": "gpt-5-codex", "wrapper": None}


def test_reader_prefers_exec_surviving_wrapper_env_marker():
    profile = read_launch_profile(
        pid=300,
        harness="claude",
        pane_pid=100,
        cmdline_of=lambda *, pid: _nul(argv=["claude"]) if pid == 300 else None,
        environ_of=lambda *, pid: _env(
            values={
                "ANTHROPIC_MODEL": "macmini/qwen3",
                "ANTHROPIC_BASE_URL": "http://localhost:11434",
                "LIVESPEC_LOCAL_LLM_WRAPPER": "/opt/local/bin/custom-claude",
            }
        )
        if pid == 300
        else None,
        ppid_of=lambda *, pid: {300: 100}.get(pid),
    )

    assert profile == {
        "harness": "claude",
        "model": "macmini/qwen3",
        "wrapper": "/opt/local/bin/custom-claude",
    }


def test_reader_stops_parent_walk_on_seen_cycle_and_depth_limit():
    cycle_profile = read_launch_profile(
        pid=300,
        harness="pi",
        pane_pid=None,
        cmdline_of=lambda *, pid: _nul(argv=["bash"]) if pid in {200, 300} else None,
        environ_of=lambda *, pid: _env(
            values={
                "ANTHROPIC_MODEL": "macmini/qwen3",
                "ANTHROPIC_BASE_URL": "http://localhost:11434",
            }
        )
        if pid == 300
        else None,
        ppid_of=lambda *, pid: {300: 200, 200: 300}.get(pid),
    )
    deep_profile = read_launch_profile(
        pid=500,
        harness="pi",
        pane_pid=None,
        cmdline_of=lambda *, pid: _nul(argv=["bash"]) if pid != 500 else _nul(argv=["pi"]),
        environ_of=lambda *, pid: _env(
            values={
                "ANTHROPIC_MODEL": "macmini/qwen3",
                "ANTHROPIC_BASE_URL": "http://localhost:11434",
            }
        )
        if pid == 500
        else None,
        ppid_of=lambda *, pid: pid - 1 if 436 <= pid <= 500 else None,
    )

    assert cycle_profile == {"harness": "pi", "model": "macmini/qwen3", "wrapper": None}
    assert deep_profile == {"harness": "pi", "model": "macmini/qwen3", "wrapper": None}


def test_profile_for_adoption_without_a_source_is_none(*, tmp_path):
    fake = FakeTmux()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)

    assert _supervisor_discovery._profile_for_adoption(sup=sup, source=None) is None


def test_wrapup_refresh_without_source_and_with_unreadable_profile(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    track = mapped_track(repo=repo, topic=topic, session=session)

    _supervisor_launch_profile_refresh.refresh_launch_profile_at_wrapup(
        sup=sup,
        track=track,
        target=session,
        capture=idle_capture(ctx=40),
    )

    fake.pane_pids = {100: session}
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "200.json").write_text(
        f'{{"pid": 200, "name": "topic", "cwd": "{repo}", "procStart": "pt"}}',
        encoding="utf-8",
    )
    sup.sessions_dir = str(sessions_dir)
    sup.ppid_of = lambda *, pid: {200: 100}.get(pid)
    sup.starttime_of = lambda *, pid: {200: "pt"}.get(pid)
    sup.cmdline_of = lambda *, pid: _nul(argv=["claude"]) if pid == 200 else None
    sup.environ_of = lambda *, pid: b""
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        _supervisor_launch_profile_refresh.refresh_launch_profile_at_wrapup(
            sup=sup,
            track=track,
            target=session,
            capture=idle_capture(ctx=40),
        )

    assert "launch profile for pid 200 has no model token" in err.getvalue()


def test_wrapup_refresh_uses_track_profile_and_skips_unchanged_store_write(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "200.json").write_text(
        f'{{"pid": 200, "name": "{topic}", "cwd": "{repo}", "procStart": "pt"}}',
        encoding="utf-8",
    )
    profile = {"harness": "claude", "model": "claude-opus-4-1-20250805", "wrapper": None}
    registry.append_mapping(
        track=registry.Track(topic=topic, repo=str(repo), tmux=session, model_profile=profile),
        store_path=tmp_path / "map.jsonl",
    )
    fake = FakeTmux()
    fake.pane_pids = {100: session}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir)
    sup.ppid_of = lambda *, pid: {200: 100}.get(pid)
    sup.starttime_of = lambda *, pid: {200: "pt"}.get(pid)
    sup.cmdline_of = lambda *, pid: _nul(argv=["claude", "--model=claude-opus-4-1-20250805"])
    sup.environ_of = lambda *, pid: b""

    _supervisor_launch_profile_refresh.refresh_launch_profile_at_wrapup(
        sup=sup,
        track=registry.Track(topic=topic, repo=str(repo), tmux=session, model_profile=profile),
        target=session,
        capture=idle_capture(ctx=40),
    )

    assert registry.read_mapping(store_path=tmp_path / "map.jsonl")[0].model_profile == profile


def test_codex_profile_source_skips_live_session_outside_tmux(*, tmp_path):
    codex_home = fake_index(tmp_path=tmp_path, records=[(ID_A, "topic")])
    host = fake_host(
        comms={300: "codex"},
        cwds={300: "/repo"},
        fds={300: [fake_rollout(session_id=ID_A)]},
    )

    assert (
        live_profile_sources(
            sessions_dir=tmp_path / "missing-claude-sessions",
            pane_pid_to_session={},
            ppid_of=lambda *, pid: None,
            starttime_of=lambda *, pid: None,
            codex_readers=CodexProfileReaders(codex_home=codex_home, **host),
        )
        == {}
    )
