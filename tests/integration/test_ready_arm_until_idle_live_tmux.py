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
import subprocess
import textwrap
import threading
import time
from pathlib import Path

import pytest

import overseer._supervisor_restart as supervisor_restart
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

    def respawn_pane(
        self, *, session: str, cwd: str, command: str, env: object | None = None
    ) -> bool:
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

    def respawn_pane(
        self, *, session: str, cwd: str, command: str, env: object | None = None
    ) -> bool:
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


class PromptContractPaneDriver:
    """Real private tmux server plus a tiny scripted model process."""

    def __init__(self, *, inner: tmuxio.TmuxIO, repo: Path) -> None:
        self.inner = inner
        self.repo = repo
        self.pastes: list[tuple[str, str]] = []
        self.respawns: list[tuple[str, str, str]] = []

    def capture_pane(self, *, session: str) -> str:
        return self.inner.capture_pane(session=session)

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
        return self.inner.send_keys(session=session, keys=keys)

    def bracketed_paste(self, *, session: str, text: str) -> bool:
        self.pastes.append((session, text))
        return self.inner.bracketed_paste(session=session, text=text)

    def respawn_pane(
        self, *, session: str, cwd: str, command: str, env: object | None = None
    ) -> bool:
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


def _tmux_socket_name(*, tmp_path: Path) -> str:
    return f"ready-arm-{os.getpid()}-{tmp_path.name}"


def _tmux_socket_path(*, tmp_path: Path) -> Path:
    base = Path(os.environ.get("TMUX_TMPDIR", "/tmp"))
    return base / f"tmux-{os.getuid()}" / _tmux_socket_name(tmp_path=tmp_path)


def _tmux_wrapper(*, tmp_path: Path) -> Path:
    socket = _tmux_socket_name(tmp_path=tmp_path)
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


