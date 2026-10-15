"""Integration-tier SPECIFICATION v059: herdr wrap-up delivery confirmation.

Measured 2026-10-15 on daemon 5.28.3: petri-factory-on-gmktec received the 08:09Z
wrap-up (it is in the pane scrollback once) and declared ready, but the daemon logged
"paste did not land", un-opened the round, and from then on answered every later
wrap-up to that pane from its stuck in-memory attempt, so nothing was ever pasted
again. gitops-fleet-capacity-monitoring followed the same sequence on 2026-10-14.
"""

from __future__ import annotations

import contextlib
import importlib
import io as _io
from typing import Any, cast

from overseer import (
    _supervisor_restart,
    _supervisor_state,
    herdr_identity,
    herdr_write,
    pane_router_reads,
    pane_router_submit,
    pane_router_submit_signals,
    registry,
    signals,
)
from overseer.test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_TARGET = herdr_identity.HerdrPaneTarget(
    socket_path="/run/herdr-test.sock", server_pid=41, server_starttime="777", pane_id="w6:pH"
)
_SESSION = herdr_identity.encode_herdr_target(target=_TARGET)
_PROMPT = "STOP AND WIND DOWN NOW. You have only 10% of your context left.\n" + "line\n" * 40
_LATER = "STOP AND WIND DOWN NOW. You have only 8% of your context left.\n" + "line\n" * 40
_RULE = "─" * 40
_STATUS = "  Opus 5.5 | /x/repo | Ctx: 8% left\n"
_PASTED = f"● prior response\n{_RULE}\n❯ [Pasted text #1 +41 lines]\n{_RULE}\n{_STATUS}"
# The live petri pane after it acted on the wrap-up: a recap block, then an EMPTY box.
_EMPTY = (
    "✻ Sautéed for 12m 54s · done 10:22 AM\n\n"
    "※ recap: We're moving the current Fabro server to gmktec through gitops.\n\n"
    f"{_RULE}\n❯ \n{_RULE}\n{_STATUS}"
)
_BUSY = "● prior response\n✻ Galloping… (3s · ↓ 120 tokens · esc to interrupt)\n"
_OK = herdr_write.WriteOutcome(ok=True, error="", effect_unknown=False)


class _Reads:
    def __init__(self, *, captures: list[str]) -> None:
        self.captures = captures

    def decode(self, *, value: str) -> herdr_identity.TargetDecoding:
        return herdr_identity.decode_target(value=value)

    def capture_pane(self, *, session: str) -> str:
        assert session == _SESSION
        return self.captures.pop(0) if len(self.captures) > 1 else self.captures[0]


class _Writer:
    def __init__(self) -> None:
        self.pastes: list[str] = []
        self.enters = 0

    def bracketed_paste(self, *, target: herdr_identity.HerdrPaneTarget, text: str) -> Any:
        assert target == _TARGET
        self.pastes.append(text)
        return _OK

    def send_enter(self, *, target: herdr_identity.HerdrPaneTarget) -> Any:
        assert target == _TARGET
        self.enters += 1
        return _OK


def _submitter(
    *, reads: _Reads, writer: _Writer, states=None
) -> pane_router_submit.PromptSubmitter:
    return pane_router_submit.PromptSubmitter(
        reads=cast(pane_router_reads.PaneRoutingReads, reads),
        writer=cast(pane_router_submit_signals.HerdrInput, writer),
        states={} if states is None else states,
    )


def _submit(*, submitter, text=_PROMPT):
    return submitter.submit_prompt_once(
        session=_SESSION, text=text, expect_codex=False, sleep=lambda _seconds: None
    )


# ## Scenario: A payload that left the input after it was observed there counts as delivered
def test_scenario_a_payload_that_left_the_input_counts_as_delivered() -> None:
    writer = _Writer()
    # The paste is seen in the composer, Enter is sent, and the next frames show only the
    # emptied box and a recap — no busy frame inside the observe window.
    submitter = _submitter(reads=_Reads(captures=[_PASTED, _EMPTY]), writer=writer)

    assert _submit(submitter=submitter) == (True, False)
    assert writer.enters == 1
    assert submitter.states == {}


def test_a_stuck_attempt_whose_payload_left_the_input_lets_the_next_wrapup_paste() -> None:
    """The wedge: a pending Enter answered every later request without pasting."""
    writer = _Writer()
    reads = _Reads(captures=[_EMPTY])
    stuck = {
        _SESSION: pane_router_submit_signals.PromptState(
            text=_PROMPT, phase="await-enter", effect_unknown=True
        )
    }
    submitter = _submitter(reads=reads, writer=writer, states=stuck)

    # The later, different wrap-up first resolves the stale attempt as delivered...
    assert _submit(submitter=submitter, text=_LATER) == (False, False)
    assert submitter.states == {}
    # ...and the one after it is pasted afresh and confirmed.
    reads.captures = [
        _PASTED.replace("[Pasted text #1 +41 lines]", "[Pasted text #2 +41 lines]"),
        _BUSY,
    ]
    assert _submit(submitter=submitter, text=_LATER) == (True, False)
    assert writer.pastes == [_LATER]


