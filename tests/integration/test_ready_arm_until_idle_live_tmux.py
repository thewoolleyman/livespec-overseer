"""Live-tmux integration coverage for ready arming until settled idle.

The test drives the real Supervisor decision cascade against a private tmux
server. The pane content is a deterministic miniature TUI transcript with a
tiny-context statusline, and the process-identity read is shimmed because CI has
no real Claude/Codex TUI to run.
"""

from __future__ import annotations

import contextlib
import io as _io
import os
import threading
import time
from pathlib import Path

from overseer import registry, signals, supervisor, tmuxio
from overseer.test_supervisor_builders import (
    busy_capture,
    declare,
    idle_capture,
    make_plan,
    mapped_track,
    write_fresh_supervisor_state,
)


class LivePaneDriver:
    """Real private tmux server plus CI-safe runtime identity evidence."""

    def __init__(self, *, inner: tmuxio.TmuxIO, repo: Path) -> None:
        self.inner = inner
        self.repo = repo
        self.pastes: list[tuple[str, str]] = []
        self.respawns: list[tuple[str, str, str]] = []
        self.pasted_text: str | None = None
        self.submitted = False

    def capture_pane(self, *, session: str) -> str:
        capture = self.inner.capture_pane(session=session)
        if self.pasted_text is not None and not self.submitted:
            return idle_capture(ctx=5).replace("\n❯ \n", f"\n❯ {self.pasted_text}\n", 1)
        if self.submitted:
            self.pasted_text = None
            self.submitted = False
            return busy_capture(ctx=5)
        return capture

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
        if keys == "Enter" and self.pasted_text is not None:
            self.submitted = True
        return True

    def bracketed_paste(self, *, session: str, text: str) -> bool:
        self.pastes.append((session, text))
        self.pasted_text = text.splitlines()[0]
        self.submitted = False
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


class RacePaneDriver:
    """Real private tmux server plus a scripted declaration/narration race."""

    def __init__(self, *, inner: tmuxio.TmuxIO, repo: Path, capture: str) -> None:
        self.inner = inner
        self.repo = repo
        self.capture = capture
        self.pastes: list[tuple[str, str]] = []
        self.respawns: list[tuple[str, str, str, float]] = []
        self.pasted_text: str | None = None
        self.submitted = False

    def capture_pane(self, *, session: str) -> str:
        if self.pasted_text is not None and not self.submitted:
            return self.capture.replace("\n❯ \n", f"\n❯ {self.pasted_text}\n", 1)
        if self.submitted:
            self.pasted_text = None
            self.submitted = False
        return self.capture

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
        if keys == "Enter" and self.pasted_text is not None:
            self.submitted = True
        return True

    def bracketed_paste(self, *, session: str, text: str) -> bool:
        self.pastes.append((session, text))
        self.pasted_text = text.splitlines()[0]
        self.submitted = False
        return True

    def respawn_pane(self, *, session: str, cwd: str, command: str) -> bool:
        self.respawns.append((session, cwd, command, time.monotonic()))
        return self.inner.respawn_pane(
            session=session,
            cwd=cwd,
            command="bash --noprofile --norc",
        )

    def new_session(self, *, name: str, cwd: str) -> bool:
        return self.inner.new_session(name=name, cwd=cwd)

    def rename_window(self, *, pane: str, name: str) -> bool:
        return self.inner.rename_window(pane=pane, name=name)


def _tmux_wrapper(*, tmp_path: Path) -> Path:
    socket = f"ready-arm-{os.getpid()}-{tmp_path.name}"
    wrapper = tmp_path / "tmux-private"
    wrapper.write_text(f'#!/bin/sh\nexec /usr/bin/tmux -L {socket} "$@"\n', encoding="utf-8")
    wrapper.chmod(0o700)
    return wrapper


def _render_script(*, repo: Path, capture: str) -> Path:
    script = repo / "tmp" / "render-capture.sh"
    payload = repo / "tmp" / "capture.txt"
    script.parent.mkdir(parents=True, exist_ok=True)
    payload.write_text(capture, encoding="utf-8")
    script.write_text(
        f"#!/bin/sh\nclear\ncat {payload}\nexec bash --noprofile --norc\n",
        encoding="utf-8",
    )
    script.chmod(0o700)
    return script


def _await_rendered(*, inner: tmuxio.TmuxIO, session: str, capture: str) -> None:
    """Block until the pane has finished rendering `capture` and stopped changing.

    `respawn_pane` returns as soon as tmux has replaced the process, not when that
    process has written its screen. The supervisor's own settle gate cannot absorb
    that gap here, because these tests stub `sleep` to a no-op — so `pane_settled`
    would compare two captures taken microseconds apart while `clear` + `cat` are
    still in flight and correctly report a CHANGING pane, leaving the tick at
    `settling` instead of the state under test. Waiting here removes the race
    without weakening a single production gate.
    """
    expected = [line.strip() for line in signals.strip_ansi(text=capture).splitlines()]
    wanted = [line for line in expected if line]
    previous: str | None = None
    for _attempt in range(200):
        current = signals.strip_ansi(text=inner.capture_pane(session=session))
        if all(line in current for line in wanted) and current == previous:
            return
        previous = current
        time.sleep(0.05)
    raise AssertionError(f"pane {session} never settled on the rendered capture")


