"""Track builders, pane captures and assertion helpers for the `supervisor` beside-tests.

The companion to `test_supervisor_fakes`, which holds the tmux/tty doubles themselves.
Split from it because the two together crossed the 200-LLOC soft band, which hard-fails
a RELEASE via `check-no-lloc-soft-warnings`.

No tests live here; see `test_supervisor_fakes` for why the `test_` prefix and the
public member names are both load-bearing.
"""

import io as _io
import json
import os

import _registry_core
import _supervisor_config
import codex_sessions
import registry
import signals
import supervisor
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

# A phrase unique to the idle-with-context-left "keep going" nudge (never in the wrap-up).
NUDGE_SENTINEL = "do NOT offer to stop"


# The REAL live Claude TUI idle shape (verified 2026-07-13): an empty `❯` prompt
# between two horizontal rule lines, the statusline as the SECOND-to-last row,
# and a footer hint as the LAST row (NOT a `╭─╮` box + `? for shortcuts`).
RULE = "─" * 40
HINT = "  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents"
# The real active-generation spinner (a token counter / dot-elapsed / hook phase);
# the lingering completed-turn summary "✻ Brewed for 25s" is deliberately NOT busy.
SPINNER = "✻ Galloping… (running stop hooks… 1/3 · 24s · ↓ 1.4k tokens)"


def idle_capture(*, ctx=None, body="", topic=None):
    """The idle box. ``topic`` renders the `-n <topic>` TITLED top border (B2)."""
    status = "  Opus 4.8 (1M context) | /x/repo"
    if ctx is not None:
        status += f" | Ctx: {ctx}% left"
    head = f"● {body}\n" if body else "● prior response\n"
    top = RULE if topic is None else ("─" * 30) + f" {topic} ──"
    return f"{head}{top}\n❯ \n{RULE}\n{status}\n{HINT}\n"


def busy_capture(*, ctx=None):
    """An actively-generating pane: the real spinner above the (idle-shaped) box."""
    return f"● response\n{SPINNER}\n" + idle_capture(ctx=ctx)


# The REAL live idle Codex TUI shape (verified 2026-07-17, codex-cli 0.144.5): a `›`
# input line above the Codex statusline `model · cwd · Context N% left · <name>` — NOT
# Claude's empty-`❯`-between-rules box. An UNNAMED session shows its UUID where a named
# one shows the thread_name; here we render the topic (a named session).
def codex_idle_capture(*, ctx=None, topic="topic"):
    status = "  gpt-5.5 high · /x/repo"
    if ctx is not None:
        status += f" · Context {ctx}% left"
    status += f" · {topic}"
    return f"● prior response\n› Write tests for @filename\n{status}\n"


def codex_busy_capture(*, ctx=None):
    """An actively-generating Codex pane: `esc to interrupt` (what `is_busy` matches) —
    the signal `_submit_prompt(expect_codex=True)` confirms a Codex submit by."""
    status = "  gpt-5.5 high · /x/repo"
    if ctx is not None:
        status += f" · Context {ctx}% left"
    return f"● response\n◦ Working (1s • esc to interrupt)\n› Write tests for @filename\n{status}\n"


# Legacy alias kept for readability in tests that predate the real-shape fixtures.
IDLE_BOX = idle_capture()


def make_plan(*, tmp_path, repo_name="repo", topic="topic", handoff=b"HANDOFF v1\n"):
    repo = tmp_path / repo_name
    plan = repo / "plan" / topic
    plan.mkdir(parents=True)
    (plan / "handoff.md").write_bytes(handoff)
    return repo, topic


def mapped_track(*, repo, topic, session):
    return registry.Track(
        topic=topic,
        repo=str(repo),
        tmux=session,
        handoff=supervisor.default_handoff(repo=str(repo), topic=topic),
        resume=supervisor.default_resume(repo=str(repo), topic=topic),
    )


