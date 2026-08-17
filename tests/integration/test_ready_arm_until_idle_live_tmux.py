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
import time
from pathlib import Path

from overseer import _supervisor_config, registry, signals, supervisor, tmuxio
from overseer.test_supervisor_builders import (
    busy_capture,
    declare,
    idle_capture,
    make_plan,
    mapped_track,
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
    )
    sup.claude_status_by_session = {session: "idle"}
    return sup


def _live_track(
    *, tmp_path: Path, clock: dict[str, float], initial_ctx: int
) -> tuple[Path, str, str, tmuxio.TmuxIO, LivePaneDriver, supervisor.Supervisor, registry.Track]:
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    tmux_bin = _tmux_wrapper(tmp_path=tmp_path)
    inner = tmuxio.TmuxIO(tmux_bin=str(tmux_bin))
    _session_with_capture(
        inner=inner,
        session=session,
        repo=repo,
        capture=idle_capture(ctx=initial_ctx, topic=topic),
    )
    driver = LivePaneDriver(inner=inner, repo=repo)
    sup = _supervisor(tmp_path=tmp_path, driver=driver, clock=clock, session=session)
    track = mapped_track(repo=repo, topic=topic, session=session)
    return repo, topic, session, inner, driver, sup, track


def _replace_and_evaluate(
    *,
    inner: tmuxio.TmuxIO,
    session: str,
    repo: Path,
    capture: str,
    sup: supervisor.Supervisor,
    track: registry.Track,
) -> supervisor.RowView:
    _replace_capture(inner=inner, session=session, repo=repo, capture=capture)
    return sup.evaluate(track=track, act=True)


def _assert_downgraded_state(*, repo: Path, topic: str) -> None:
    downgraded = signals.read_state(repo=str(repo), topic=topic)
    assert downgraded is not None
    assert downgraded.token == signals.STATE_WINDING_DOWN
    assert downgraded.detail == "auto @1400"
    assert signals.state_path(repo=str(repo), topic=topic).read_text(encoding="utf-8") == (
        "winding-down: auto @1400\n"
    )


def test_ready_degrades_to_visible_winding_down_after_more_output(*, tmp_path: Path) -> None:
    clock = {"t": 1000.0}
    repo, topic, session, inner, driver, sup, track = _live_track(
        tmp_path=tmp_path, clock=clock, initial_ctx=30
    )
    try:
        assert sup.evaluate(track=track, act=True).status == "warned"
        declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1010.0)

        clock["t"] = 1400.0
        working = _replace_and_evaluate(
            inner=inner,
            session=session,
            repo=repo,
            capture=busy_capture(ctx=30),
            sup=sup,
            track=track,
        )
        assert working.status == "working"
        _assert_downgraded_state(repo=repo, topic=topic)

        clock["t"] = 1410.0
        armed_down = _replace_and_evaluate(
            inner=inner,
            session=session,
            repo=repo,
            capture=idle_capture(ctx=30, topic=topic),
            sup=sup,
            track=track,
        )
        assert armed_down.status == "winding-down"
        assert len(driver.respawns) == 0

        clock["t"] = 1400.0 + _supervisor_config.ACK_STALE_AFTER + 1.0
        rearmed = _replace_and_evaluate(
            inner=inner,
            session=session,
            repo=repo,
            capture=idle_capture(ctx=20, topic=topic),
            sup=sup,
            track=track,
        )
        assert rearmed.status == "danger"
        assert len(driver.pastes) == 2
        assert len(driver.respawns) == 0
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