def _session_with_capture(*, inner: tmuxio.TmuxIO, session: str, repo: Path, capture: str) -> None:
    script = _render_script(repo=repo, capture=capture)
    assert inner.new_session(name=session, cwd=str(repo))
    assert inner.respawn_pane(session=session, cwd=str(repo), command=str(script))
    _await_rendered(inner=inner, session=session, capture=capture)


def _replace_capture(*, inner: tmuxio.TmuxIO, session: str, repo: Path, capture: str) -> None:
    script = _render_script(repo=repo, capture=capture)
    assert inner.respawn_pane(session=session, cwd=str(repo), command=str(script))
    _await_rendered(inner=inner, session=session, capture=capture)


def _close_session(*, inner: tmuxio.TmuxIO, session: str, repo: Path) -> None:
    inner.respawn_pane(session=session, cwd=str(repo), command="true")


def _supervisor(
    *,
    tmp_path: Path,
    driver: LivePaneDriver,
    clock: dict[str, float],
    session: str,
) -> supervisor.Supervisor:
    sup = supervisor.Supervisor(
        tmux=driver,
        store_path=str(tmp_path / "map.jsonl"),
        stamp_path=str(tmp_path / "stamps.json"),
        now=lambda: clock["t"],
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


def _loop_supervisor(
    *,
    tmp_path: Path,
    driver: RacePaneDriver,
    session: str,
    repo: Path,
) -> supervisor.Supervisor:
    sup = supervisor.Supervisor(
        tmux=driver,
        store_path=str(tmp_path / "map.jsonl"),
        stamp_path=str(tmp_path / "stamps.json"),
        watch_repos=[str(repo)],
        now=time.time,
        out=_io.StringIO(),
        codex_home=str(tmp_path / "codex-home-none"),
        codex_pids_of_comm=lambda *, comm: [],
        proc_root=str(tmp_path),
        which=lambda _name: "/usr/bin/tmux",
        gitignore_check=lambda *, repo: True,
    )
    sup.claude_status_by_session = {session: "idle"}
    return sup


def _append_narration(*, driver: RacePaneDriver) -> None:
    if driver.respawns:
        return
    driver.capture = driver.capture.replace("● prior response", "● narrated after ready")


def _race_fixture(
    *, tmp_path: Path
) -> tuple[Path, str, str, tmuxio.TmuxIO, RacePaneDriver, supervisor.Supervisor, str]:
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    tmux_bin = _tmux_wrapper(tmp_path=tmp_path)
    inner = tmuxio.TmuxIO(tmux_bin=str(tmux_bin))
    capture = idle_capture(ctx=40, topic=topic)
    _session_with_capture(inner=inner, session=session, repo=repo, capture=capture)
    driver = RacePaneDriver(inner=inner, repo=repo, capture=capture)
    sup = _loop_supervisor(tmp_path=tmp_path, driver=driver, session=session, repo=repo)
    track = mapped_track(repo=repo, topic=topic, session=session)
    registry.append_mapping(
        track=track,
        store_path=sup.store_path,
        added_at="2026-08-17T00:00:00Z",
    )
    write_fresh_supervisor_state(repo=repo, topic=topic)

    def build_rows(*, act: bool = True) -> list[registry.Track]:
        return [track]

    sup.build_rows = build_rows
    return repo, topic, session, inner, driver, sup, capture


def _loop_until_second_tick(
    *, sup: supervisor.Supervisor
) -> tuple[threading.Event, threading.Event, threading.Thread]:
    first_tick_done = threading.Event()
    loop_finished = threading.Event()
    original_tick = sup.tick
    tick_count = {"value": 0}

    def tick(*, act: bool = True) -> list[supervisor.RowView]:
        views = original_tick(act=act)
        tick_count["value"] += 1
        first_tick_done.set()
        if tick_count["value"] >= 2:
            raise KeyboardInterrupt
        return views

    def run_loop() -> None:
        sup.run(interval=10.0, once=False, recover=False)
        loop_finished.set()

    sup.tick = tick
    loop = threading.Thread(target=run_loop)
    loop.daemon = True
    loop.start()
    return first_tick_done, loop_finished, loop


def _open_warning_round(*, sup: supervisor.Supervisor) -> None:
    for _attempt in range(3):
        if sup.tick(act=True)[0].status == "warned":
            return
    raise AssertionError("supervisor did not open a warning round")


def _script_tiny_context_wrapup(*, prompt: str) -> list[str]:
    transcript = [
        "overseer-declare winding-down",
        "append sanctioned plan resume state",
        "stop background processes",
        "overseer-declare ready",
    ]
    has_final_act_rule = "ready is your FINAL act" in prompt
    has_anti_confabulation_rule = (
        "if you are still in this conversation, no restart happened - never conclude otherwise"
        in prompt
    )
    if not (has_final_act_rule and has_anti_confabulation_rule):
        transcript.append("Restart completed; continuing with the next step.")
    return transcript


def test_state_file_event_wakes_daemon_before_next_narration_turn(*, tmp_path: Path) -> None:
    repo, topic, session, inner, driver, sup, _capture = _race_fixture(tmp_path=tmp_path)
    try:
        _open_warning_round(sup=sup)
        first_tick_done, loop_finished, loop = _loop_until_second_tick(sup=sup)
        assert first_tick_done.wait(timeout=5.0)
        time.sleep(0.3)
        declared_at = time.monotonic()
        declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=time.time())
        narrator = threading.Timer(2.0, _append_narration, kwargs={"driver": driver})
        narrator.start()
        try:
            assert loop_finished.wait(timeout=5.0)
        finally:
            narrator.cancel()
            loop.join(timeout=1.0)

        assert driver.respawns
        assert driver.respawns[0][3] - declared_at < 1.0
        rendered = signals.strip_ansi(text=driver.capture_pane(session=session))
        assert "narrated after ready" not in rendered
    finally:
        _close_session(inner=inner, session=session, repo=repo)


