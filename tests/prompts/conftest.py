"""Real-tmux rig shared by the discrimination fixtures in this directory.

Ported from `red-green-harness.sh`, whose 24 legs proved these defects on a
private socket. The harness is not tracked and never ran in the gate; these
fixtures put the same legs on the standing `just check` surface.

Every session here lives on a PRIVATE socket (`tmux -L`), unique per test, per
xdist worker AND PER RUN, and is killed in a `finally`. The maintainer's default
socket is never addressed.

That "per run" was missing for a while, in the code and in this sentence, and it
was `overseer-jcw`: the name came from `tmp_path.name` alone, which is the TEST's
identity and is byte-identical across separate pytest invocations. Two concurrent
`just check` runs on one host therefore shared a socket, and the second read the
first's pane. A uniqueness claim is only as good as its narrowest axis.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol

import pytest

__all__: list[str] = []

# A quiet-pane deadline, not an end-to-end wall-clock budget. `overseer-63y` made
# settle expiry fail LOUDLY instead of returning an unsettled pane, which fixed
# the false verdict but exposed that the (c) scrollback leg could exceed this
# value while it was still visibly printing `AFTER-*` lines on a loaded host.
# `settle` therefore renews this budget only while the pane is still changing
# before the requested sentinel has appeared; after the sentinel is present, the
# same budget remains the fail-closed stability deadline.
_SETTLE_TIMEOUT_S = 5.0


class Settle(Protocol):
    def __call__(self, target: str, needle: str, *, fail_on_timeout: bool = False) -> str: ...


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
    # The PID is what makes this unique per RUN. `tmp_path.name` alone is the
    # test's identity and repeats across invocations; under xdist the PID also
    # separates workers, so it subsumes the axis this used to rely on. It stays
    # STABLE within a process, which the `finally` below depends on to kill the
    # server it actually started.
    socket = f"legs-{os.getpid()}-{tmp_path.name}"
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
        # `no branch`, not `no cover`: the body always runs, but WHETHER the
        # loop iterates a second time is decided by how fast the machine draws
        # a pane. Both the sleep-then-check ordering below and this pragma
        # exist because the same file measured 100% locally and 95% in CI —
        # first the sleep never ran, then the loop-back arc was never taken. A
        # gate whose verdict depends on host speed is not a gate, and the
        # honest fix is to say the arc is timing-dependent rather than to
        # contrive a test that forces a second iteration.
        while time.monotonic() < deadline:
            # Sleep BEFORE the check: checking first makes this line's
            # execution depend on the sentinel not being present yet.
            time.sleep(0.05)
            # The pragma belongs HERE, on the `if`, not on the `while` — the
            # arc coverage reports missing is this branch's FALSE side (loop
            # back for another poll), which is untaken whenever the sentinel is
            # already there on the first look. Putting it on the loop header
            # did nothing, measured twice in the pinned image.
            if needle in tmux("capture-pane", "-p", "-t", target).stdout:  # pragma: no branch
                return
        # COVERAGE-EXEMPT: reached only if the sentinel never appears within the
        # timeout. Returning lets the CALLER's assertion report the real pane
        # contents, which is a far better failure message than a timeout
        # traceback — do not convert this into a raise.
        return  # pragma: no cover

    return _wait_for


@pytest.fixture(name="settle")
def _settle_fixture(*, tmux: Callable[..., subprocess.CompletedProcess[str]]) -> Settle:
    """Wait until a pane contains `needle` AND stops changing.

    Never a fixed sleep: a fixed wait after `send-keys` races the pane's own
    rendering, and the typed command line contains the text under test, so an
    eager capture reads the command being typed and the assertion flaps. That
    race made an earlier version of this suite fail about one run in four.
    """

    def _settle(target: str, needle: str, *, fail_on_timeout: bool = False) -> str:
        deadline = time.monotonic() + _SETTLE_TIMEOUT_S
        previous = "\x00never-captured"
        saw_needle = False
        while time.monotonic() < deadline:
            current = tmux("capture-pane", "-p", "-t", target).stdout
            current_has_needle = needle in current
            if current_has_needle and current == previous:
                return current
            if not saw_needle and current != previous:
                deadline = time.monotonic() + _SETTLE_TIMEOUT_S
            saw_needle = saw_needle or current_has_needle
            previous = current
            time.sleep(0.1)
        if fail_on_timeout:
            pytest.fail(
                f"tmux pane did not settle before the timeout; last capture was:\n{previous}"
            )
        # COVERAGE-EXEMPT: reached only if a pane never settles within the
        # timeout. Unreachable on a healthy run, kept so a hung pane yields the
        # last capture instead of raising — the caller's assertion then reports
        # the actual pane contents, which is a far better failure message than
        # a timeout traceback. Callers whose own command text can match the
        # assertion under test may opt into the fail-closed path above.
        return previous  # pragma: no cover

    return _settle
