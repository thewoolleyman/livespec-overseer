"""Tests for the ``overseer-declare`` session declaration CLI."""

from __future__ import annotations

import importlib
import io as _io
import os
import shlex
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from overseer import registry, signals, supervisor, tmuxio
from overseer.test_supervisor_builders import idle_capture, make_plan, mapped_track

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent


def assert_overseer_declare_shipped() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'overseer-declare = "overseer.declare:main"' in pyproject


def test_overseer_declare_ready_is_a_shipped_console_script() -> None:
    assert_overseer_declare_shipped()


def test_overseer_declare_ready_writes_state_and_prints_terminal_contract(*, tmp_path, capsys):
    assert_overseer_declare_shipped()
    module = importlib.import_module("overseer.declare")
    repo = tmp_path / "repo"
    topic = "handoff-thread"
    repo.mkdir()

    code = module.main(argv=["ready", "--repo", str(repo), "--topic", topic])

    assert code == 0
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert capsys.readouterr().out == (
        "restart armed - any further output cancels/downgrades this; you will know it "
        "worked because this conversation ends.\n"
    )


def test_overseer_declare_ready_infers_topic_from_tmux_session(*, tmp_path, monkeypatch):
    assert_overseer_declare_shipped()
    module = importlib.import_module("overseer.declare")
    repo = tmp_path / "repo"
    topic = "mapped-thread"
    repo.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("TMUX_PANE", "%9")

    class FakeTmux:
        def pane_session_name(self, *, pane: str) -> str | None:
            assert pane == "%9"
            return topic

    code = module.main(argv=["ready"], tmux=FakeTmux())

    assert code == 0
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY


def test_overseer_declare_ready_wakes_state_file_fast_path(*, tmp_path):
    module = importlib.import_module("overseer.declare")
    state_watch = importlib.import_module("_supervisor_state_watch")
    repo, topic = make_plan(tmp_path=tmp_path)
    store = tmp_path / "map.jsonl"
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=topic),
        store_path=store,
    )
    sup = SimpleNamespace(
        store_path=str(store),
        watch_repos=[str(repo)],
        watch_set_path=None,
        sleep=lambda _seconds: None,
    )
    state_path = signals.state_path(repo=str(repo), topic=topic)
    woke: list[bool] = []
    waiter = threading.Thread(
        target=lambda: woke.append(state_watch.wait_for_state_declaration(sup=sup, interval=5.0))
    )

    waiter.start()
    for _attempt in range(200):
        if state_path.parent.exists():
            break
        time.sleep(0.01)
    assert module.main(argv=["ready", "--repo", str(repo), "--topic", topic]) == 0
    waiter.join(timeout=3.0)

    assert woke == [True]


class DeclaredPaneDriver:
    """Real private tmux pane plus CI-safe runtime identity evidence."""

    def __init__(self, *, inner: tmuxio.TmuxIO, repo: Path, topic: str) -> None:
        self.inner = inner
        self.repo = repo
        self.topic = topic
        self.respawns: list[tuple[str, str, str]] = []

    def capture_pane(self, *, session: str) -> str:
        visible = self.inner.capture_pane(session=session)
        return f"{visible}\n{idle_capture(ctx=5, topic=self.topic)}"

    def pane_id(self, *, session: str) -> str | None:
        return self.inner.pane_id(session=session)

    def pane_pid(self, *, session: str) -> int | None:
        return self.inner.pane_pid(session=session)

    def pane_current_command(self, *, session: str) -> str | None:
        if session.startswith("%") or self.inner.session_exists(session=session):
            return "node"
        return None

    def pane_current_path(self, *, session: str) -> str | None:
        if session.startswith("%") or self.inner.session_exists(session=session):
            return str(self.repo)
        return None

    def session_exists(self, *, session: str) -> bool:
        return self.inner.session_exists(session=session)

    def pane_pid_sessions(self) -> dict[int, str]:
        return self.inner.pane_pid_sessions()

    def send_keys(self, *, session: str, keys: str) -> bool:
        return True

    def bracketed_paste(self, *, session: str, text: str) -> bool:
        return True

    def respawn_pane(self, *, session: str, cwd: str, command: str) -> bool:
        self.respawns.append((session, cwd, command))
        return self.inner.respawn_pane(
            session=session,
            cwd=cwd,
            command="bash --noprofile --norc",
        )

    def new_session(self, *, name: str, cwd: str) -> bool:
        return self.inner.new_session(name=name, cwd=cwd)

    def rename_window(self, *, pane: str, name: str) -> bool:
        return self.inner.rename_window(pane=pane, name=name)


