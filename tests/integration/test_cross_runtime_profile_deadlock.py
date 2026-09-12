"""The stale-Claude-profile / bare-Codex / usable-state-database deadlock.

Measured live 2026-09-12 (`overseer-phz7te`) on a Codex pane whose mapping row still
carried its predecessor's Claude profile. Three defects compounded:

1. the wrap-up profile refresh reported ``has no model token`` for the BARE Codex
   carrier and gave up, because the rejection ran before the exact-identity
   ``threads.model`` row it was entitled to could be read;
2. nothing else re-read the profile inside an already-open round, so the Codex restart
   arm refused 95 times over half an hour with ``harness 'claude' cannot relaunch a
   Codex track``;
3. the evaluator compared the stale CLAUDE baseline against the CODEX statusline, called
   the inevitable cross-runtime disagreement a standing statusline veto, and suspended
   ready expiry — so the row reported its declaration too old while keeping the same
   declaration forever.

These tests drive the whole arc against a genuine on-disk SQLite state database and the
real restart arm: capture, self-heal, the successor restart that follows it, the
fail-closed branch when the database has no usable token, and the expiry lifecycle that
must now run to completion on a cross-runtime row.
"""

from __future__ import annotations

import contextlib
import io as _io
import json
import sqlite3

import _supervisor_launch_profile_refresh as refresh
import codex_sessions
import registry
import signals
from test_supervisor_builders import (
    TEST_EPIC,
    adopt_sup,
    arm_ready_marker,
    codex_busy_capture,
    codex_idle_capture,
    make_plan,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

CARRIER_PID = 2914615
PANE_PID = 7001
SESSION_ID = "01a08bff-a75e-75a1-bb61-209e13ac8994"
FRESH_SESSION_ID = "019f7b2f-3771-7ad3-9fc3-26fda0435ca9"
READY_MAX_AGE = 1800.0

# The mapping row as the incident found it: a prior CLAUDE profile, rendered baseline and
# all, standing on a track whose pane is now running Codex.
STALE_CLAUDE_PROFILE: dict[str, str | None] = {
    "harness": "claude",
    "model": "claude-opus-4-8[1m]",
    "statusline_model": "Opus 4.8 (1M context)",
    "wrapper": None,
}


def _codex_home(*, tmp_path, topic, model):
    home = tmp_path / "codex-home"
    home.mkdir(exist_ok=True)
    (home / "session_index.jsonl").write_text(
        "".join(
            json.dumps({"id": indexed, "thread_name": topic, "updated_at": updated}) + "\n"
            for indexed, updated in (
                (SESSION_ID, "2026-09-12T05:00:00Z"),
                (FRESH_SESSION_ID, "2026-09-12T05:41:00Z"),
            )
        ),
        encoding="utf-8",
    )
    connection = sqlite3.connect(home / "state_1.sqlite")
    with connection:
        _ = connection.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, model TEXT, cwd TEXT)")
        _ = connection.execute(
            "INSERT INTO threads (id, model, cwd) VALUES (?, ?, ?)",
            (SESSION_ID, model, str(tmp_path / "repo")),
        )
    connection.close()
    return home


def _rollout(*, codex_home, session_id):
    return str(
        codex_home
        / "sessions"
        / "2026"
        / "09"
        / "12"
        / f"rollout-2026-09-12T05-00-00-{session_id}.jsonl"
    )


def incident(*, tmp_path, model="gpt-5.6-sol", profile=None, clock=None):
    """A live BARE Codex carrier whose mapping row carries ``profile``, at a valid ready.

    Every Codex host coupling is injected, so the capture path reads this fixture's
    ``/proc`` and Codex home rather than the runner's. The carrier's argv is the bare
    ``codex`` the incident measured — no ``-m``, and an empty environ — so the ONLY model
    available anywhere is the exact-identity ``threads.model`` row.
    """
    repo, topic = make_plan(tmp_path=tmp_path, topic="repo")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    home = _codex_home(tmp_path=tmp_path, topic=topic, model=model)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=codex_idle_capture(ctx=40), cmd="bun")
    fake.pane_pids = {PANE_PID: session}
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    ticking = clock if clock is not None else {"t": 1002.0}
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={CARRIER_PID: PANE_PID},
        starttimes={},
        watch_repos=[str(repo)],
        codex_home=str(home),
        codex_pids_of_comm=lambda *, comm: (
            [CARRIER_PID] if comm == codex_sessions.CODEX_COMM else []
        ),
        codex_fd_targets_of=lambda *, pid: (
            [_rollout(codex_home=home, session_id=SESSION_ID)] if pid == CARRIER_PID else []
        ),
        codex_cwd_of=lambda *, pid: str(repo) if pid == CARRIER_PID else None,
        cmdline_of=lambda *, pid: b"codex\0" if pid == CARRIER_PID else None,
        environ_of=lambda *, pid: b"" if pid == CARRIER_PID else None,
        now=lambda: ticking["t"],
        out=_io.StringIO(),
    )

    def seeded_codex_session() -> None:
        respawned = any(call[0] == "respawn" for call in fake.calls)
        sup.live_codex = {
            (session, topic): codex_sessions.CodexSession(
                pid=CARRIER_PID,
                name=topic,
                cwd=str(repo),
                session_id=FRESH_SESSION_ID if respawned else SESSION_ID,
            )
        }

    seeded_codex_session()
    sup._refresh_codex_sessions = seeded_codex_session
    if profile is not None:
        registry.append_mapping(
            track=registry.Track(
                topic=topic,
                repo=str(repo),
                tmux=session,
                epic=TEST_EPIC,
                model_profile=dict(profile),
            ),
            store_path=sup.store_path,
        )
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=f"codex:{SESSION_ID}",
        stamp_path=sup.stamp_path,
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    return repo, topic, session, fake, sup