def test_a_paste_never_seen_in_an_empty_composer_is_forgotten_and_pasted_again() -> None:
    writer = _Writer()
    reads = _Reads(captures=[_EMPTY])
    submitter = _submitter(reads=reads, writer=writer)

    assert _submit(submitter=submitter) == (False, False)
    assert submitter.states == {}
    assert writer.enters == 0

    reads.captures = [_PASTED, _BUSY]
    assert _submit(submitter=submitter) == (True, False)
    assert len(writer.pastes) == 2


def test_a_codex_composer_is_never_positively_empty() -> None:
    codex = "› Write tests for @filename\n  gpt-5.5 high · /x/repo · Context 8% left · topic\n"
    assert pane_router_submit_signals.composer_empty(capture=codex) is False


def _undelivered_wrapup(*, tmp_path, monkeypatch, effect_unknown):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=10))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    # Patch the module the daemon itself imports (by bare name), never the `overseer.`
    # package alias, which is a different module object the daemon never calls.
    monkeypatch.setattr(
        importlib.import_module("_supervisor_launch"),
        "submit_prompt_outcome",
        lambda **_kwargs: (False, effect_unknown),
        # The seam this change introduces; absent before it, so a pre-change tree
        # exercises its own submit path and fails on the round's behavior instead.
        raising=False,
    )
    track = mapped_track(repo=repo, topic=topic, session=session)
    return repo, topic, session, sup, track, clock


def _inject(*, sup, track, session):
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        _supervisor_restart.maybe_inject(
            sup=sup, track=track, target=session, eff_ctx=10, threshold=50
        )
    return err.getvalue()


def _stamp(*, sup, repo, topic):
    return registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)


# ## Scenario: A provably failed wrap-up paste still un-opens its round
def test_scenario_a_provably_failed_paste_still_unopens_its_round(*, tmp_path, monkeypatch):
    repo, topic, session, sup, track, _clock = _undelivered_wrapup(
        tmp_path=tmp_path, monkeypatch=monkeypatch, effect_unknown=False
    )

    err = _inject(sup=sup, track=track, session=session)

    assert _stamp(sup=sup, repo=repo, topic=topic) is None
    assert "wrap-up injection FAILED" in err


# ## Scenario: An unconfirmed delivery is completed without re-stamping or re-pasting
def test_scenario_an_unconfirmed_delivery_is_retried_without_restamping(*, tmp_path, monkeypatch):
    repo, topic, session, sup, track, clock = _undelivered_wrapup(
        tmp_path=tmp_path, monkeypatch=monkeypatch, effect_unknown=True
    )
    _inject(sup=sup, track=track, session=session)
    opened = _stamp(sup=sup, repo=repo, topic=topic)
    assert opened is not None

    clock["t"] += 60
    _inject(sup=sup, track=track, session=session)

    assert _stamp(sup=sup, repo=repo, topic=topic) == opened


def test_a_payload_standing_in_the_input_is_submitted_not_pasted_again() -> None:
    writer = _Writer()
    standing = {
        _SESSION: pane_router_submit_signals.PromptState(
            text=_PROMPT, phase="await-enter", effect_unknown=True
        )
    }
    submitter = _submitter(reads=_Reads(captures=[_PASTED, _BUSY]), writer=writer, states=standing)

    assert _submit(submitter=submitter) == (True, False)
    assert writer.pastes == []
    assert writer.enters == 1


# ## Scenario: An unconfirmed wrap-up delivery keeps its round open
def test_scenario_an_unconfirmed_delivery_keeps_its_round_open(*, tmp_path, monkeypatch):
    repo, topic, session, sup, track, clock = _undelivered_wrapup(
        tmp_path=tmp_path, monkeypatch=monkeypatch, effect_unknown=True
    )

    err = _inject(sup=sup, track=track, session=session)

    stamp = _stamp(sup=sup, repo=repo, topic=topic)
    assert stamp is not None
    assert "wrap-up delivery UNCONFIRMED" in err

    # The session got the wrap-up after all, wound down, and declared: it certifies.
    monkeypatch.undo()
    clock["t"] += 5
    declare(repo=repo, topic=topic, value=signals.STATE_READY, mtime=stamp + 1.0)
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=track, act=True)
    assert view.status == "restarting"


# ## Scenario: A held unconfirmed attempt is released when its round closes
def test_scenario_a_held_attempt_is_released_when_its_round_closes(*, tmp_path, monkeypatch):
    repo, topic, session, sup, track, _clock = _undelivered_wrapup(
        tmp_path=tmp_path, monkeypatch=monkeypatch, effect_unknown=True
    )
    _inject(sup=sup, track=track, session=session)
    held = pane_router_submit_signals.PromptState(
        text=_PROMPT, phase="await-enter", effect_unknown=True
    )
    sup.tmux.prompt_states = {session: held, "herdr:another-pane": held}

    _supervisor_state.clear_state(sup=sup, track=track)

    assert _stamp(sup=sup, repo=repo, topic=topic) is None
    # Only THIS track's pane is released; another pane's attempt is not touched.
    assert sup.tmux.prompt_states == {"herdr:another-pane": held}
