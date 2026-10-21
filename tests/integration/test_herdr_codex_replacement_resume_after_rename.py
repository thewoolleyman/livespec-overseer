"""Integration-tier SPECIFICATION v064: a herdr Codex replacement after an unconfirmable rename.

Found by factory run 01M5EVBNK0X1 and reproduced three times against a real herdr
instance, the released ``overseerd`` and a stub codex (2026-10-21). The daemon submitted
``/rename <topic>`` to the fresh Codex successor through the verified native prompt
submitter. A slash command asks the model for nothing, so no turn began; a Codex pane can
never prove its composer empty either, so that delivery could never be confirmed and the
router kept its per-pane ``PromptState``. Every later payload for that pane then re-drove
the HELD rename text instead of pasting itself, so the replacement's resume line was never
delivered, ``_resume_successor`` wrote phase ``resume-attempted`` and failed, and the
Enter-only retry had no payload standing in the composer to match. The Codex arm of herdr
replacement could not complete for any caller.

SPECIFICATION v064 (``SPECIFICATION/spec.md``) settles it: a daemon-authored payload that
asks the runtime for no turn MUST NOT be held as an UNCONFIRMED delivery and MUST NOT
suppress a later paste, and its outcome is proven by its own evidence — for a Codex rename,
the durable ``session_index.jsonl`` record binding the successor's rollout to the topic. The
held wrap-up suppression stays for every other payload, which the last test here pins.

These tests drive the REAL router (``PaneRoutingWrites`` over ``PromptSubmitter``) rather
than stubbing ``submit_prompt``, because the defect lived entirely inside that seam: every
pre-existing successor test patched it out, which is how this shipped.
"""

from __future__ import annotations

import contextlib
import io as _io
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from overseer import (
    _herdr_replacement_store,
    _supervisor_herdr_recovery,
    herdr_identity,
    herdr_write,
    pane_router_reads,
    pane_router_submit,
    pane_router_submit_signals,
    pane_router_writes,
    registry,
    signals,
)
from overseer._codex_session_models import CodexSession
from overseer.test_supervisor_builders import (
    codex_busy_capture,
    codex_idle_capture,
    declare,
    make_plan,
    make_supervisor,
    mapped_track,
)
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []

OLD_ROLLOUT = "019f548d-0000-7000-8000-000000000001"
NEW_ROLLOUT = "019f548d-0000-7000-8000-000000000002"
OLD_INDEXED_AT = "2026-10-21T09:00:00Z"
RENAMED_AT = "2026-10-21T10:21:00Z"
# Single-line, and clear of every busy marker a Codex confirm reads (`esc to interrupt`,
# `· Ns ·`, `↓ N tokens`), so an UNSUBMITTED payload can never false-read as submitted.
RESUME = "resume plan epic overseer-test-epic in repository /x/repo; read its plan state"
READY_MTIME = 1001.0
ROUND_AT = 1000.0
_OK = herdr_write.WriteOutcome(ok=True, error="", effect_unknown=False)


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
    shell = SimpleNamespace(
        pid=100,
        starttime="shell-start",
        executable="/bin/bash",
        argv=("/bin/bash",),
        process_group=100,
        session_id=90,
    )
    leader = _process(pid=300, starttime="leader-new", pgrp=300)
    runtime = _process(pid=301, starttime="runtime-new", pgrp=300)
    return SimpleNamespace(shell=shell, foreground_group=300, processes=(shell, leader, runtime))


def _transaction(*, target: str, repo: Path) -> dict[str, object]:
    return {
        "version": 1,
        "phase": "launch-attempted",
        "target": target,
        "server": {
            "socket_path": "/tmp/herdr.sock",
            "pid": 700,
            "starttime": "server-start",
            "pane_id": "w1:p9",
        },
        "runtime": "codex",
        "predecessor": {"pid": 201, "starttime": "runtime-old", "process_group": 200},
        "predecessor_rollout": OLD_ROLLOUT,
        "shell": {
            "pid": 100,
            "starttime": "shell-start",
            "executable": "/bin/bash",
            "argv": ["/bin/bash"],
            "process_group": 100,
            "session_id": 90,
        },
        "round": {
            "ready_mtime": READY_MTIME,
            "round_at": ROUND_AT,
            "session_identity": "codex:201:runtime-old:topic",
        },
        "launch": {"command": "codex", "cwd": str(repo), "env": {}},
        "resume": RESUME,
    }