def _supervisor(
    *, tmp_path: Path, driver: DeclaredPaneDriver, session: str
) -> supervisor.Supervisor:
    sup = supervisor.Supervisor(
        tmux=driver,
        store_path=str(tmp_path / "map.jsonl"),
        stamp_path=str(tmp_path / "stamps.json"),
        now=time.time,
        sleep=lambda _seconds: None,
        out=_io.StringIO(),
        codex_home=str(tmp_path / "codex-home-none"),
        codex_pids_of_comm=lambda *, comm: [],
        proc_root=str(tmp_path),
        which=lambda _name: "/usr/bin/tmux",
        gitignore_check=lambda *, repo: True,
    )
    sup.claude_status_by_session = {session: "idle"}
    return sup


def _tmux_wrapper(*, tmp_path: Path) -> Path:
    socket = f"declare-{os.getpid()}-{tmp_path.name}"
    wrapper = tmp_path / "tmux-private"
    wrapper.write_text(f'#!/bin/sh\nexec /usr/bin/tmux -L {socket} "$@"\n', encoding="utf-8")
    wrapper.chmod(0o700)
    return wrapper


def _await_rendered(*, inner: tmuxio.TmuxIO, session: str, capture: str) -> None:
    for _attempt in range(200):
        current = signals.strip_ansi(text=inner.capture_pane(session=session))
        if capture in current:
            return
        time.sleep(0.05)
    raise AssertionError(f"pane {session} never rendered {capture!r}")


def _close_session(*, inner: tmuxio.TmuxIO, session: str, repo: Path) -> None:
    inner.respawn_pane(session=session, cwd=str(repo), command="true")


def test_fake_session_cli_prints_contract_and_restarts_in_real_supervisor_loop(*, tmp_path):
    assert_overseer_declare_shipped()
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    tmux_bin = _tmux_wrapper(tmp_path=tmp_path)
    inner = tmuxio.TmuxIO(tmux_bin=str(tmux_bin))
    command = (
        f"PYTHONPATH={shlex.quote(str(ROOT))} "
        f"{shlex.quote(str(ROOT / '.venv' / 'bin' / 'python'))} "
        f"-m overseer.declare ready --repo {shlex.quote(str(repo))} "
        f"--topic {shlex.quote(topic)}"
    )
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=time.time() - 1.0,
        stamp_path=str(tmp_path / "stamps.json"),
    )
    try:
        assert inner.new_session(name=session, cwd=str(repo))
        assert inner.respawn_pane(
            session=session,
            cwd=str(repo),
            command=f"bash --noprofile --norc -lc {shlex.quote(command + '; sleep 60')}",
        )
        _await_rendered(
            inner=inner,
            session=session,
            capture="restart armed - any further output cancels/downgrades this",
        )
        driver = DeclaredPaneDriver(inner=inner, repo=repo, topic=topic)
        sup = _supervisor(tmp_path=tmp_path, driver=driver, session=session)
        track = mapped_track(repo=repo, topic=topic, session=session)
        registry.append_mapping(
            track=track,
            store_path=sup.store_path,
            added_at="2026-08-17T00:00:00Z",
        )

        rendered = signals.strip_ansi(text=driver.capture_pane(session=session))
        assert "restart armed - any further output cancels/downgrades this" in rendered
        restarted = sup.evaluate(track=track, act=True)

        assert restarted.status == "restarting"
        assert driver.respawns
    finally:
        _close_session(inner=inner, session=session, repo=repo)
