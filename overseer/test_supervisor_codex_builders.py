"""Extracted supervisor beside-test builders."""

import dataclasses
import json

import codex_sessions
import registry
from test_supervisor_capture_builders import codex_busy_capture, codex_idle_capture
from test_supervisor_core_builders import make_supervisor
from test_supervisor_fakes import FakeTmux
from test_supervisor_restart_builders import arm_ready_marker, on_respawn
from test_supervisor_store_builders import make_plan, mapped_track

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


def codex_home_with(*, tmp_path, topic, session_id, rollout=True, renamed_to=None):
    """A fake ~/.codex naming `session_id` for `topic`, optionally with its rollout on disk.

    `renamed_to` appends the SECOND record a `/rename <topic>` writes once a wrap-up
    restart has replaced that session with a fresh rollout. It carries a later
    `updated_at`, because "which rollout does this topic name NOW?" is the question the
    restart's naming proof asks, and the index answers it by recency.
    """
    home = tmp_path / "codex-home"
    home.mkdir(exist_ok=True)
    records = [(session_id, "2026-07-18T00:00:00Z")]
    if renamed_to is not None:
        records.append((renamed_to, "2026-07-18T00:01:00Z"))
    (home / "session_index.jsonl").write_text(
        "".join(
            json.dumps({"id": indexed, "thread_name": topic, "updated_at": updated}) + "\n"
            for indexed, updated in records
        ),
        encoding="utf-8",
    )
    if rollout:
        day = home / "sessions" / "2026" / "07" / "18"
        day.mkdir(parents=True)
        (day / f"rollout-2026-07-18T00-00-00-{session_id}.jsonl").write_text("{}\n")
    return home


def codex_dead_track(*, repo, topic, session, session_id):
    """A mapped row whose DURABLE `observed_session_identity` proves it ran Codex.

    The recorded identity is the only evidence a dead track's runtime may be established
    from; the index and the rollout merely corroborate it. A row without one is a
    topic-only guess and is refused, so every Codex recovery test builds its row here.
    """
    return dataclasses.replace(
        mapped_track(repo=repo, topic=topic, session=session),
        observed_session_identity=f"codex:{session_id}",
    )


def verify_codex_respawn(*, sup, fake, plan, session_id, capture=None, live=None):
    """Model a REAL `codex resume` landing: the process registers and the kick submits.

    ``plan`` is the ``(repo, topic, session)`` triple the track is mapped to. The verified
    recovery launcher reports success only on live process evidence matching the target
    session, topic, exact UUID and repository cwd, PLUS the pane going busy — the Codex
    submit-confirm signal. Both are what a genuinely resumed session supplies, so a test
    exercising the SUCCESS leg supplies both here.

    The two overrides model the near-misses that must NOT read as success: ``capture`` a
    pane that came up on a picker or sat idle, and ``live`` the ``(cwd, session_id)`` a
    process in another repository — or holding another rollout — would report.
    """
    repo, topic, session = plan
    frame = capture if capture is not None else codex_busy_capture()
    live_cwd, live_session_id = live if live is not None else (repo, session_id)
    on_respawn(fake=fake, after=lambda target: fake.panes.__setitem__(target, frame))

    def refresh_to_live_codex() -> None:
        sup.live_codex = {
            (session, topic): codex_sessions.CodexSession(
                pid=4242, name=topic, cwd=str(live_cwd), session_id=live_session_id
            )
        }

    sup._refresh_codex_sessions = refresh_to_live_codex


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


FRESH_CODEX_SESSION_ID = "019f7b2f-3771-7ad3-9fc3-26fda0435ca9"


def adopt_codex_ready(*, tmp_path):
    """A codex track adopted in `live_codex`, at a valid `ready`, on an idle Codex pane.

    The shared fixture for the restart-routing guards: a `bun` pane showing the real idle
    Codex shape, a live CodexSession in the map (as `_refresh_codex_sessions` builds each
    tick), and a genuinely-valid `ready` (stamp + newer marker) so evaluation reaches the
    restart branch — the branch where a runtime-misrouted restart would fire the claude
    command at a codex pane.

    Discovery is modelled ACROSS the respawn, because a wrap-up restart launches a FRESH
    Codex session rather than resuming the prior rollout. Before the respawn the topic
    resolves to the predecessor's rollout; afterwards it resolves to
    `FRESH_CODEX_SESSION_ID` — the successor the daemon's `/rename <topic>` made
    adoptable — which is exactly the id CHANGE the restart's post-respawn proof requires.

    The `session_index` is modelled the same way and for the same reason: the rename
    appends a DURABLE record for the successor, and that record — not the fd-gated live
    join — is what the restart confirms the name from while the successor is still idle.
    A test that wants the post-rename discovery gap itself drives its own index.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=codex_idle_capture(ctx=40), cmd="bun"
    )  # a codex pane
    fake.codex_busy_frame = codex_busy_capture(ctx=95)  # the fresh session takes the resume
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    session_id = "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={},
        starttimes={},
        codex_home=str(
            codex_home_with(
                tmp_path=tmp_path,
                topic=topic,
                session_id=session_id,
                rollout=False,
                renamed_to=FRESH_CODEX_SESSION_ID,
            )
        ),
    )

    def seeded_codex_session() -> None:
        respawned = any(call[0] == "respawn" for call in fake.calls)
        live_id = FRESH_CODEX_SESSION_ID if respawned else session_id
        sup.live_codex = {
            (session, topic): codex_sessions.CodexSession(
                pid=4242, name=topic, cwd=str(repo), session_id=live_id
            )
        }

    seeded_codex_session()
    sup._refresh_codex_sessions = seeded_codex_session
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