@dataclass(kw_only=True)
class _StubCodex:
    """A Codex pane that starts NO turn on `/rename` and a turn on a submitted prompt.

    The one behaviour the defect turns on: `/rename` is answered by the durable index
    record alone, so nothing a capture can show ever confirms its delivery.
    """

    fake: FakeTmux
    target: str
    topic: str
    index_path: Path
    indexes_the_rename: bool
    pastes: list[str] = field(default_factory=list)
    turns: list[str] = field(default_factory=list)
    composer: str = ""

    def _render(self) -> None:
        idle = codex_idle_capture(ctx=95, topic=self.topic)
        if not self.composer:
            self.fake.panes[self.target] = idle
            return
        self.fake.panes[self.target] = idle.replace(
            "› Write tests for @filename", f"› {self.composer}"
        )

    def paste(self, text: str) -> None:
        self.pastes.append(text)
        self.composer = text.partition("\n")[0].strip()
        self._render()

    def enter(self) -> None:
        submitted = self.composer
        self.composer = ""
        if not submitted:
            return
        if submitted.startswith("/rename "):
            # A slash command asks the model for nothing: the pane returns to idle and
            # only the durable session index records that it landed.
            self._render()
            if self.indexes_the_rename:
                _write_index(
                    path=self.index_path,
                    topic=self.topic,
                    records=[(OLD_ROLLOUT, OLD_INDEXED_AT), (NEW_ROLLOUT, RENAMED_AT)],
                )
            return
        self.turns.append(submitted)
        self.fake.panes[self.target] = codex_busy_capture(ctx=95)


@dataclass(kw_only=True)
class _StubWriter:
    """The herdr input surface, driving the one stub Codex pane."""

    stub: _StubCodex

    def bracketed_paste(
        self, *, target: herdr_identity.HerdrPaneTarget, text: str
    ) -> herdr_write.WriteOutcome:
        del target
        self.stub.paste(text)
        return _OK

    def send_enter(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_write.WriteOutcome:
        del target
        self.stub.enter()
        return _OK


@dataclass(kw_only=True)
class _Reads:
    """The read surface the router resolves its pane coordinate and captures through."""

    fake: FakeTmux

    def decode(self, *, value: str) -> herdr_identity.TargetDecoding:
        return herdr_identity.decode_target(value=value)

    def capture_pane(self, *, session: str) -> str:
        return cast(str, self.fake.capture_pane(session=session))


def _write_index(*, path: Path, topic: str, records: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps({"id": rollout, "thread_name": topic, "updated_at": updated}) + "\n"
            for rollout, updated in records
        ),
        encoding="utf-8",
    )


@dataclass(kw_only=True)
class _World:
    repo: Path
    topic: str
    target: str
    sup: Any
    track: registry.Track
    stub: _StubCodex
    prompt_states: dict[str, pane_router_submit_signals.PromptState]
    record_path: Path


def _armed_replacement(*, tmp_path: Path, indexes_the_rename: bool) -> _World:
    repo, topic = make_plan(tmp_path=tmp_path)
    target = _target(tmp_path=tmp_path)
    codex_home = tmp_path / "codex-home"
    index_path = codex_home / "session_index.jsonl"
    _write_index(path=index_path, topic=topic, records=[(OLD_ROLLOUT, OLD_INDEXED_AT)])

    fake = FakeTmux()
    fake.serve(session=target, repo=repo, capture=codex_idle_capture(ctx=95, topic=topic))
    fake.cmds[target] = "codex"
    fake.herdr_replacement_snapshot = lambda *, session: _snapshot()
    stub = _StubCodex(
        fake=fake,
        target=target,
        topic=topic,
        index_path=index_path,
        indexes_the_rename=indexes_the_rename,
    )
    prompt_states: dict[str, pane_router_submit_signals.PromptState] = {}
    writes = pane_router_writes.PaneRoutingWrites(
        reads=cast(pane_router_reads.PaneRoutingReads, _Reads(fake=fake)),
        herdr_writer=cast(pane_router_submit_signals.HerdrInput, _StubWriter(stub=stub)),
        prompt_states=prompt_states,
    )
    # The daemon's own paste surface and the router's submit surfaces all drive the one
    # stub pane, so a payload is recorded once whichever route delivers it.
    fake.on_paste = lambda _session, text: stub.paste(text)
    fake.prompt_states = prompt_states
    fake.submit_prompt_once = writes.submit_prompt_once
    fake.retry_prompt_enter_once = writes.retry_prompt_enter_once

    sup = make_supervisor(tmp_path=tmp_path, fake=fake, codex_home=str(codex_home))
    sup.live_codex[(target, topic)] = CodexSession(
        pid=301, name=topic, cwd=str(repo), session_id=NEW_ROLLOUT
    )
    sup.starttime_of = lambda *, pid: "runtime-new" if pid == 301 else None
    sup.refresh_codex_sessions = lambda: None
    track = mapped_track(repo=repo, topic=topic, session=target)
    _ = declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=READY_MTIME)
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=ROUND_AT,
        session_identity="codex:201:runtime-old:topic",
        stamp_path=sup.stamp_path,
    )
    record_path = (
        _herdr_replacement_store.scratch_path(track=track) / _herdr_replacement_store.RECORD_NAME
    )
    _herdr_replacement_store.durable_write(
        path=record_path, value=_transaction(target=target, repo=repo)
    )
    return _World(
        repo=repo,
        topic=topic,
        target=target,
        sup=sup,
        track=track,
        stub=stub,
        prompt_states=prompt_states,
        record_path=record_path,
    )


