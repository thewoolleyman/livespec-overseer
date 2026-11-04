"""The native Enter retry authorizes Enter only from the Codex composer row."""

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
import pytest
from test_supervisor_builders import FakeTmux

RESUME = "read the durable handoff"
STATUS = "  gpt-5.5 high · /repo · topic\n"
SCROLLBACK_ONLY = f"› {RESUME}\n● working on it\n\n› \n{STATUS}"
COMPOSER_HOLDS = f"● earlier output\n\n› {RESUME}\n{STATUS}"


def _target(*, tmp_path: Path) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=str(tmp_path / "herdr.sock"),
            server_pid=700,
            server_starttime="server-start",
            pane_id="w1:p9",
        )
    )


def _retry(*, tmp_path: Path, captures: list[str]) -> tuple[tuple[bool, bool], list[str]]:
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
        session=_target(tmp_path=tmp_path), text=RESUME, sleep=lambda _seconds: None
    )
    return result, sent


def test_native_retry_does_not_press_enter_for_text_only_in_scrollback(*, tmp_path: Path) -> None:
    result, sent = _retry(tmp_path=tmp_path, captures=[SCROLLBACK_ONLY])

    assert result == (False, False)
    assert sent == []


def test_native_retry_does_not_press_enter_when_the_composer_clears_before_recapture(
    *, tmp_path: Path
) -> None:
    result, sent = _retry(tmp_path=tmp_path, captures=[SCROLLBACK_ONLY, SCROLLBACK_ONLY])

    assert result == (False, False)
    assert sent == []


@pytest.mark.parametrize("busy", [True, False])
def test_native_retry_presses_enter_when_the_composer_holds_the_text(
    *, tmp_path: Path, busy: bool
) -> None:
    after = "• Working (3s • esc to interrupt)\n" + COMPOSER_HOLDS if busy else SCROLLBACK_ONLY
    result, sent = _retry(tmp_path=tmp_path, captures=[COMPOSER_HOLDS, after])

    assert len(sent) == 1
    assert result == ((True, False) if busy else (False, True))
