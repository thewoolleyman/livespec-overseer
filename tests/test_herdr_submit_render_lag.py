"""A Herdr submit must not read Claude's not-yet-redrawn composer as a failed submit.

Reproduced on 2026-10-12 against released v5.26.0, in the isolated live exercise:
the daemon pasted the wrap-up into a herdr-hosted Claude pane, pressed Enter, and
took its FIRST post-Enter capture before Claude had redrawn. That capture still
showed the pasted prompt in the composer, the observe loop stopped on it, and the
submit was judged failed. Claude did receive and act on the wrap-up and declared
ready, but the daemon had rolled its round back, so every restart was refused
("ready declaration changed before durable binding").
"""

from __future__ import annotations

from typing import Any, cast

import herdr_identity
import herdr_write
import pane_router_reads
import pane_router_submit
import pane_router_submit_signals

__all__: list[str] = []

_TARGET = herdr_identity.HerdrPaneTarget(
    socket_path="/run/herdr-test.sock", server_pid=41, server_starttime="777", pane_id="w1:p1"
)
_SESSION = herdr_identity.encode_herdr_target(target=_TARGET)
_PROMPT = "You are down to 50% of your context.\nPlease start wrapping up.\n" + "line\n" * 40
_RULE = "─" * 40
_COMPOSER = f"● prior response\n{_RULE}\n❯ [Pasted text #1 +41 lines]\n{_RULE}\n  Ctx: 50% left\n"
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
        self.enters = 0

    def bracketed_paste(self, *, target: herdr_identity.HerdrPaneTarget, text: str) -> Any:
        assert target == _TARGET
        assert text == _PROMPT
        return _OK

    def send_enter(self, *, target: herdr_identity.HerdrPaneTarget) -> Any:
        assert target == _TARGET
        self.enters += 1
        return _OK


def _submitter(*, captures: list[str], writer: _Writer) -> pane_router_submit.PromptSubmitter:
    return pane_router_submit.PromptSubmitter(
        reads=cast(pane_router_reads.PaneRoutingReads, _Reads(captures=captures)),
        writer=cast(pane_router_submit_signals.HerdrInput, writer),
        states={},
    )


def test_a_composer_still_showing_the_paste_right_after_enter_is_not_the_verdict() -> None:
    writer = _Writer()
    # Paste observed, then Enter: the first capture is the not-yet-redrawn composer,
    # the next one shows the turn running.
    submitter = _submitter(captures=[_COMPOSER, _COMPOSER, _BUSY], writer=writer)

    submitted, effect_unknown = submitter.submit_prompt_once(
        session=_SESSION, text=_PROMPT, expect_codex=False, sleep=lambda _seconds: None
    )

    assert (submitted, effect_unknown) == (True, False)
    assert writer.enters == 1
    assert submitter.states == {}