def test_ready_arm_real_tmux_rig_unlinks_its_private_socket(*, tmp_path: Path) -> None:
    """The live ready-arm rig must not leave one `ready-arm-*` socket per test.

    Measured 2026-08-19: 22,715 orphan rig sockets, oldest 2026-07-18. This
    cleanup names only the socket created by this fixture instance.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    inner = tmuxio.TmuxIO(tmux_bin=str(_tmux_wrapper(tmp_path=tmp_path)))
    before = int(_tmux_socket_path(tmp_path=tmp_path).exists())

    try:
        _session_with_capture(inner=inner, session=session, repo=repo, capture=idle_capture(ctx=5))
        assert int(_tmux_socket_path(tmp_path=tmp_path).exists()) == before + 1
    finally:
        _close_session(tmp_path=tmp_path)

    assert int(_tmux_socket_path(tmp_path=tmp_path).exists()) == before


def _replace_capture(*, inner: tmuxio.TmuxIO, session: str, repo: Path, capture: str) -> None:
    script = _render_script(repo=repo, capture=capture)
    assert inner.respawn_pane(session=session, cwd=str(repo), command=str(script))
    _await_rendered(inner=inner, session=session, capture=capture)


def _close_session(*, tmp_path: Path) -> None:
    subprocess.run(  # noqa: S603
        [str(_tmux_wrapper(tmp_path=tmp_path)), "kill-server"],
        capture_output=True,
        text=True,
        check=False,
    )
    _tmux_socket_path(tmp_path=tmp_path).unlink(missing_ok=True)


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
        status_path=str(tmp_path / "status.json"),
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
    sup.claude_identity_by_session = {(session, session): f"claude:{session}:{session}"}
    sup.refresh_claude_status = lambda: None
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
        status_path=str(tmp_path / "loop-status.json"),
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
    sup.claude_identity_by_session = {(session, session): f"claude:{session}:{session}"}
    sup.refresh_claude_status = lambda: None
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


def _open_tiny_context_round(
    *, sup: supervisor.Supervisor, driver: PromptContractPaneDriver
) -> None:
    view = sup.tick(act=True)[0]
    assert view.ctx == 5
    assert view.status in {"warned", "danger"}
    assert driver.pastes


def _assert_restart_diagnostic(*, repo: Path, topic: str, err: str) -> None:
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert state.token == signals.STATE_RESTARTED
    assert "restart completed" in state.detail
    assert err.count("consumed ready declaration") == 1


def _legacy_wrapup_message(*, remaining: int, repo: str, topic: str, epic: str | None) -> str:
    current = supervisor.wrapup_message(remaining=remaining, repo=repo, topic=topic, epic=epic)
    return current.replace(
        "Declare done, and stop. The command that declares ready is your FINAL act:",
        "Declare done, and stop:",
    ).replace(
        "\n\nAfter `overseer-declare ready`, stop immediately.\n"
        "if you are still in this conversation, no restart happened - never conclude otherwise.",
        "",
    )


def _tiny_context_tui_script(
    *, repo: Path, topic: str, transcript: Path, stop_after_ready: bool
) -> Path:
    state_file = signals.state_path(repo=str(repo), topic=topic)
    script = repo / "tmp" / "tiny-context-tui.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import sys
            import termios
            import time
            import tty
            from pathlib import Path

            RULE = {"─" * 40!r}
            HINT = {"  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents"!r}
            STATE_FILE = Path({str(state_file)!r})
            TRANSCRIPT = Path({str(transcript)!r})
            CRASH_LOG = TRANSCRIPT.with_suffix(".crash.log")
            STOP_AFTER_READY = {stop_after_ready!r}

            def record(line):
                TRANSCRIPT.parent.mkdir(parents=True, exist_ok=True)
                with TRANSCRIPT.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\\n")

            def render(composer=""):
                sys.stdout.write("\\033[2J\\033[H")
                sys.stdout.write("● prior response\\r\\n")
                sys.stdout.write(RULE + "\\r\\n")
                first_line = composer.splitlines()[0] if composer.splitlines() else ""
                sys.stdout.write("❯ " + first_line[:80] + "\\r\\n")
                sys.stdout.write(RULE + "\\r\\n")
                sys.stdout.write("  Opus 4.8 (1M context) | /x/repo | Ctx: 5% left\\r\\n")
                sys.stdout.write(HINT + "\\r\\n")
                sys.stdout.flush()

            def render_busy():
                sys.stdout.write("\\033[2J\\033[H")
                sys.stdout.write("● response\\r\\n")
                sys.stdout.write(
                    "✻ Galloping… (running stop hooks… 1/3 · 24s · ↓ 1.4k tokens)\\r\\n"
                )
                sys.stdout.write(RULE + "\\r\\n")
                sys.stdout.write("❯ \\r\\n")
                sys.stdout.write(RULE + "\\r\\n")
                sys.stdout.write("  Opus 4.8 (1M context) | /x/repo | Ctx: 5% left\\r\\n")
                sys.stdout.write(HINT + "\\r\\n")
                sys.stdout.flush()

            def declare(value):
                STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
                STATE_FILE.write_text(value + "\\n", encoding="utf-8")

            def act_on(prompt):
                record("overseer-declare winding-down")
                declare("winding-down")
                record("append sanctioned plan resume state")
                record("stop background processes")
                record("overseer-declare ready")
                declare("ready")
                if STOP_AFTER_READY:
                    return
                record("Restart completed; continuing with the next step.")

            def main():
                tty_in = open("/dev/tty", "r", encoding="utf-8", errors="ignore")
                old = termios.tcgetattr(tty_in)
                try:
                    tty.setraw(tty_in.fileno())
                    render()
                    buf = ""
                    while True:
                        ch = tty_in.read(1)
                        if not ch:
                            return
                        buf += ch
                        prompt = buf.replace("\\x1b[200~", "").replace("\\x1b[201~", "")
                        render(prompt)
                        if "write the file." not in prompt:
                            continue
                        while tty_in.read(1) not in ("\\r", "\\n"):
                            pass
                        act_on(prompt)
                        render_busy()
                        time.sleep(1.0)
                        render()
                        while True:
                            time.sleep(1.0)
                finally:
                    termios.tcsetattr(tty_in, termios.TCSADRAIN, old)
                    tty_in.close()

            try:
                main()
            except Exception as exc:
                CRASH_LOG.parent.mkdir(parents=True, exist_ok=True)
                CRASH_LOG.write_text(type(exc).__name__ + ": " + str(exc) + "\\n", encoding="utf-8")
                raise
            """
        ),
        encoding="utf-8",
    )
    script.chmod(0o700)
    return script


