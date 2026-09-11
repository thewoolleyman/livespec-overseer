"""The late fresh-Codex successor an ordinary tick must reconcile.

Measured live 2026-09-11 (``overseer-bdhxhx``), on the residual half of the fresh-Codex
arm's first natural control. Daemon instance ``685abc9a…`` launched rollout
``01a08dd5…`` at 00:19:33Z to replace predecessor ``01a08cf6…``, and its bounded
live-adoption poll ran out at 00:20:04Z with ``codex-fresh-session-unadopted`` — keeping
the predecessor's ``ready`` declaration and the round open, which is the correct
fail-closed behaviour for a proof that did not land.

What was missing is what happened NEXT. The successor became live and ordinary discovery
adopted it, which is precisely the proof the round had been waiting for; nothing
reconciled the two. The stale declaration stood until it expired at 03:51:31Z, the
expiry notice reset the idle episode, and a human relayed the plan-resume instruction by
hand at 03:56:59Z — three and a half hours after the restart the daemon itself had
performed.

The first test drives that exact ordering, with the clock advanced past the ready
maximum age between the two ticks so the whole live gap is inside the window: one
ordinary tick must complete the round rather than let it age out. The wrong-candidate
half of the same claim — that proving SOMETHING changed is not proving the DAEMON
changed it — is in ``test_codex_late_successor_safety``.
"""

from __future__ import annotations

import contextlib
import dataclasses
import io as _io
import json
from pathlib import Path

import codex_sessions
import pytest
import registry
import signals
from test_supervisor_builders import (
    FRESH_CODEX_SESSION_ID,
    TEST_EPIC,
    adopt_codex_ready,
    codex_busy_capture,
    key_for,
    mapped_track,
)

__all__: list[str] = ["Stranded", "unadopted_fresh_restart"]

PRIOR_INDEXED_AT = "2026-09-11T00:10:00Z"
RENAMED_AT = "2026-09-11T00:19:46Z"
# The live timeline in seconds: the restart gives up at the first instant, and the
# successor is only reconciled long after the 1800s ready maximum age would have
# expired the declaration — which is what actually happened, at 03:51:31Z.
RESTART_AT = 1000.0
LATE_TICK_AT = 5001.0


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def write_index(*, home: Path, topic: str, records) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "session_index.jsonl").write_text(
        "".join(
            json.dumps({"id": session_id, "thread_name": topic, "updated_at": updated}) + "\n"
            for session_id, updated in records
        ),
        encoding="utf-8",
    )


@dataclasses.dataclass(frozen=True, kw_only=True)
class Stranded:
    """The world as the 2026-09-11 restart left it: successor named, round still open."""

    repo: Path
    topic: str
    session: str
    predecessor: str
    fake: object
    sup: object
    track: object
    log: _io.StringIO
    clock: dict[str, float]
    live: dict[str, bool]

    def tick(self, *, act: bool = True):
        with contextlib.redirect_stderr(self.log):
            return self.sup.evaluate(track=self.track, act=act)

    def surfaces(self, *, session_id, name=None, cwd=None):
        """Point live discovery at one candidate successor for the next ordinary tick."""
        self.sup.live_codex = {
            (self.session, self.topic): codex_sessions.CodexSession(
                pid=5150,
                name=name if name is not None else self.topic,
                cwd=str(cwd if cwd is not None else self.repo),
                session_id=session_id,
            )
        }

    def age_past_ready_maximum(self) -> None:
        """Advance to 03:51-and-later, where the live declaration expired unreconciled."""
        self.clock["t"] = LATE_TICK_AT

    def round_record(self):
        return registry.read_round_record(
            repo=str(self.repo), topic=self.topic, stamp_path=self.sup.stamp_path
        )

    def state_token(self):
        return signals.read_state(repo=str(self.repo), topic=self.topic).token

    def resume_pastes(self):
        return [text for text in self.fake.paste_texts() if TEST_EPIC in text]

    def respawns(self):
        return [call for call in self.fake.calls if call[0] == "respawn"]


def unadopted_fresh_restart(*, tmp_path, resume_takes=True) -> Stranded:
    """Run the measured restart: named, kicked, and never discoverable before it gives up.

    ``resume_takes`` is the one thing that varies, and it separates the two shapes this
    recovery has to cover. True is the CURRENT sequence — the resume line submits and
    only the final live-adoption proof times out. False is the older partial sequence a
    daemon may still be running, where the kick never landed either; the reconciliation
    then owes the successor its resume line as well as its round.
    """
    repo, topic, session, session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    clock = {"t": RESTART_AT}
    sup.now = lambda: clock["t"]
    home = tmp_path / "late-codex-home"
    write_index(home=home, topic=topic, records=[(session_id, PRIOR_INDEXED_AT)])
    sup.codex_home = str(home)
    live = {"discoverable": False, "kick_lands": resume_takes}

    def paste_effects(paste_session, text):
        if text == f"/rename {topic}":
            write_index(
                home=home,
                topic=topic,
                records=[(session_id, PRIOR_INDEXED_AT), (FRESH_CODEX_SESSION_ID, RENAMED_AT)],
            )
            return  # a slash command asks the model for nothing; the pane stays idle
        if live["kick_lands"]:
            fake.panes[paste_session] = codex_busy_capture(ctx=95)

    fake.on_paste = paste_effects

    def discoverable_only_when_declared() -> None:
        if not live["discoverable"]:
            sup.live_codex = {}
            return
        sup.live_codex = {
            (session, topic): codex_sessions.CodexSession(
                pid=5150, name=topic, cwd=str(repo), session_id=FRESH_CODEX_SESSION_ID
            )
        }

    sup._refresh_codex_sessions = discoverable_only_when_declared
    stranded = Stranded(
        repo=repo,
        topic=topic,
        session=session,
        predecessor=session_id,
        fake=fake,
        sup=sup,
        track=mapped_track(repo=repo, topic=topic, session=session),
        log=_io.StringIO(),
        clock=clock,
        live=live,
    )
    view = stranded.tick()

    assert view.status == "restarting"
    assert stranded.state_token() == signals.STATE_READY
    assert len(stranded.respawns()) == 1
    return stranded


