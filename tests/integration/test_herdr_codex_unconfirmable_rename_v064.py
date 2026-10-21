"""Integration-tier SPECIFICATION v064: a Codex herdr rename that starts no turn.

Found by factory run 01M5EVBNK0X1 on overseer-uzvcbn.4 and code-confirmed by
claude-herdr-overseer on 2026-10-21, which reproduced it three times against a real
herdr instance with the released `overseerd` and a stub codex.

The daemon submitted `/rename <topic>` to a fresh Codex successor through the NATIVE
herdr submitter, which confirms a delivery only by an observed turn start or by a
positively empty composer. A slash command asks Codex for nothing, so no turn starts;
and a Codex composer is never positively empty, because its idle placeholder is
indistinguishable from typed text in a capture. The attempt therefore resolved in
NEITHER direction: the router HELD it, and because a held attempt re-drives its own
payload rather than pasting a new one, every later request for that pane was answered
from the stale rename. The replacement's resume line was never pasted at all — phase
stuck at `resume-attempted`, the `ready` declaration unspent, and the successor left
idle with a fresh context window and nothing to do. The Codex arm of herdr replacement
could not complete for ANY caller.

v064 scopes the held-paste rule to the payload that was held, and excepts the no-turn
naming payload: it is not held, and its outcome is proven by its own evidence — the
durable `session_index` record binding the successor's rollout to the topic — exactly
as the tmux arm has always proved it. What a held UNCONFIRMED wrap-up suppresses is
unchanged, and so is the tmux arm, both pinned below.
"""

from __future__ import annotations

import contextlib
import io as _io
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import _herdr_replacement_store
import _supervisor_herdr_recovery
import herdr_identity
import herdr_write
import pane_router_reads
import pane_router_submit
import pane_router_submit_signals
import pane_router_writes
import signals
from _codex_session_models import CodexSession
from test_supervisor_builders import (
    TEST_EPIC,
    adopt_codex_ready,
    codex_busy_capture,
    codex_idle_capture,
    declare,
    make_plan,
    make_supervisor,
    mapped_track,
)

__all__: list[str] = []

OLD = "019f548d-0000-7000-8000-000000000001"
NEW = "019f548d-0000-7000-8000-000000000002"
RESUME = "resume plan epic overseer-test-epic in repository /x/repo"
WRAPUP = "STOP AND WIND DOWN NOW. You have only 10% of your context left."
LATER_WRAPUP = "STOP AND WIND DOWN NOW. You have only 8% of your context left."
NUDGE = "You have context left — keep going, and do NOT offer to stop."
# The grey rotating placeholder a live idle Codex composer shows (`codex_idle_capture`).
# Replacing it is how this fixture renders a composer that HOLDS a payload.
PLACEHOLDER = "› Write tests for @filename"
_OK = herdr_write.WriteOutcome(ok=True, error="", effect_unknown=False)
_REFUSED = herdr_write.WriteOutcome(ok=False, error="paste refused", effect_unknown=False)


def _target(*, tmp_path: Path) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=str(tmp_path / "herdr.sock"),
            server_pid=700,
            server_starttime="server-start",
            pane_id="w1:p9",
        )
    )


def _process(*, pid: int, starttime: str, pgrp: int) -> SimpleNamespace:
    return SimpleNamespace(
        pid=pid,
        starttime=starttime,
        executable="/usr/bin/codex",
        argv=("codex",),
        process_group=pgrp,
        session_id=90,
    )


def _snapshot() -> SimpleNamespace:
    """The retained shell with a FRESH Codex launcher and runtime child in it."""
    shell = SimpleNamespace(
        pid=100,
        starttime="shell-start",
        executable="/bin/bash",
        argv=("/bin/bash",),
        process_group=100,
        session_id=90,
    )
    launcher = _process(pid=300, starttime="leader-new", pgrp=300)
    runtime = _process(pid=301, starttime="runtime-new", pgrp=300)
    return SimpleNamespace(
        ok=True,
        error="",
        shell=shell,
        foreground_group=300,
        processes=(shell, launcher, runtime),
    )