def stored_profile(*, sup):
    return registry.read_valid_mapping(store_path=sup.store_path)[0].model_profile


def stored_track(*, sup):
    return registry.read_valid_mapping(store_path=sup.store_path)[0]


def respawns(*, fake):
    return [call for call in fake.calls if call[0] == "respawn"]


def test_a_bare_codex_carrier_is_adopted_with_its_state_database_model(*, tmp_path):
    _repo, topic, _session, _fake, sup = incident(tmp_path=tmp_path)

    with contextlib.redirect_stderr(_io.StringIO()):
        adopted = sup.adopt_sessions()

    assert [track.topic for track in adopted] == [topic]
    assert stored_profile(sup=sup) == {
        "harness": "codex",
        "model": "gpt-5.6-sol",
        "statusline_model": "gpt-5.5 high",
        "wrapper": None,
    }


def test_the_wrapup_refresh_replaces_a_stale_claude_profile_on_a_bare_codex_carrier(*, tmp_path):
    _repo, _topic, session, _fake, sup = incident(tmp_path=tmp_path, profile=STALE_CLAUDE_PROFILE)

    with contextlib.redirect_stderr(_io.StringIO()):
        refresh.refresh_launch_profile_at_wrapup(
            sup=sup,
            track=stored_track(sup=sup),
            target=session,
            capture=codex_idle_capture(ctx=40),
        )

    assert stored_profile(sup=sup) == {
        "harness": "codex",
        "model": "gpt-5.6-sol",
        "statusline_model": "gpt-5.5 high",
        "wrapper": None,
    }


def test_a_cross_runtime_profile_self_heals_before_any_destructive_restart(*, tmp_path):
    repo, topic, session, fake, sup = incident(tmp_path=tmp_path, profile=STALE_CLAUDE_PROFILE)

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup._do_codex_restart(track=stored_track(sup=sup), target=fake.pane_id(session=session))

    assert respawns(fake=fake) == []
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert stored_profile(sup=sup) == {
        "harness": "codex",
        "model": "gpt-5.6-sol",
        "statusline_model": "gpt-5.5 high",
        "wrapper": None,
    }
    assert (str(repo), topic, "launch-profile-self-healed") in sup.alerted
    assert "recaptured and persisted the live profile" in err.getvalue()


def test_the_re_observed_row_restarts_once_and_consumes_the_declaration(*, tmp_path):
    repo, topic, session, fake, sup = incident(tmp_path=tmp_path, profile=STALE_CLAUDE_PROFILE)
    fake.codex_busy_frame = codex_busy_capture(ctx=95)
    target = fake.pane_id(session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        sup._do_codex_restart(track=stored_track(sup=sup), target=target)
        healed = stored_track(sup=sup)
        sup._do_codex_restart(track=healed, target=target)

    assert len(respawns(fake=fake)) == 1
    assert "-m gpt-5.6-sol" in respawns(fake=fake)[0][3]
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED


def test_an_unusable_state_database_model_fails_closed_and_preserves_the_pane(*, tmp_path):
    repo, topic, session, fake, sup = incident(
        tmp_path=tmp_path, model="<synthetic>", profile=STALE_CLAUDE_PROFILE
    )

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        sup._do_codex_restart(track=stored_track(sup=sup), target=fake.pane_id(session=session))

    assert respawns(fake=fake) == []
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert stored_profile(sup=sup) == STALE_CLAUDE_PROFILE
    assert (str(repo), topic, "launch-profile-unreadable") in sup.alerted
    assert "no usable model token" in err.getvalue()
    assert "could not be recaptured" in err.getvalue()


def test_a_cross_runtime_statusline_disagreement_no_longer_suspends_ready_expiry(*, tmp_path):
    clock = {"t": 1001.0 + READY_MAX_AGE + 1.0}
    repo, topic, _session, _fake, sup = incident(
        tmp_path=tmp_path, profile=STALE_CLAUDE_PROFILE, clock=clock
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        _ = sup.evaluate(track=stored_track(sup=sup), act=True)

    state = signals.read_state(repo=str(repo), topic=topic)
    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert state is not None and state.token == signals.STATE_READY_EXPIRED
    assert record.expired_at == 1001.0 + READY_MAX_AGE


def test_a_same_runtime_statusline_disagreement_still_suspends_ready_expiry(*, tmp_path):
    clock = {"t": 1001.0 + READY_MAX_AGE + 1.0}
    repo, topic, _session, _fake, sup = incident(
        tmp_path=tmp_path,
        clock=clock,
        profile={
            "harness": "codex",
            "model": "gpt-5.6-sol",
            "statusline_model": "gpt-5.5 recorded",
            "wrapper": None,
        },
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        _ = sup.evaluate(track=stored_track(sup=sup), act=True)

    state = signals.read_state(repo=str(repo), topic=topic)
    record = registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert state is not None and state.token == signals.STATE_READY
    assert record.expired_at is None
