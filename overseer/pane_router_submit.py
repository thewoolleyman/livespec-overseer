"""Verified native prompt delivery for instance-qualified Herdr panes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import cast

import herdr_identity
import herdr_write
import pane_router_reads
import pane_router_submit_signals

__all__: list[str] = ["PromptSubmitter"]

_OBSERVE_ATTEMPTS = 3
_OBSERVE_INTERVAL = 0.5
_AWAIT_PASTE = "await-paste"
_AWAIT_ENTER = "await-enter"
_UNCERTAIN_PASTE = "uncertain-paste"


@dataclass(kw_only=True)
class PromptSubmitter:
    reads: pane_router_reads.PaneRoutingReads
    writer: pane_router_submit_signals.HerdrInput
    states: dict[str, pane_router_submit_signals.PromptState]

    def _observe(
        self,
        *,
        session: str,
        sleep: Callable[[float], None],
        accept: pane_router_submit_signals.CapturePredicate,
    ) -> str:
        capture = ""
        for attempt in range(_OBSERVE_ATTEMPTS):
            capture = self.reads.capture_pane(session=session)
            if accept(capture=capture):
                break
            if attempt + 1 < _OBSERVE_ATTEMPTS:
                sleep(_OBSERVE_INTERVAL)
        return capture

    def _observe_paste(
        self,
        *,
        session: str,
        sleep: Callable[[float], None],
        state: pane_router_submit_signals.PromptState,
        prompt_visible: pane_router_submit_signals.CapturePredicate,
    ) -> tuple[bool | None, bool]:
        capture = self._observe(session=session, sleep=sleep, accept=prompt_visible)
        return {
            True: (None, False),
            False: (False, state.effect_unknown),
        }[prompt_visible(capture=capture)]

    def _clear_submission(self, *, session: str) -> tuple[bool, bool]:
        _ = self.states.pop(session, None)
        return True, False

    def _resume_enter(
        self,
        *,
        session: str,
        sleep: Callable[[float], None],
        state: pane_router_submit_signals.PromptState,
        prompt_visible: pane_router_submit_signals.CapturePredicate,
        submitted: pane_router_submit_signals.CapturePredicate,
    ) -> tuple[bool | None, bool]:
        resolved = partial(
            pane_router_submit_signals.resolved,
            prompt_visible=prompt_visible,
            submitted=submitted,
        )
        capture = self._observe(session=session, sleep=sleep, accept=resolved)
        routes = {
            True: partial(self._clear_submission, session=session),
            False: partial(
                self._resume_unconfirmed,
                capture=capture,
                state=state,
                prompt_visible=prompt_visible,
            ),
        }
        return routes[submitted(capture=capture)]()

    @staticmethod
    def _resume_unconfirmed(
        *,
        capture: str,
        state: pane_router_submit_signals.PromptState,
        prompt_visible: pane_router_submit_signals.CapturePredicate,
    ) -> tuple[bool | None, bool]:
        return {
            True: (None, False),
            False: (False, state.effect_unknown),
        }[prompt_visible(capture=capture)]

    def _prepare_prompt(
        self,
        *,
        session: str,
        text: str,
        target: herdr_identity.HerdrPaneTarget,
        sleep: Callable[[float], None],
        prompt_visible: pane_router_submit_signals.CapturePredicate,
        submitted: pane_router_submit_signals.CapturePredicate,
    ) -> tuple[bool | None, bool]:
        state = self.states.get(session)
        if state is None:
            pasted = self.writer.bracketed_paste(target=target, text=text)
            state = pane_router_submit_signals.PromptState(
                text=text,
                phase=_UNCERTAIN_PASTE if pasted.effect_unknown else _AWAIT_PASTE,
                effect_unknown=pasted.effect_unknown,
            )
            known_failure = not pasted.ok and not pasted.effect_unknown
            self.states.update({True: {}, False: {session: state}}[known_failure])
            observed = self._observe_paste(
                session=session,
                sleep=sleep,
                state=state,
                prompt_visible=prompt_visible,
            )
            return {True: (False, False), False: observed}[known_failure]
        if state.phase in {_AWAIT_PASTE, _UNCERTAIN_PASTE}:
            return self._observe_paste(
                session=session,
                sleep=sleep,
                state=state,
                prompt_visible=prompt_visible,
            )
        return self._resume_enter(
            session=session,
            sleep=sleep,
            state=state,
            prompt_visible=prompt_visible,
            submitted=submitted,
        )

    def _finish_submit(
        self,
        *,
        session: str,
        text: str,
        entered: herdr_write.WriteOutcome,
        capture: str,
        prompt_visible: pane_router_submit_signals.CapturePredicate,
        submitted: pane_router_submit_signals.CapturePredicate,
    ) -> tuple[bool, bool]:
        if submitted(capture=capture):
            return self._clear_submission(session=session)
        mutation_may_have_landed = entered.ok | entered.effect_unknown
        effect_unknown = {
            True: False,
            False: mutation_may_have_landed,
        }[prompt_visible(capture=capture)]
        self.states[session] = pane_router_submit_signals.PromptState(
            text=text,
            phase=_AWAIT_ENTER,
            effect_unknown=effect_unknown,
        )
        return False, effect_unknown

    def submit_prompt_once(
        self,
        *,
        session: str,
        text: str,
        expect_codex: bool,
        sleep: Callable[[float], None],
    ) -> tuple[bool, bool]:
        """Observe the paste before Enter and the submit before reporting success."""
        del expect_codex
        target = cast(
            herdr_identity.HerdrPaneTarget,
            self.reads.decode(value=session).herdr,
        )
        existing = self.states.get(session)
        active_text = text if existing is None else existing.text
        same_request = active_text == text
        prompt_visible = partial(pane_router_submit_signals.prompt_visible, text=active_text)
        submitted = pane_router_submit_signals.submitted
        prepared, effect_unknown = self._prepare_prompt(
            session=session,
            text=active_text,
            target=target,
            sleep=sleep,
            prompt_visible=prompt_visible,
            submitted=submitted,
        )
        if prepared is not None:
            return {True: (prepared, effect_unknown), False: (False, effect_unknown)}[same_request]
        entered = self.writer.send_enter(target=target)
        resolved = partial(
            pane_router_submit_signals.resolved,
            prompt_visible=prompt_visible,
            submitted=submitted,
        )
        capture = self._observe(
            session=session,
            sleep=sleep,
            accept=resolved,
        )
        result = self._finish_submit(
            session=session,
            text=active_text,
            entered=entered,
            capture=capture,
            prompt_visible=prompt_visible,
            submitted=submitted,
        )
        return {True: result, False: (False, result[1])}[same_request]