def _reconcile(*, world: _World) -> Any:
    with contextlib.redirect_stderr(_io.StringIO()):
        return _supervisor_herdr_recovery.reconcile_bare_shell(
            sup=world.sup, track=world.track, target=world.target, act=True
        )


def _phase(*, world: _World) -> object:
    record = _herdr_replacement_store.read_transaction(path=world.record_path)
    return cast(dict[str, object], record).get("phase")


def _declared(*, world: _World) -> str | None:
    state = signals.read_state(repo=str(world.repo), topic=world.topic)
    return None if state is None else state.token


# ## Scenario: A Codex herdr replacement delivers the resume line after an unconfirmable rename
def test_a_herdr_codex_replacement_delivers_the_resume_after_an_unconfirmable_rename(
    *, tmp_path: Path
) -> None:
    world = _armed_replacement(tmp_path=tmp_path, indexes_the_rename=True)

    row = _reconcile(world=world)

    # The no-turn naming payload is not held as an UNCONFIRMED delivery for this pane.
    assert world.prompt_states == {}
    # The index recorded the successor's rollout, so the resume line was pasted into it...
    assert world.stub.pastes == [f"/rename {world.topic}", RESUME]
    # ...and ONLY that payload's delivery is confirmed by an observed turn start.
    assert world.stub.turns == [RESUME]
    # The replacement reached phase completed and consumed the ready declaration.
    assert _phase(world=world) == "completed"
    assert _declared(world=world) == signals.STATE_RESTARTED
    assert row is not None
    assert row.note == "durable Herdr replacement phase: completed"


def test_a_successor_the_index_never_names_keeps_ready_and_delivers_no_resume(
    *, tmp_path: Path
) -> None:
    """The failure leg the same rule states: an unnamed successor is surfaced, not resumed."""
    world = _armed_replacement(tmp_path=tmp_path, indexes_the_rename=False)

    row = _reconcile(world=world)

    assert row is not None
    assert row.status == "replacement-failed"
    assert row.note == "fresh Codex successor was never named for this plan topic"
    # The resume line is never pasted into a successor the daemon cannot prove it tracks.
    assert world.stub.pastes == [f"/rename {world.topic}"]
    assert world.stub.turns == []
    assert _declared(world=world) == signals.STATE_READY
    # A naming attempt that failed is not held either, or it would answer for — and
    # suppress — the Enter-only rename retry the next observation owes this pane.
    assert world.prompt_states == {}


def test_a_held_unconfirmed_wrapup_still_suppresses_a_later_wrapup_and_nudge(
    *, tmp_path: Path
) -> None:
    """The suppression that STAYS: every payload but the no-turn one is still held off."""
    target = _target(tmp_path=tmp_path)
    rule = "─" * 40
    wrapup = "STOP AND WIND DOWN NOW. You have only 10% of your context left."
    fake = FakeTmux()
    # The held wrap-up is still standing in the composer, so nothing resolves it.
    fake.panes[target] = f"● prior response\n{rule}\n❯ {wrapup}\n{rule}\n  Ctx: 10% left\n"
    stub = _StubCodex(
        fake=fake,
        target=target,
        topic="topic",
        index_path=tmp_path / "unused" / "session_index.jsonl",
        indexes_the_rename=False,
    )
    held = {
        target: pane_router_submit_signals.PromptState(
            text=wrapup, phase="await-enter", effect_unknown=True
        )
    }
    submitter = pane_router_submit.PromptSubmitter(
        reads=cast(pane_router_reads.PaneRoutingReads, _Reads(fake=fake)),
        writer=cast(pane_router_submit_signals.HerdrInput, _StubWriter(stub=stub)),
        states=held,
    )

    for later in ("STOP AND WIND DOWN NOW. You have only 8% of your context left.", "keep going"):
        assert submitter.submit_prompt_once(
            session=target, text=later, expect_codex=False, sleep=lambda _seconds: None
        ) == (False, False)

    assert stub.pastes == []
    assert held[target].text == wrapup
