"""The native Herdr Enter retry recognizes a collapsed multi-line payload in the composer.

Claude collapses a multi-line paste (a daemon wrap-up) to ``[Pasted text #N +K lines]``.
That placeholder proves the payload landed only when the expected payload is multi-line,
so the retry must judge the FULL retained text, not its first line.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import herdr_adapter
import herdr_identity
import herdr_write
import pane_router
import pane_router_reads
import pane_router_submit_signals
from test_supervisor_builders import FakeTmux

WRAPUP = "wind down now\nstep one\nstep two"
RULE = "─" * 40
PASTED = f"● prior output\n{RULE}\n❯ [Pasted text #1 +2 lines]\n{RULE}\n  Ctx: 20% left\n"
SUBMITTED = f"● Working… (3s · esc to interrupt)\n{RULE}\n❯ \n{RULE}\n  Ctx: 20% left\n"


def _target(*, tmp_path: Path) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=str(tmp_path / "herdr.sock"),
            server_pid=700,
            server_starttime="server-start",
            pane_id="w1:p9",
        )
    )


def _retry(*, tmp_path: Path, captures: list[str], text: str) -> tuple[tuple[bool, bool], int]:
    sent: list[str] = []

    def send_enter(*, target: herdr_identity.HerdrPaneTarget) -> herdr_write.WriteOutcome:
        sent.append(target.pane_id)
        return herdr_write.WriteOutcome(ok=True, error="", effect_unknown=False)

    observer = SimpleNamespace(
        capture_pane=lambda *, target, retain_ansi: herdr_adapter.PaneCapture(
            ok=True,
            text=captures.pop(0) if len(captures) > 1 else captures[0],
            error="",
        )
    )
    driver = pane_router.MixedPaneDriver(
        tmux=FakeTmux(),
        herdr=cast(pane_router_reads.HerdrObserver, observer),
        herdr_writer=cast(
            pane_router_submit_signals.HerdrInput, SimpleNamespace(send_enter=send_enter)
        ),
    )
    result = driver.retry_prompt_enter_once(
        session=_target(tmp_path=tmp_path), text=text, sleep=lambda _seconds: None
    )
    return result, len(sent)


def test_native_retry_presses_enter_for_a_collapsed_multiline_wrapup(*, tmp_path: Path) -> None:
    result, sent = _retry(tmp_path=tmp_path, captures=[PASTED, SUBMITTED], text=WRAPUP)

    assert sent == 1
    assert result == (True, False)


def test_native_retry_leaves_a_single_line_payload_behind_a_placeholder_alone(
    *, tmp_path: Path
) -> None:
    result, sent = _retry(tmp_path=tmp_path, captures=[PASTED], text="wind down now")

    assert sent == 0
    assert result == (False, False)