def _write_index(*, home: Path, topic: str, records: list[tuple[str, str]]) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "session_index.jsonl").write_text(
        "".join(
            json.dumps({"id": rollout, "thread_name": topic, "updated_at": updated}) + "\n"
            for rollout, updated in records
        ),
        encoding="utf-8",
    )


@dataclass(frozen=True, kw_only=True)
class _Behaviour:
    """What this stub Codex does with what the daemon hands it."""

    names: bool = True  # `/rename` appends the successor's durable index record
    paste_ok: bool = True  # the backend acknowledges the bracketed paste
    enter_lands: bool = True  # the Enter reaches the TUI rather than being dropped


# The faithful stub: everything acknowledged, the rename recorded, the Enter landing.
# A module-level singleton rather than a default-argument call, which ruff's B008 reads
# as a shared-mutable hazard — this one is frozen, so sharing it is the point.
FAITHFUL = _Behaviour()


class _StubCodex:
    """A herdr pane running a stub Codex, driven the way the live reproduction drove it.

    Two behaviours are the whole fixture, and the defect lives in the gap between them:

    - `/rename <topic>` STARTS NO TURN. The composer clears and Codex appends the
      durable `session_index` record; the pane never goes busy, so a submitter waiting
      on a turn start waits forever.
    - An ordinary prompt DOES start a turn, which is the only delivery confirmation
      Codex offers at all.

    It is also the herdr WRITER the router pastes through and the READS the router
    observes, so a test here exercises the real `PromptSubmitter` / `PaneRoutingWrites`
    rather than a stand-in for them.
    """

    def __init__(
        self,
        *,
        target: str,
        topic: str,
        home: Path,
        behaviour: _Behaviour = FAITHFUL,
        composer: str | None = None,
    ) -> None:
        self.target = target
        self.topic = topic
        self.home = home
        self.behaviour = behaviour
        self.composer = composer
        self.busy = False
        self.pastes: list[str] = []
        self.enters = 0
        self.prompt_states: dict[str, pane_router_submit_signals.PromptState] = {}
        # `make_supervisor` reads these two to seed its Claude status map; a codex pane
        # carries no Claude identity, which is exactly what they report here.
        self.sessions = {target}
        self.cmds = {target: "codex"}

    # -- the reads the reconcile and the router take ------------------------ #

    def decode(self, *, value: str) -> herdr_identity.TargetDecoding:
        return herdr_identity.decode_target(value=value)

    def capture_pane(self, *, session: str) -> str:
        assert session == self.target
        frame = codex_busy_capture(ctx=100) if self.busy else codex_idle_capture(ctx=100)
        if self.composer is None:
            return frame
        return frame.replace(PLACEHOLDER, f"› {self.composer}")

    def herdr_replacement_snapshot(self, *, session: str) -> SimpleNamespace:
        assert session == self.target
        return _snapshot()

    # -- the herdr input surface the router writes through ------------------ #

    def bracketed_paste(
        self, *, target: herdr_identity.HerdrPaneTarget, text: str
    ) -> herdr_write.WriteOutcome:
        assert target.pane_id == "w1:p9"
        self.pastes.append(text)
        if not self.behaviour.paste_ok:
            return _REFUSED
        self.composer = text.partition("\n")[0]
        return _OK

    def send_enter(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_write.WriteOutcome:
        assert target.pane_id == "w1:p9"
        self.enters += 1
        if not self.behaviour.enter_lands:
            return _OK  # the Enter was dropped: the payload still stands in the input
        submitted, self.composer = self.composer, None
        if submitted is None:
            return _OK
        if submitted.startswith("/"):
            # A slash command renames the thread and starts NO turn, so the only trace
            # it leaves anywhere is the durable index record.
            if self.behaviour.names:
                _write_index(
                    home=self.home,
                    topic=self.topic,
                    records=[(OLD, "2026-10-21T00:00:00Z"), (NEW, "2026-10-21T00:01:00Z")],
                )
            return _OK
        self.busy = True
        return _OK

    # -- the native submit entry points the daemon reaches for -------------- #

    def _writes(self) -> pane_router_writes.PaneRoutingWrites:
        return pane_router_writes.PaneRoutingWrites(
            reads=cast(pane_router_reads.PaneRoutingReads, self),
            herdr_writer=cast(pane_router_submit_signals.HerdrInput, self),
            prompt_states=self.prompt_states,
        )

    def submit_prompt_once(
        self, *, session: str, text: str, expect_codex: bool, sleep: Any
    ) -> tuple[bool, bool]:
        return self._writes().submit_prompt_once(
            session=session, text=text, expect_codex=expect_codex, sleep=sleep
        )

    def submit_no_turn_prompt_once(self, *, session: str, text: str, sleep: Any) -> bool:
        return self._writes().submit_no_turn_prompt_once(session=session, text=text, sleep=sleep)


def _transaction(*, target: str, repo: Path) -> dict[str, object]:
    return {
        "version": 1,
        "phase": "launch-attempted",
        "target": target,
        "server": {
            "socket_path": str(repo.parent / "herdr.sock"),
            "pid": 700,
            "starttime": "server-start",
            "pane_id": "w1:p9",
        },
        "runtime": "codex",
        "predecessor": {"pid": 201, "starttime": "runtime-old", "process_group": 200},
        "predecessor_rollout": OLD,
        "shell": {
            "pid": 100,
            "starttime": "shell-start",
            "executable": "/bin/bash",
            "argv": ["/bin/bash"],
            "process_group": 100,
            "session_id": 90,
        },
        "round": {
            "ready_mtime": 1001.0,
            "round_at": 1000.0,
            "session_identity": "codex:201:runtime-old:topic",
        },
        "launch": {"command": "codex", "cwd": str(repo), "env": {}},
        "resume": RESUME,
    }


def _replacement_world(*, tmp_path: Path, behaviour: _Behaviour = FAITHFUL):
    """A herdr Codex replacement whose fresh successor is launched and unnamed.

    The durable transaction sits at `launch-attempted` with the predecessor gone, its
    retained shell intact and a fresh Codex runtime child in it — the exact state an
    acting tick reconciles. The index names only the PREDECESSOR's rollout, so nothing
    yet proves the successor; the stub Codex writes the successor's record when, and
    only when, it is renamed.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    target = _target(tmp_path=tmp_path)
    home = tmp_path / "codex-home"
    _write_index(home=home, topic=topic, records=[(OLD, "2026-10-21T00:00:00Z")])
    pane = _StubCodex(target=target, topic=topic, home=home, behaviour=behaviour)
    sup = make_supervisor(tmp_path=tmp_path, fake=pane, now=lambda: 1002.0, codex_home=str(home))
    sup.live_codex[(target, topic)] = CodexSession(
        pid=301, name=topic, cwd=str(repo), session_id=NEW
    )
    sup.starttime_of = lambda *, pid: "runtime-new" if pid == 301 else None
    sup.refresh_codex_sessions = lambda: None
    track = mapped_track(repo=repo, topic=topic, session=target)
    _ = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=1001.0)
    record_path = (
        _herdr_replacement_store.scratch_path(track=track) / _herdr_replacement_store.RECORD_NAME
    )
    _herdr_replacement_store.durable_write(
        path=record_path, value=_transaction(target=target, repo=repo)
    )
    return repo, topic, target, pane, sup, track, record_path


def _reconcile(*, sup: Any, track: Any, target: str) -> tuple[Any, str]:
    log = _io.StringIO()
    with contextlib.redirect_stderr(log):
        view = _supervisor_herdr_recovery.reconcile_bare_shell(
            sup=sup, track=track, target=target, act=True
        )
    return view, log.getvalue()


def _phase(*, record_path: Path) -> str:
    return cast(str, json.loads(record_path.read_text(encoding="utf-8"))["phase"])


# ## Scenario: A Codex herdr replacement delivers the resume line after an unconfirmable rename
def test_scenario_a_codex_replacement_delivers_the_resume_after_an_unconfirmable_rename(
    *, tmp_path: Path
) -> None:
    """The whole round, with the rename confirmable by NOTHING the pane can show.

    Sabotage: hold the rename as an ordinary native attempt again and this goes red
    exactly where the live reproduction did — one paste, no resume, phase
    `resume-attempted`, declaration unspent.
    """
    repo, topic, target, pane, sup, track, record_path = _replacement_world(tmp_path=tmp_path)

    view, _log = _reconcile(sup=sup, track=track, target=target)

    assert view is not None
    assert view.note == "durable Herdr replacement phase: completed"
    assert _phase(record_path=record_path) == "completed"
    # Named first, from the index record the rename appended; then the resume line.
    assert pane.pastes == [f"/rename {topic}", RESUME]
    assert TEST_EPIC in pane.pastes[1]
    # The replacement consumed the declaration that authorized it.
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED
    # And it confirmed the resume by the successor's own turn start, not by the rename.
    assert pane.busy is True
    assert pane.prompt_states == {}


def test_an_unconfirmable_rename_is_never_held_as_an_unconfirmed_delivery(
    *, tmp_path: Path
) -> None:
    """The router level, asked directly: the no-turn payload records NO attempt.

    This is the fix stated as the smallest fact that implies it. A recorded attempt is
    what answered the resume request from the stale rename, so a pane holding nothing
    after the rename is what lets the next payload be pasted at all.
    """
    target = _target(tmp_path=tmp_path)
    pane = _StubCodex(target=target, topic="topic", home=tmp_path / "home")

    delivered = pane.submit_no_turn_prompt_once(
        session=target, text="/rename topic", sleep=lambda _seconds: None
    )

    assert delivered is True
    assert pane.pastes == ["/rename topic"]
    assert pane.enters == 1
    assert pane.prompt_states == {}
    assert pane.busy is False  # a slash command never starts a turn


def test_an_unnamed_successor_keeps_ready_surfaces_itself_and_pastes_no_resume(
    *, tmp_path: Path
) -> None:
    """The failure path v064 states explicitly, for a successor nothing ever names.

    The resume line is withheld rather than pasted hopefully: submitting it into a
    session the next tick cannot find would spend the declaration on nothing.
    """
    repo, topic, target, pane, sup, track, record_path = _replacement_world(
        tmp_path=tmp_path, behaviour=_Behaviour(names=False)
    )

    view, _log = _reconcile(sup=sup, track=track, target=target)

    assert view is not None
    assert view.status == "replacement-failed"
    assert view.note == "fresh Codex successor is not named in the session index"
    assert _phase(record_path=record_path) == "rename-attempted"
    assert pane.pastes == [f"/rename {topic}"]  # the resume was never submitted
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    # Nothing is held for the pane either, so a later tick may paste afresh.
    assert pane.prompt_states == {}


def test_a_refused_rename_paste_sends_no_enter_and_still_keeps_ready(*, tmp_path: Path) -> None:
    """A paste the backend REFUSED is a proven failure, so no Enter follows it."""
    repo, topic, target, pane, sup, track, _record_path = _replacement_world(
        tmp_path=tmp_path, behaviour=_Behaviour(paste_ok=False)
    )

    view, _log = _reconcile(sup=sup, track=track, target=target)

    assert view is not None
    assert view.note == "fresh Codex successor is not named in the session index"
    assert pane.pastes == [f"/rename {topic}"]
    assert pane.enters == 0
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY


def test_a_held_unconfirmed_wrapup_never_suppresses_the_proven_successors_resume(
    *, tmp_path: Path
) -> None:
    """v064's SECOND exception, and the one the first cut of this fix left out.

    The replacement's own wind-down is the paste that most often ends UNCONFIRMED on a
    Codex pane, so a held attempt is the ORDINARY state a replacement starts from — and
    the round that would release it (`complete_replacement_round`) only runs once the
    resume has already succeeded. Held, it answered this request with the stale wrap-up
    and the resume line was never pasted at all: the identical symptom this item exists
    to eliminate, reached through the other held payload.

    What the held attempt describes is a composer the PREDECESSOR took with it. The
    successor is a different process generation in the retained pane, which is what
    `_prove_successor` has already established by the time the resume is due, so the
    line is pasted afresh and confirmed by the successor's own observed turn start.
    """
    repo, topic, target, pane, sup, track, record_path = _replacement_world(tmp_path=tmp_path)
    pane.prompt_states[target] = pane_router_submit_signals.PromptState(
        text=WRAPUP, phase="await-enter", effect_unknown=True
    )

    view, _log = _reconcile(sup=sup, track=track, target=target)

    assert view is not None
    assert view.note == "durable Herdr replacement phase: completed"
    assert _phase(record_path=record_path) == "completed"
    assert pane.pastes == [f"/rename {topic}", RESUME]
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED
    assert pane.busy is True
    # The released attempt is not re-held either: the resume resolved DELIVERED.
    assert pane.prompt_states == {}


def test_a_held_unconfirmed_wrapup_is_followed_by_no_later_wrapup_or_nudge(
    *, tmp_path: Path
) -> None:
    """What the no-turn exception does NOT relax: every other payload stays suppressed.

    A wrap-up whose Enter was dropped still stands in the composer, and a Codex pane
    can never prove that composer empty — so the attempt is genuinely UNCONFIRMED. A
    later wrap-up and a keep-going nudge are both answered from it without being pasted,
    which is the hazard v064 keeps: a second wind-down arriving behind a first that did
    in fact land.
    """
    target = _target(tmp_path=tmp_path)
    pane = _StubCodex(
        target=target,
        topic="topic",
        home=tmp_path / "home",
        behaviour=_Behaviour(enter_lands=False),
        composer=WRAPUP,
    )
    pane.prompt_states[target] = pane_router_submit_signals.PromptState(
        text=WRAPUP, phase="await-enter", effect_unknown=True
    )
    submitter = pane_router_submit.PromptSubmitter(
        reads=cast(pane_router_reads.PaneRoutingReads, pane),
        writer=cast(pane_router_submit_signals.HerdrInput, pane),
        states=pane.prompt_states,
    )

    for later in (LATER_WRAPUP, NUDGE):
        assert submitter.submit_prompt_once(
            session=target, text=later, expect_codex=True, sleep=lambda _seconds: None
        ) == (False, False)

    assert pane.pastes == []
    assert pane.prompt_states[target].text == WRAPUP


# ## Scenario: Both backends retain supervision and acting guards
def test_the_tmux_codex_arm_still_names_resumes_and_consumes_its_declaration(
    *, tmp_path: Path
) -> None:
    """The tmux arm is reached by a different route and must be untouched by this fix.

    It proves its rename from the same index record but pastes it directly, holding no
    router attempt to begin with — which is precisely the shape the herdr arm now
    adopts. `tests/test_codex_fresh_restart_post_rename_gap.py` drives the measured
    post-rename discovery gap in full; this is the both-backends guard beside the herdr
    change itself.
    """
    repo, topic, session, _session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    track = mapped_track(repo=repo, topic=topic, session=session)
    log = _io.StringIO()

    with contextlib.redirect_stderr(log):
        view = sup.evaluate(track=track, act=True)

    assert view.status == "restarting"
    assert fake.paste_texts()[0] == f"/rename {topic}"
    assert TEST_EPIC in fake.paste_texts()[1]
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED

    fake.calls.clear()
    with contextlib.redirect_stderr(log):
        _ = sup.evaluate(track=track, act=True)

    assert not fake.has(method="respawn")  # the consumed declaration authorizes nothing