def key_for(*, repo, topic):
    """The normalized in-memory inject-state key the supervisor uses."""
    return _supervisor_config.track_key(repo=str(repo), topic=topic)


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
    kwargs.setdefault("codex_pids_of_comm", lambda _comm: [])
    # Hermetic host preconditions: present them as SUPPORTED so no test depends on the
    # RUNNER having tmux (or a /proc). Without these defaults the `run()` startup gate
    # would fail every existing run() test on a container without tmux installed — the
    # same host-coupling hazard the codex seams above already close. A
    # precondition-behavior test overrides them to simulate an unsupported host.
    kwargs.setdefault("proc_root", str(tmp_path))  # any existing dir reads as "has /proc"
    kwargs.setdefault("which", lambda _name: "/usr/bin/tmux")
    return supervisor.Supervisor(
        tmux=fake,
        store_path=str(tmp_path / "map.jsonl"),
        stamp_path=str(tmp_path / "stamps.json"),
        **kwargs,
    )


# A phrase from the SHARED wrap-up body, so it matches BOTH tones (the gentle
# suggestion at 50/40 and the insistent shutdown demand at 30/20/10).
WRAPUP_SENTINEL = "Declare your state by writing ONE line"


def adopt_sup(*, tmp_path, fake, sessions_dir, ppid, starttimes, **kwargs):
    return make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=str(sessions_dir),
        ppid_of=ppid.get,
        starttime_of=starttimes.get,
        **kwargs,
    )


def arm_ready_marker(*, repo, topic, mtime=1001.0):
    """The session declares `ready` — the ONLY thing that authorizes a restart."""
    return declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=mtime)


def assert_no_tmux_scoping(*, command):
    """The L1 env inversion is REMOVED (plan/tmux-fleet-visibility): a spawn
    command must carry NO tmux socket scoping, so a bare `tmux ls` in the
    spawned agent lists the real fleet. This pins the ABSENCE so the prefix
    cannot silently regress."""
    assert "TMUX_TMPDIR" not in command
    assert "unset TMUX" not in command


# --------------------------------------------------------------------------- #
# Reboot recovery is runtime-dispatched (defect #5): a dead track whose TOPIC names a
# session in the persistent codex index is a CODEX track — resumed via `codex resume <id>`
# (option c) when its rollout survives, else skip+surface (option b), NEVER recreated as
# Claude. A topic absent from the index is a Claude track and recovers as before.
# --------------------------------------------------------------------------- #


def codex_home_with(*, tmp_path, topic, session_id, rollout=True):
    """A fake ~/.codex naming `session_id` for `topic`, optionally with its rollout on disk."""
    home = tmp_path / "codex-home"
    home.mkdir(exist_ok=True)
    (home / "session_index.jsonl").write_text(
        json.dumps({"id": session_id, "thread_name": topic, "updated_at": "2026-07-18T00:00:00Z"})
        + "\n",
        encoding="utf-8",
    )
    if rollout:
        day = home / "sessions" / "2026" / "07" / "18"
        day.mkdir(parents=True)
        (day / f"rollout-2026-07-18T00-00-00-{session_id}.jsonl").write_text("{}\n")
    return home


# --------------------------------------------------------------------------- #
# Restart interlock: fires ONLY on marker-valid + not-busy + idle; deletes marker.
# --------------------------------------------------------------------------- #


