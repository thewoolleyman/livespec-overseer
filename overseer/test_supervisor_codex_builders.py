"""Extracted supervisor beside-test builders."""

import json

import codex_sessions
import registry
from test_supervisor_capture_builders import codex_idle_capture
from test_supervisor_core_builders import make_supervisor
from test_supervisor_fakes import FakeTmux
from test_supervisor_restart_builders import arm_ready_marker
from test_supervisor_store_builders import make_plan

__all__: list[str] = []

NUDGE_SENTINEL = "do NOT offer to stop"
TEST_EPIC = "overseer-test-epic"
RULE = "─" * 40
HINT = "  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents"
SPINNER = "✻ Galloping… (running stop hooks… 1/3 · 24s · ↓ 1.4k tokens)"
WRAPUP_SENTINEL = "Declare your state by writing ONE line"
GREEN = "\x1b[32m"
RESET = "\x1b[0m"
_ANCHORED_HANDOFF = f"HANDOFF v1\n\n**Ledger anchor:** `{TEST_EPIC}`\n".encode()


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


def adopt_sup(*, tmp_path, fake, sessions_dir, ppid, starttimes, **kwargs):
    return make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=str(sessions_dir),
        ppid_of=lambda *, pid: ppid.get(pid),
        starttime_of=lambda *, pid: starttimes.get(pid),
        **kwargs,
    )


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

    def keep_seeded_codex_session() -> None:
        sup.live_codex = {
            (session, topic): codex_sessions.CodexSession(
                pid=4242, name=topic, cwd=str(repo), session_id=session_id
            )
        }

    sup._refresh_codex_sessions = keep_seeded_codex_session
    assert sup._is_codex_track(
        session=session, repo=str(repo), topic=topic, target=session
    )  # the precondition holds
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=f"codex:{session_id}",
        stamp_path=sup.stamp_path,
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
