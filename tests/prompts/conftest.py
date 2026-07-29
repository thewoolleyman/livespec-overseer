"""Real-tmux rig shared by the discrimination fixtures in this directory.

Ported from `red-green-harness.sh`, whose 24 legs proved these defects on a
private socket. The harness is not tracked and never ran in the gate; these
fixtures put the same legs on the standing `just check` surface.

Every session here lives on a PRIVATE socket (`tmux -L`), unique per test and
per xdist worker, and is killed in a `finally`. The maintainer's default socket
is never addressed.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

__all__: list[str] = []

_SETTLE_TIMEOUT_S = 5.0


def _tmux(socket: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Invoke tmux on a private socket.

    S603/S607 are suppressed DELIBERATELY and narrowly, matching the reasoning
    already landed in `test_emitted_commands_discriminate.py`: the argv is a
    LIST with no shell and no untrusted input, and resolving `tmux` through
    PATH is LOAD-BEARING — these legs must exercise whatever tmux the
    environment provides (measured green on the host's 3.5a and on 3.4 in the
    pinned CI image), so an absolute path would make them pass or fail for
    environmental reasons instead of for the behaviour under test.
    """
    return subprocess.run(  # noqa: S603
        ["tmux", "-L", socket, *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(name="tmux")
def _tmux_fixture(*, tmp_path: Path) -> Iterator[Callable[..., subprocess.CompletedProcess[str]]]:
    """A private tmux socket, bound into a call helper and torn down after."""
    # COVERAGE-EXEMPT ON PURPOSE — DO NOT DELETE THIS GUARD AS DEAD CODE.
    # Unreachable whenever tmux IS present, i.e. every run that reaches 100%
    # coverage — so the line that makes these modules REFUSE TO SKIP is exactly
    # the one a fail_under=100 gate would otherwise reject. Deleting it makes
    # coverage happy and silently restores skip-on-missing-tmux, which is the
    # defect class these fixtures exist to prove.
    if shutil.which("tmux") is None:  # pragma: no cover
        pytest.fail(
            "tmux is required by this contract's acceptance and is absent. "
            "This must FAIL rather than skip: a skipped leg proves nothing."
        )
    socket = f"legs-{tmp_path.name}"
    try:
        yield lambda *args: _tmux(socket, *args)
    finally:
        _tmux(socket, "kill-server")


@pytest.fixture(name="wait_for")
def _wait_for_fixture(
    *, tmux: Callable[..., subprocess.CompletedProcess[str]]
) -> Callable[[str, str], None]:
    """Block until `needle` APPEARS in a pane — no stability requirement.

    Distinct from `settle`, and the distinction is the difference between a
    flaky leg and a deterministic one. `settle` waits for a pane to STOP
    changing, which a deliberately-churning pane never does. Waiting on the
    sentinel instead of on a fixed sleep is the same fix that took the original
    harness from failing about one run in four to ten green runs in a row; the
    first draft of the busy leg used `time.sleep(0.8)` and flaked at ~1-in-3
    when the shell had not yet started the loop.
    """

    def _wait_for(target: str, needle: str) -> None:
        deadline = time.monotonic() + _SETTLE_TIMEOUT_S
        while time.monotonic() < deadline:
            if needle in tmux("capture-pane", "-p", "-t", target).stdout:
                return
            time.sleep(0.05)
        # COVERAGE-EXEMPT: reached only if the sentinel never appears within the
        # timeout. Returning lets the CALLER's assertion report the real pane
        # contents, which is a far better failure message than a timeout
        # traceback — do not convert this into a raise.
        return  # pragma: no cover

    return _wait_for


@pytest.fixture(name="settle")
def _settle_fixture(
    *, tmux: Callable[..., subprocess.CompletedProcess[str]]
) -> Callable[[str, str], str]:
    """Wait until a pane contains `needle` AND stops changing.

    Never a fixed sleep: a fixed wait after `send-keys` races the pane's own
    rendering, and the typed command line contains the text under test, so an
    eager capture reads the command being typed and the assertion flaps. That
    race made an earlier version of this suite fail about one run in four.
    """

    def _settle(target: str, needle: str) -> str:
        deadline = time.monotonic() + _SETTLE_TIMEOUT_S
        previous = "\x00never-captured"
        while time.monotonic() < deadline:
            current = tmux("capture-pane", "-p", "-t", target).stdout
            if needle in current and current == previous:
                return current
            previous = current
            time.sleep(0.1)
        # COVERAGE-EXEMPT: reached only if a pane never settles within the
        # timeout. Unreachable on a healthy run, kept so a hung pane yields the
        # last capture instead of raising — the caller's assertion then reports
        # the actual pane contents, which is a far better failure message than
        # a timeout traceback.
        return previous  # pragma: no cover

    return _settle
