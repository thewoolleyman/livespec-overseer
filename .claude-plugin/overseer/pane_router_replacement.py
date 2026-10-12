"""Guarded Herdr process-replacement delegation for the mixed pane driver."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

import herdr_identity
import herdr_replacement
import herdr_write
import pane_router_reads

__all__: list[str] = ["ReplacementInput", "controller", "target"]


class ReplacementInput(Protocol):
    """The native input surface shared by prompt and process replacement writes."""

    def bracketed_paste(
        self, *, target: herdr_identity.HerdrPaneTarget, text: str
    ) -> herdr_write.WriteOutcome: ...

    def send_enter(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_write.WriteOutcome: ...

    def launch(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        cwd: str,
        command: str,
        env: Mapping[str, str | None],
    ) -> herdr_write.WriteOutcome: ...


def controller(
    *,
    observer: pane_router_reads.HerdrObserver,
    writer: ReplacementInput,
    process_of: herdr_replacement.ProcessReader,
    process_ids: herdr_replacement.ProcessIds,
    terminate_group: herdr_replacement.GroupTerminator,
    login_shells: frozenset[str],
) -> herdr_replacement.ReplacementController:
    """Build a controller from the mixed driver's injected native seams."""
    return herdr_replacement.ReplacementController(
        observer=observer,
        writer=writer,
        process_of=process_of,
        process_ids=process_ids,
        terminate_group=terminate_group,
        login_shells=login_shells,
    )


def target(*, session: str) -> herdr_identity.HerdrPaneTarget:
    """Decode one exact Herdr generation or refuse a foreign backend."""
    decoded = herdr_identity.decode_target(value=session)
    if decoded.herdr is None or decoded.error:
        raise ValueError(decoded.error or "replacement target is not a Herdr pane")
    return decoded.herdr