def test_one_ordinary_tick_completes_a_restart_whose_adoption_proof_timed_out(*, tmp_path):
    """The measured recovery: no expiry, no notice, no second respawn, no manual relay.

    Sabotage: drop the reconciliation from the cascade and this goes red exactly where
    the live control did — the declaration ages past its maximum and expires, the round
    stays open, and the successor sits working with nobody having consumed anything.
    """
    stranded = unadopted_fresh_restart(tmp_path=tmp_path)
    key = key_for(repo=stranded.repo, topic=stranded.topic)
    stale_istate = stranded.sup.inject[key]
    resume_pastes_before = len(stranded.resume_pastes())
    stranded.surfaces(session_id=FRESH_CODEX_SESSION_ID)
    stranded.age_past_ready_maximum()

    view = stranded.tick()

    assert view.status == "working"  # the successor is judged on its own merits
    assert stranded.state_token() == signals.STATE_RESTARTED
    assert stranded.round_record().at is None  # the round is closed, not merely quiet
    assert stranded.sup.inject[key] is not stale_istate  # per-round + idle-nudge state reset
    assert len(stranded.respawns()) == 1  # the successor was never killed and relaunched
    assert len(stranded.resume_pastes()) == resume_pastes_before  # nothing re-relayed
    log = stranded.log.getvalue()
    assert log.count(f"consumed ready declaration for {stranded.repo}::{stranded.topic}") == 1
    assert log.count(f"restarted (codex) {stranded.repo}::{stranded.topic}") == 1
    assert "expired ready declaration" not in log


def test_the_reconciled_round_is_closed_for_good_and_never_fires_twice(*, tmp_path):
    """The provenance dies with the round, so a later tick has nothing left to act on."""
    stranded = unadopted_fresh_restart(tmp_path=tmp_path)
    stranded.surfaces(session_id=FRESH_CODEX_SESSION_ID)
    _ = stranded.tick()
    stranded.log.truncate(0)

    view = stranded.tick()

    assert view.status == "working"
    assert stranded.state_token() == signals.STATE_RESTARTED
    assert stranded.round_record().at is None
    assert "restarted (codex)" not in stranded.log.getvalue()
    assert "consumed ready declaration" not in stranded.log.getvalue()


def test_a_late_adoption_delivers_a_resume_the_round_never_managed_to_submit(*, tmp_path):
    """The older partial sequence: the kick is owed, so reconciliation pays it — once."""
    stranded = unadopted_fresh_restart(tmp_path=tmp_path, resume_takes=False)
    delivered_before = len(stranded.resume_pastes())
    stranded.live["kick_lands"] = True
    stranded.surfaces(session_id=FRESH_CODEX_SESSION_ID)

    _ = stranded.tick()

    assert len(stranded.resume_pastes()) == delivered_before + 1
    assert stranded.state_token() == signals.STATE_RESTARTED
    assert stranded.round_record().at is None

    delivered = len(stranded.resume_pastes())
    _ = stranded.tick()
    assert len(stranded.resume_pastes()) == delivered  # at most once, across every tick


def test_a_late_resume_that_never_confirms_keeps_the_declaration_and_retries(*, tmp_path):
    """An unconfirmed submit consumes nothing: the round stays open under its own alert."""
    stranded = unadopted_fresh_restart(tmp_path=tmp_path, resume_takes=False)
    stranded.surfaces(session_id=FRESH_CODEX_SESSION_ID)

    _ = stranded.tick()

    assert stranded.state_token() == signals.STATE_READY
    assert stranded.round_record().at is not None
    assert "late-adopted fresh Codex session never took the resume line" in stranded.log.getvalue()

    stranded.live["kick_lands"] = True
    _ = stranded.tick()
    assert stranded.state_token() == signals.STATE_RESTARTED


def test_a_read_only_list_pass_never_reconciles_anything(*, tmp_path):
    """``act=False`` is the ``list`` command: it classifies, it never consumes anything."""
    stranded = unadopted_fresh_restart(tmp_path=tmp_path)
    stranded.surfaces(session_id=FRESH_CODEX_SESSION_ID)

    _ = stranded.tick(act=False)

    assert stranded.state_token() == signals.STATE_READY
    assert stranded.round_record().at is not None
