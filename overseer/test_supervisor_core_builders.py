"""Core supervisor beside-test builders."""

import io as _io

import signals
import supervisor

__all__: list[str] = []


def make_supervisor(*, tmp_path, fake, **kwargs):
    kwargs.setdefault("out", _io.StringIO())
    kwargs.setdefault("now", lambda: 1000.0)  # overridable: pass now=lambda: clock["t"]
    kwargs.setdefault("sleep", lambda _s: None)
    # Hermetic Codex discovery by default (#6): an empty `/proc` scan + a non-existent
    # `~/.codex` so adopt/refresh touch NO real host state, and the suite stays green with
    # a live codex on the host. With `pids_of_comm` returning [], the fd/cwd readers are
    # never reached, so they need no fake. A codex-behavior test overrides these to inject
    # a simulated session (see test_refresh_and_adopt_route_codex_through_injected_seams).
    kwargs.setdefault("codex_home", str(tmp_path / "codex-home-none"))
    kwargs.setdefault("codex_pids_of_comm", lambda *, comm: [])
    # Hermetic host preconditions: present them as SUPPORTED so no test depends on the
    # RUNNER having tmux (or a /proc). Without these defaults the `run()` startup gate
    # would fail every existing run() test on a container without tmux installed — the
    # same host-coupling hazard the codex seams above already close. A
    # precondition-behavior test overrides them to simulate an unsupported host.
    kwargs.setdefault("proc_root", str(tmp_path))  # any existing dir reads as "has /proc"
    kwargs.setdefault("which", lambda _name: "/usr/bin/tmux")
    kwargs.setdefault("status_path", str(tmp_path / "status.json"))
    sup = supervisor.Supervisor(
        tmux=fake,
        store_path=str(tmp_path / "map.jsonl"),
        stamp_path=str(tmp_path / "stamps.json"),
        **kwargs,
    )
    sup.claude_status_by_session = {
        session: "idle"
        for session in fake.sessions
        if isinstance(command := fake.cmds.get(session), str)
        and signals.pane_is_claude(pane_current_command=command)
    }

    def refresh_claude_status() -> None:
        sup.claude_identity_by_session = {
            (session, session): f"claude:{session}:{session}"
            for session in fake.sessions
            if isinstance(command := fake.cmds.get(session), str)
            and signals.pane_is_claude(pane_current_command=command)
        }

    refresh_claude_status()
    sup.refresh_claude_status = refresh_claude_status
    return sup


# A phrase from the SHARED wrap-up body, so it matches BOTH tones (the gentle
# suggestion at 50/40 and the insistent shutdown demand at 30/20/10).
WRAPUP_SENTINEL = "Declare your state by writing ONE line"