def test_wrapup_contract_makes_ready_the_scripted_session_final_act(*, tmp_path: Path) -> None:
    repo, topic, session, inner, driver, sup, _capture = _race_fixture(tmp_path=tmp_path)
    try:
        _open_warning_round(sup=sup)
        assert len(driver.pastes) == 1
        _target, prompt = driver.pastes[0]

        transcript = _script_tiny_context_wrapup(prompt=prompt)
        declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=time.time())
        restarted = sup.evaluate(
            track=mapped_track(repo=repo, topic=topic, session=session), act=True
        )

        assert restarted.status == "restarting"
        assert driver.respawns
        assert transcript[-1] == "overseer-declare ready"
        assert transcript.count("overseer-declare ready") == 1
        assert "Restart completed; continuing with the next step." not in transcript
    finally:
        _close_session(inner=inner, session=session, repo=repo)


def test_ready_arms_restart_until_first_verified_idle_after_more_output(*, tmp_path: Path) -> None:
    clock = {"t": 1000.0}
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    tmux_bin = _tmux_wrapper(tmp_path=tmp_path)
    inner = tmuxio.TmuxIO(tmux_bin=str(tmux_bin))
    try:
        _session_with_capture(
            inner=inner,
            session=session,
            repo=repo,
            capture=idle_capture(ctx=5, topic=topic),
        )
        driver = LivePaneDriver(inner=inner, repo=repo)
        sup = _supervisor(
            tmp_path=tmp_path,
            driver=driver,
            clock=clock,
            session=session,
        )
        track = mapped_track(repo=repo, topic=topic, session=session)

        opened = sup.evaluate(track=track, act=True)
        assert opened.status == "danger"
        declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)

        clock["t"] = 1400.0
        _replace_capture(
            inner=inner,
            session=session,
            repo=repo,
            capture=busy_capture(ctx=5),
        )
        assert sup.evaluate(track=track, act=True).status == "working"
        assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY

        clock["t"] = 1410.0
        _replace_capture(
            inner=inner,
            session=session,
            repo=repo,
            capture=idle_capture(ctx=5, topic=topic),
        )
        restarted = sup.evaluate(track=track, act=True)

        assert restarted.status == "restarting"
        assert len(driver.respawns) == 1
    finally:
        _close_session(inner=inner, session=session, repo=repo)


def test_ready_arm_max_age_expires_loudly_without_respawning(*, tmp_path: Path) -> None:
    clock = {"t": 1000.0}
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    tmux_bin = _tmux_wrapper(tmp_path=tmp_path)
    inner = tmuxio.TmuxIO(tmux_bin=str(tmux_bin))
    try:
        _session_with_capture(
            inner=inner,
            session=session,
            repo=repo,
            capture=idle_capture(ctx=5, topic=topic),
        )
        driver = LivePaneDriver(inner=inner, repo=repo)
        sup = _supervisor(
            tmp_path=tmp_path,
            driver=driver,
            clock=clock,
            session=session,
        )
        track = mapped_track(repo=repo, topic=topic, session=session)

        assert sup.evaluate(track=track, act=True).status == "danger"
        declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)
        clock["t"] = 1010.0 + 1800.0 + 1.0

        err = _io.StringIO()
        with contextlib.redirect_stderr(err):
            expired = sup.evaluate(track=track, act=True)

        assert expired.status == "ready-uncertifiable"
        assert "ready declaration exceeded 30m max age" in (expired.note or "")
        assert "ready cannot certify" in err.getvalue()
        assert len(driver.respawns) == 0
    finally:
        _close_session(inner=inner, session=session, repo=repo)