def declare(*, repo, topic, value, mtime=1001.0):
    """Write the session's ONE state file with ``value`` (e.g. "ready", "blocked: x").

    The single indicator lives at ``<repo>/tmp/overseer/<topic>/.overseer-state`` — its
    parent dir does not exist yet, so create it. One file with a VALUE: there is no way
    to be simultaneously `ready` and `blocked`, which is the whole point.
    """
    path = signals.state_path(repo=str(repo), topic=topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{value}\n")
    os.utime(path, (mtime, mtime))
    return path


# --------------------------------------------------------------------------- #
# CLI mapping edits.
# --------------------------------------------------------------------------- #


def isolate_store(*, tmp_path, monkeypatch):
    """Redirect the hard-coded mapping store at a tmp file.

    The de-gold-plated CLI (2026-07-13) no longer exposes ``--store``; the path is
    fixed to ``registry.DEFAULT_STORE_PATH``. Tests point that module default at a
    tmp file so a CLI ``main([...])`` never writes into the developer's real
    ``~/.livespec-overseer.jsonl``.
    """
    store = tmp_path / "map.jsonl"
    # Patch the module that DEFINES the default and RESOLVES it. `_store()` reads
    # `DEFAULT_STORE_PATH` as a bare module global, so patching the `registry` facade
    # would set an attribute nothing reads and let this CLI test append to the
    # developer's real ~/.livespec-overseer.jsonl.
    monkeypatch.setattr(_registry_core, "DEFAULT_STORE_PATH", store)
    # `add`/`start` now consult the real fleet manifest to detect cross-repo topic
    # collisions (for the single-dash prefix). Neutralize that read by default so a
    # CLI test is hermetic and never flakes on the host's actual fleet; a collision
    # test overrides this with its own set.
    monkeypatch.setattr(supervisor, "_cli_colliding", lambda: frozenset())
    return store


def nudge_count(*, fake):
    return len([t for t in fake.paste_texts() if NUDGE_SENTINEL in t])


# --------------------------------------------------------------------------- #
# Panes that vanish or never come up. Every step of an act is a hard gate: an
# unresolvable pane, a respawn whose pane never becomes the expected runtime, and
# a fresh TUI sitting on a gate all STOP the act with the declaration preserved.
# --------------------------------------------------------------------------- #


def on_respawn(*, fake, after):
    """Run ``after(session)`` right after a SUCCESSFUL FakeTmux respawn.

    Models what the pane actually BECOMES once the respawn lands — a bare shell (the
    launch never came up), or a fresh TUI that opened on a trust/update gate.
    """
    inner = fake.respawn_pane

    def respawn(*, session, cwd, command):
        landed = inner(session=session, cwd=cwd, command=command)
        if landed:
            after(session)
        return landed

    fake.respawn_pane = respawn


# --------------------------------------------------------------------------- #
# The `NEEDS YOU` attention block (the daemon owns "what needs attention?").
#
# The bottom pane is an LLM: it prints text ONCE and that text then ages silently,
# so it reported tracks that had been resolved for minutes. Current state therefore
# belongs to the daemon's re-rendered table, which is free and cannot go stale.
# --------------------------------------------------------------------------- #


def render_of(*, sup, views):
    """Render VIEWS and return what the daemon printed (the table + attention block)."""
    sup.render(rows=views)
    return sup.out.getvalue()


def row_line(*, out, topic):
    """The single rendered line for TOPIC (the data row, not the header)."""
    return next(ln for ln in out.splitlines() if topic in ln and "Topic" not in ln)


# --------------------------------------------------------------------------- #
# R1 — self-healing resume-submit (2026-07-18). A freshly-respawned Claude can
# DROP the resume line's Enter while still drawing its welcome screen (proven live
# 2026-07-17: fabro / autonomous-mode / overseer-rewrite all stranded this way in
# one day). The old code cleared the `ready` marker and logged "restarted" anyway,
# so the daemon never retried and the session sat idle with an un-run handoff. Now
# the daemon KEEPS the round open, marks `resume_pending`, and retries the SUBMIT
# ONLY (re-send Enter, never a re-respawn) until the box clears.
# --------------------------------------------------------------------------- #


def unsubmitted_resume_capture(*, ctx=30):
    """A freshly-respawned Claude with the resume line sitting UN-submitted in the box.

    The box holds the pasted `read <handoff> and follow it` text (a `❯ read …` line between
    rules), so it is NOT the empty idle box (`input_box_ready` False) and NOT busy — exactly
    the stranded state a dropped Enter leaves."""
    status = "  Opus 4.8 (1M context) | /x/repo"
    if ctx is not None:
        status += f" | Ctx: {ctx}% left"
    return (
        f"● welcome\n{RULE}\n❯ read /x/repo/plan/topic/handoff.md and follow it\n"
        f"{RULE}\n{status}\n{HINT}\n"
    )


def wrapup_count(*, fake):
    return len([t for t in fake.paste_texts() if WRAPUP_SENTINEL in t])


# --------------------------------------------------------------------------- #
# adopt: pick up live Claude sessions by their registry name (~/.claude/sessions).
# --------------------------------------------------------------------------- #


def write_session(*, sessions_dir, pid, name, cwd, proc_start="pt", status="idle"):
    payload = {"pid": pid, "name": name, "cwd": str(cwd), "procStart": proc_start, "status": status}
    (sessions_dir / f"{pid}.json").write_text(json.dumps(payload), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Row color: the operator scans the live table by hue. Green = working, yellow =
# idle/waiting-on-human, red = broken, default (uncolored) = unassigned. Color is
# TTY-only, so it never corrupts piped `list` output or the beside-tests' plain
# StringIO — the render gates on `out.isatty()`.
# --------------------------------------------------------------------------- #

GREEN = "\x1b[32m"

RESET = "\x1b[0m"


def adopt_codex_ready(*, tmp_path):
    """A codex track adopted in `live_codex`, at a valid `ready`, on an idle Codex pane.

    The shared fixture for the two restart-routing guards below: a `bun` pane showing the
    real idle Codex shape, a live CodexSession in the map (as `_refresh_codex_sessions`
    builds each tick), and a genuinely-valid `ready` (stamp + newer marker) so evaluation
    reaches the restart branch — the branch where a runtime-misrouted restart would fire
    the claude command at a codex pane.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=codex_idle_capture(ctx=40), cmd="bun"
    )  # a codex pane
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sup = adopt_sup(tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir, ppid={}, starttimes={})
    session_id = "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=4242, name=topic, cwd=str(repo), session_id=session_id
        )
    }
    assert sup._is_codex_track(
        session=session, repo=str(repo), topic=topic, target=session
    )  # the precondition holds
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)  # the SOLE restart authorization
    return repo, topic, session, session_id, fake, sup


# --------------------------------------------------------------------------- #
# The `tmux` column annotates the session name with its RUNTIME — `livespec
# (claude)` / `livespec1 (codex)` — so the operator can tell at a glance whether a
# track is a Claude or a Codex session (maintainer 2026-07-18). Only a row with a
# LIVE MANAGED pane carries a runtime; the no-managed-pane rows (`unassigned` /
# `session-gone` / `live-outside-tmux`) render a bare `—` with no `(...)`. The
# annotation is part of the CELL, so the column width is computed from it and
# alignment holds.
# --------------------------------------------------------------------------- #


def cell_row(*, out, topic):
    """The single rendered DATA line for TOPIC (skipping the header row)."""
    return next(ln for ln in out.splitlines() if topic in ln and "Topic" not in ln)


# --------------------------------------------------------------------------- #
# Fail-soft marker I/O. The state file is written by the SESSION and read by the
# daemon, so every marker read/write/delete can fail on a tick (a directory in
# the file's place, an unwritable marker dir). Each failure must be LOGGED and
# the surrounding decision left in its safe default — never raised out of the
# tick, which would strand every other track the daemon is supervising.
# --------------------------------------------------------------------------- #


def undeletable_state_file(*, repo, topic):
    """Put a DIRECTORY where the ``.overseer-state`` file belongs.

    ``unlink`` on a directory always fails (``EISDIR``) for every user including
    root, so this models an undeletable marker without a chmod the CI container
    (which runs as root) would ignore.
    """
    path = signals.state_path(repo=str(repo), topic=topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir()
    return path
