"""CANDIDATE FIXTURE for S1/S2 — the emitted commands must DISCRIMINATE.

STAGING DRAFT. Not filed, not committed. Destination is `tests/prompts/` when
S1 lands; it is placed here so the slice starts from working test code rather
than from a shell script.

WHY THIS EXISTS ALONGSIDE `test_generated_supervisor_handoff_contract.py`.
That module asserts a charter CONTAINS the required text. `overseer-hbr.4`
raised the bar from "mentions a rule" to "emits a runnable command". These
defects clear both bars: the shipped commands are present, runnable, and they
answer WRONGLY. So this module asserts on BEHAVIOUR — it runs each emitted form
against a rigged tmux topology and requires the right verdict.

THE TOPOLOGY IS THE WHOLE POINT. `<topic>` is always a strict prefix of
`<topic>-supervisor`, and a bare `-t <name>` prefix-matches. So with the worker
ABSENT and only the supervisor alive, every bare-target command resolves onto
the supervisor's own pane: preconditions report a live worker that does not
exist, and — the severe case — `send-keys` and `paste-buffer` DELIVER THE
WORKER'S BRIEF INTO THE SUPERVISOR and return 0.

NO SKIPS. If tmux is unavailable this module FAILS rather than skipping. A
skipped acceptance leg is a verifier that cannot fail, which is the exact defect
class this thread exists to remove; a green suite that silently tested nothing
would be worse than a red one.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

_WORKER = "rgw"
_SUPERVISOR = "rgw-supervisor"
# The one correct spelling: leading `=` for exact match, trailing colon
# REQUIRED. Measured across has-session / display-message / capture-pane /
# send-keys / list-panes — no other spelling is correct in all five.
_EXACT_WORKER = f"={_WORKER}:"
_EXACT_SUPERVISOR = f"={_SUPERVISOR}:"


def _tmux_call(socket: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Thin positional shim: tmux argv is inherently ordered.

    The repo's test surface is keyword-only by convention (352 signatures use
    the `*` separator) even though `tests/` sits outside the enforced
    `source_trees`. Every TEST below follows that convention; this one helper
    keeps a positional varargs tail because an argv list is a sequence, not a
    set of named options.
    """
    # S603/S607 suppressed DELIBERATELY and narrowly, not waved through:
    # S603 — argv is fully controlled (literal `tmux`, a socket name derived
    #   from pytest's own tmp_path, test-supplied flags). A LIST with no shell,
    #   so there is no untrusted input and no word splitting.
    # S607 — resolving `tmux` through PATH is LOAD-BEARING, not laziness. This
    #   fixture must exercise whatever tmux the environment actually provides:
    #   measured green on the host's tmux 3.5a AND on tmux 3.4 in the pinned CI
    #   image. An absolute path would make it pass or fail for environmental
    #   reasons instead of for the behaviour under test.
    return subprocess.run(  # noqa: S603
        ["tmux", "-L", socket, *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def _tmux_socket_path(*, socket: str) -> Path:
    base = Path(os.environ.get("TMUX_TMPDIR", "/tmp"))
    return base / f"tmux-{os.getuid()}" / socket


@pytest.fixture(name="socket")
def _socket(*, tmp_path: Path) -> Iterator[str]:
    """A private tmux socket holding ONLY the supervisor — the rigged topology.

    Private so the maintainer's default socket is never touched, and torn down
    on the way out even if a test fails.
    """
    # COVERAGE-EXEMPT ON PURPOSE — DO NOT DELETE THIS GUARD AS DEAD CODE.
    # It is unreachable whenever tmux IS present, i.e. every run that reaches
    # 100% coverage — so the line asserting we REFUSE TO SKIP is precisely the
    # one a fail_under=100 gate would otherwise reject. Deleting it makes
    # coverage happy and silently restores skip-on-missing-tmux, which is the
    # exact defect class this fixture exists to prove.
    if shutil.which("tmux") is None:  # pragma: no cover
        pytest.fail(
            "tmux is required by this contract's acceptance and is absent. "
            "This must FAIL rather than skip: a skipped leg proves nothing, and "
            "these commands can only be judged by running them."
        )
    # PID for the same reason as `conftest.py`'s rig, and this is the SECOND
    # instance of that defect: `tmp_path.name` is the test's identity and repeats
    # across runs, so two concurrent suites shared this socket and one read the
    # other's supervisor pane. Fixing only the shared conftest left this one
    # live — a per-module socket scheme is a per-module copy of the bug.
    name = f"disc-{os.getpid()}-{tmp_path.name}"
    _tmux_call(
        name, "new-session", "-d", "-s", _SUPERVISOR, "-x", "80", "-y", "20", "-c", str(tmp_path)
    )
    _settle(socket=name, target=_EXACT_SUPERVISOR)
    try:
        yield name
    finally:
        _tmux_call(name, "kill-server")
        _tmux_socket_path(socket=name).unlink(missing_ok=True)


def _settle(*, socket: str, target: str, timeout_s: float = 4.0) -> str:
    """Wait until the pane renders AND stops changing; never a fixed sleep.

    A fixed sleep after `send-keys` races the pane's own rendering, and the
    typed command line contains the text under test — so an eager capture reads
    the command being typed and the assertion flaps. Measured: that race made an
    earlier version of this suite fail about one run in four.
    """
    deadline = time.monotonic() + timeout_s
    previous = "\x00never-captured"
    while time.monotonic() < deadline:
        current = _tmux_call(socket, "capture-pane", "-p", "-t", target).stdout
        if current and current == previous:
            return current
        previous = current
        time.sleep(0.1)
    # COVERAGE-EXEMPT: reached only if a pane never stops changing within the
    # timeout. Unreachable on a healthy run, kept so a hung pane yields the
    # last capture instead of raising.
    return previous  # pragma: no cover


def _supervisor_pane(*, socket: str) -> str:
    return _tmux_call(socket, "capture-pane", "-p", "-t", _EXACT_SUPERVISOR).stdout


# --------------------------------------------------------------------------
# The severe case: drive commands that DELIVER into the wrong pane.
# --------------------------------------------------------------------------


def test_the_bare_target_send_keys_delivers_into_the_supervisor(*, socket: str) -> None:
    """The defect, pinned. Without this the fix below proves nothing.

    Sabotage that reddens this: none needed — it asserts the BROKEN behaviour,
    so it fails the day tmux stops prefix-matching, which is exactly when the
    remedy below stops being necessary.
    """
    _tmux_call(socket, "send-keys", "-t", _WORKER, "echo BARE_SENTINEL")
    _settle(socket=socket, target=_EXACT_SUPERVISOR)
    assert "BARE_SENTINEL" in _supervisor_pane(socket=socket), (
        "expected the bare target to leak into the supervisor's pane; if this "
        "no longer holds, re-derive the remedy rather than deleting the test"
    )


def test_the_exact_target_send_keys_reaches_no_pane(*, socket: str) -> None:
    """The remedy. RED: replace `_EXACT_WORKER` with `_WORKER`."""
    _tmux_call(socket, "send-keys", "-t", _EXACT_WORKER, "echo EXACT_SENTINEL")
    _settle(socket=socket, target=_EXACT_SUPERVISOR)
    assert "EXACT_SENTINEL" not in _supervisor_pane(socket=socket)


def test_the_bare_target_paste_buffer_leaks_the_whole_brief(*, socket: str, tmp_path: Path) -> None:
    """Worse than send-keys: this is the LONG-BRIEF delivery path.

    A mistargeted paste puts a whole multi-paragraph instruction into the
    supervisor's own agent rather than a single line.
    """
    brief = tmp_path / "brief.txt"
    brief.write_text("PASTE_SENTINEL line one\nPASTE_SENTINEL line two\n", encoding="utf-8")
    _tmux_call(socket, "load-buffer", "-b", "disc", str(brief))
    _tmux_call(socket, "paste-buffer", "-b", "disc", "-t", _WORKER)
    _settle(socket=socket, target=_EXACT_SUPERVISOR)
    assert "PASTE_SENTINEL" in _supervisor_pane(socket=socket)


def test_the_exact_target_paste_buffer_reaches_no_pane(*, socket: str, tmp_path: Path) -> None:
    """RED: replace `_EXACT_WORKER` with `_WORKER`."""
    brief = tmp_path / "brief.txt"
    brief.write_text("PASTE_EXACT_SENTINEL\n", encoding="utf-8")
    _tmux_call(socket, "load-buffer", "-b", "disc", str(brief))
    _tmux_call(socket, "paste-buffer", "-b", "disc", "-t", _EXACT_WORKER)
    _settle(socket=socket, target=_EXACT_SUPERVISOR)
    assert "PASTE_EXACT_SENTINEL" not in _supervisor_pane(socket=socket)


# --------------------------------------------------------------------------
# Preconditions: each must be able to return FALSE.
# --------------------------------------------------------------------------


def test_the_bare_existence_check_cannot_detect_a_missing_worker(*, socket: str) -> None:
    """`has-session -t <name>` exits 0 by prefix-matching `<name>-supervisor`."""
    assert _tmux_call(socket, "has-session", "-t", _WORKER).returncode == 0


def test_the_exact_existence_check_detects_a_missing_worker(*, socket: str) -> None:
    """RED: drop the `=` or the trailing colon."""
    assert _tmux_call(socket, "has-session", "-t", _EXACT_WORKER).returncode != 0


def test_the_bare_pane_resolution_returns_the_supervisors_own_pane(*, socket: str) -> None:
    """Precondition 2's process-tree walk inspects the SUPERVISOR when bare."""
    bare = _tmux_call(socket, "display-message", "-p", "-t", _WORKER, "#{pane_pid}").stdout.strip()
    supervisor = _tmux_call(
        socket, "display-message", "-p", "-t", _EXACT_SUPERVISOR, "#{pane_pid}"
    ).stdout.strip()
    assert bare and bare == supervisor


def test_the_exact_pane_resolution_yields_nothing_for_an_absent_worker(*, socket: str) -> None:
    """RED: drop the trailing colon — the value goes empty even when it EXISTS,
    and an empty value laundered through `readlink -f` becomes a containment
    PASS, so the two defects compose."""
    resolved = _tmux_call(
        socket, "display-message", "-p", "-t", _EXACT_WORKER, "#{pane_pid}"
    ).stdout.strip()
    assert resolved == ""


# --------------------------------------------------------------------------
# THE CONTROL. Without it, "refuse everything" passes every test above.
# --------------------------------------------------------------------------


def test_the_control_the_exact_form_still_drives_a_live_worker(
    *, socket: str, tmp_path: Path
) -> None:
    """The exact form must DELIVER when the worker exists.

    Every assertion above is satisfied by a remedy that simply never sends
    anything. This is the leg that makes them mean something — the same role
    `test_the_control_a_fully_conformant_charter_passes` plays in the sibling
    contract module.
    """
    _tmux_call(
        socket, "new-session", "-d", "-s", _WORKER, "-x", "80", "-y", "20", "-c", str(tmp_path)
    )
    _settle(socket=socket, target=_EXACT_WORKER)
    _tmux_call(socket, "send-keys", "-t", _EXACT_WORKER, "echo DELIVERY_CONTROL")
    worker_pane = _settle(socket=socket, target=_EXACT_WORKER)
    assert "DELIVERY_CONTROL" in worker_pane
    assert "DELIVERY_CONTROL" not in _supervisor_pane(socket=socket)