def _prompt_contract_fixture(
    *, tmp_path: Path, stop_after_ready: bool
) -> tuple[
    Path,
    str,
    str,
    tmuxio.TmuxIO,
    PromptContractPaneDriver,
    supervisor.Supervisor,
    Path,
]:
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    transcript = repo / "tmp" / "tiny-context-transcript.txt"
    tmux_bin = _tmux_wrapper(tmp_path=tmp_path)
    inner = tmuxio.TmuxIO(tmux_bin=str(tmux_bin))
    script = _tiny_context_tui_script(
        repo=repo, topic=topic, transcript=transcript, stop_after_ready=stop_after_ready
    )
    assert inner.new_session(name=session, cwd=str(repo))
    assert inner.respawn_pane(session=session, cwd=str(repo), command=str(script))
    _await_rendered(inner=inner, session=session, capture=idle_capture(ctx=5))
    driver = PromptContractPaneDriver(inner=inner, repo=repo)
    sup = _loop_supervisor(tmp_path=tmp_path, driver=driver, session=session, repo=repo)
    track = mapped_track(repo=repo, topic=topic, session=session)
    registry.append_mapping(
        track=track,
        store_path=sup.store_path,
        added_at="2026-08-17T00:00:00Z",
    )
    write_fresh_supervisor_state(repo=repo, topic=topic)
    sup.build_rows = lambda *, act=True: [track]
    return repo, topic, session, inner, driver, sup, transcript


def _read_transcript_until(*, path: Path, needle: str) -> list[str]:
    for _attempt in range(100):
        if path.exists():
            transcript = path.read_text(encoding="utf-8").splitlines()
            if needle in transcript:
                return transcript
        time.sleep(0.05)
    raise AssertionError(f"{needle!r} never appeared in {path}")


def _await_input_ready(*, driver: PromptContractPaneDriver, session: str) -> None:
    for _attempt in range(100):
        capture = driver.capture_pane(session=session)
        if signals.input_box_ready(capture_text=capture) and not signals.is_busy(
            capture_text=capture
        ):
            return
        time.sleep(0.05)
    raise AssertionError("tiny-context pane never returned to an idle input box")


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
        _close_session(tmp_path=tmp_path)


@pytest.mark.parametrize(
    ("use_legacy_prompt", "stop_after_ready"),
    [(True, False), (False, True)],
)
def test_wrapup_contract_drives_tiny_context_session_to_final_ready(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    use_legacy_prompt: bool,
    stop_after_ready: bool,
) -> None:
    if use_legacy_prompt:
        monkeypatch.setattr(supervisor_restart, "wrapup_message", _legacy_wrapup_message)
    repo, topic, session, inner, driver, sup, transcript_path = _prompt_contract_fixture(
        tmp_path=tmp_path, stop_after_ready=stop_after_ready
    )
    try:
        _open_tiny_context_round(sup=sup, driver=driver)
        transcript = _read_transcript_until(
            path=transcript_path,
            needle=(
                "Restart completed; continuing with the next step."
                if use_legacy_prompt
                else "overseer-declare ready"
            ),
        )

        if use_legacy_prompt:
            assert transcript[-1] == "Restart completed; continuing with the next step."
            assert transcript[-2] == "overseer-declare ready"
            return

        _await_input_ready(driver=driver, session=session)
        restarted = sup.evaluate(
            track=mapped_track(repo=repo, topic=topic, session=session), act=True
        )
        transcript = transcript_path.read_text(encoding="utf-8").splitlines()
        assert restarted.status == "restarting"
        assert driver.respawns
        assert transcript[-1] == "overseer-declare ready"
        assert transcript.count("overseer-declare ready") == 1
        assert "Restart completed; continuing with the next step." not in transcript
    finally:
        _close_session(tmp_path=tmp_path)


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
        err = _io.StringIO()
        with contextlib.redirect_stderr(err):
            restarted = sup.evaluate(track=track, act=True)

        assert restarted.status == "restarting"
        assert len(driver.respawns) == 1
        _assert_restart_diagnostic(repo=repo, topic=topic, err=err.getvalue())
    finally:
        _close_session(tmp_path=tmp_path)


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
        assert err.getvalue().count("expired ready declaration") == 1
        state = signals.read_state(repo=str(repo), topic=topic)
        assert state is not None
        assert state.token == signals.STATE_READY_EXPIRED
        assert "ready declaration exceeded" in state.detail
        assert len(driver.respawns) == 0
    finally:
        _close_session(tmp_path=tmp_path)
