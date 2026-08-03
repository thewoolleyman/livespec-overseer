"""Defects (c), (c'), (d), and S4 condition-watcher predicates: wake mechanisms.

(c)  `capture-pane -S -N` returns `min(N, scrollback)` PLUS THE ENTIRE VISIBLE
     PANE — never "the last N lines". Measured on a 20-row pane: no `-S` = 20
     lines, `-S -15` = 35, `-S -40` = 60. So a picker footer sitting in
     SCROLLBACK fires the wake on the first poll, permanently.

(c') Visible-only capture is NECESSARY BUT NOT SUFFICIENT: a brief that QUOTES
     the footer false-wakes, and every charter documenting this rule quotes it.
     NEITHER AVAILABLE FIX IS SUFFICIENT ALONE — the union of a line-anchored
     test and a footer-SHAPE test is required, and the anchor must bind BOTH
     ends, because a start-only anchor is defeated by terminal WRAPPING.

(d)  `prev=""` watcher init: an unresolvable target's empty capture equals
     `prev` on iteration 1, so the watcher reports IDLE when the session does
     not exist.

All three share one function, so they share one module. Each shipped form is
PINNED as wrong; the controls prove the remedies did not simply stop waking.
"""

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Callable
from typing import Protocol

import pytest

__all__: list[str] = []

_PICKER, _IDLE, _LOST, _BUSY = "PICKER", "IDLE", "LOST", "BUSY"
_PENDING = "PENDING"
_POLLS = 4
_STABLE_TO_IDLE = 3
_VISIBLE_TAIL = 8
_PANE_CHANGE_TIMEOUT_S = 5.0

# END-anchored: a wrapped continuation line can BEGIN with "Enter to select"
# (measured — the echoed command wrapped at that exact column), so anchoring
# only the start re-introduces the (c') false positive.
_ANCHORED = re.compile(r"^[ \t]*Enter to (select|confirm)[ \t]*$", re.MULTILINE)
# The footer SHAPE: two "<key> to <verb>" clauses joined by a separator. This
# is the half that catches a REAL footer carrying trailing text, which the
# anchored half cannot match.
_SHAPE = re.compile(r"[^ ]+ to [a-z]+([,]| [^ a-zA-Z0-9]+) +[^ ]+ to [a-z]+")

Tmux = Callable[..., subprocess.CompletedProcess[str]]


class Settle(Protocol):
    def __call__(self, target: str, needle: str, *, fail_on_timeout: bool = False) -> str: ...


def _looks_like_picker(*, pane: str) -> bool:
    """Positional test over the last lines of CONTENT, not of the pane grid.

    Measured, and it cost a debugging round: a tmux pane is a fixed grid, so
    after a `clear` the content sits at the TOP and the final rows are blank.
    Taking the last N lines of the RAW capture then yields nothing but empties
    and a real footer goes undetected — the positional anchor silently stops
    discriminating, which is this thread's own defect class. Trailing blanks
    are stripped first so "near the bottom" means near the bottom of what was
    actually written.
    """
    tail = "\n".join(pane.rstrip().splitlines()[-_VISIBLE_TAIL:])
    return bool(_ANCHORED.search(tail) or _SHAPE.search(tail))


def watcher_shipped(*, tmux: Tmux, target: str) -> str:
    """Scrollback-fed capture, bare target, substring test, `prev=""` init."""
    previous, stable = "", 0
    for _ in range(_POLLS):
        pane = tmux("capture-pane", "-p", "-t", target, "-S", "-40").stdout
        if "Enter to select" in pane:
            return _PICKER
        if pane == previous:
            stable += 1
        else:
            stable, previous = 0, pane
        if stable >= _STABLE_TO_IDLE:
            return _IDLE
        time.sleep(0.15)
    return _BUSY


def watcher_proposed(*, tmux: Tmux, target: str) -> str:
    """Visible-only capture, exact target, union picker test, sentinel init."""
    previous, stable = "\x00never-captured", 0
    for _ in range(_POLLS):
        pane = tmux("capture-pane", "-p", "-t", target).stdout
        if not pane:
            return _LOST
        if _looks_like_picker(pane=pane):
            return _PICKER
        if pane == previous:
            stable += 1
        else:
            stable, previous = 0, pane
        if stable >= _STABLE_TO_IDLE:
            return _IDLE
        time.sleep(0.15)
    return _BUSY


def pr_condition_watcher_shipped(*, pr: dict[str, str]) -> str:
    """Derived-field-only PR watcher shape from the S4 live failure."""
    match pr["mergeStateStatus"]:
        case "CLEAN" | "UNSTABLE" | "HAS_HOOKS" | "DIRTY" | "BEHIND" | "CONFLICTING":
            return _PENDING
        case _:
            return "WAKE: PR watcher expired still BLOCKED - RE-ARM or inspect checks"


def pr_condition_watcher_proposed(*, pr: dict[str, str]) -> str:
    """Terminal authoritative field first, then derived detail, then fail-open."""
    match pr["state"]:
        case "MERGED":
            return "WAKE: PR state=MERGED"
        case "CLOSED":
            return "WAKE: PR state=CLOSED"
        case "OPEN":
            pass
        case unknown:
            return f"WAKE: unrecognized PR state={unknown}"

    match pr["mergeStateStatus"]:
        case "CLEAN":
            return "WAKE: PR mergeable state=CLEAN"
        case "UNSTABLE" | "HAS_HOOKS" | "DIRTY" | "BEHIND" | "CONFLICTING":
            return _PENDING
        case unknown:
            return f"WAKE: unrecognized mergeStateStatus={unknown}"


def _worker(*, tmux: Tmux, rows: str = "20") -> str:
    tmux("new-session", "-d", "-s", "wk", "-x", "80", "-y", rows)
    return "=wk:"


def _run(
    *,
    tmux: Tmux,
    command: str,
    settle: Settle,
    needle: str,
    fail_on_timeout: bool = False,
) -> None:
    tmux("send-keys", "-t", "=wk:", command, "Enter")
    settle("=wk:", needle, fail_on_timeout=fail_on_timeout)


def _wait_for_change_on_watcher_sleep(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmux: Tmux,
    target: str,
) -> None:
    """Make watcher sleeps observe pane progress instead of assuming cadence."""
    real_sleep = time.sleep

    def _sleep_until_changed(seconds: float) -> None:
        previous = tmux("capture-pane", "-p", "-t", target).stdout
        deadline = time.monotonic() + max(seconds, _PANE_CHANGE_TIMEOUT_S)
        while time.monotonic() < deadline:
            real_sleep(0.05)
            current = tmux("capture-pane", "-p", "-t", target).stdout
            if current != previous:
                return
        # COVERAGE-EXEMPT: reached only if a deliberately changing pane stops
        # advancing before the deadline. Healthy runs prove the positive path;
        # this timeout makes a rig failure loud instead of returning IDLE.
        pytest.fail(  # pragma: no cover
            "tmux pane did not change during watcher sleep; " f"last capture was:\n{previous}"
        )

    monkeypatch.setattr(time, "sleep", _sleep_until_changed)


def test_settle_can_fail_loudly_on_expiry(
    *, monkeypatch: pytest.MonkeyPatch, settle: Settle
) -> None:
    import conftest as prompt_conftest

    monkeypatch.setattr(prompt_conftest, "_SETTLE_TIMEOUT_S", 0.0)

    with pytest.raises(pytest.fail.Exception) as exc_info:
        settle("=wk:", "NEVER-APPEARS", fail_on_timeout=True)

    assert "tmux pane did not settle before the timeout" in str(exc_info.value)


def test_c_a_footer_in_scrollback_wakes_the_shipped_watcher(
    *, monkeypatch: pytest.MonkeyPatch, tmux: Tmux, settle: Callable[[str, str], str]
) -> None:
    """DEFECT (c) PINNED: the footer has SCROLLED OFF and it still wakes."""
    import conftest as prompt_conftest

    monkeypatch.setattr(prompt_conftest, "_SETTLE_TIMEOUT_S", 0.5)
    _worker(tmux=tmux)
    _run(
        tmux=tmux,
        command=(
            'printf "%s\\n" "  up/dn to navigate, Enter to select, Esc to cancel"; '
            'for i in $(seq 1 25); do echo "AFTER-$i"; sleep 0.05; done'
        ),
        settle=settle,
        needle="AFTER-25",
        fail_on_timeout=True,
    )
    assert watcher_shipped(tmux=tmux, target="wk") == _PICKER


def test_c_a_footer_in_scrollback_does_not_wake_the_proposed_watcher(
    *, monkeypatch: pytest.MonkeyPatch, tmux: Tmux, settle: Callable[[str, str], str]
) -> None:
    """REMEDY. RED: restore `-S -40` -> wakes on the first poll."""
    import conftest as prompt_conftest

    monkeypatch.setattr(prompt_conftest, "_SETTLE_TIMEOUT_S", 0.5)
    _worker(tmux=tmux)
    _run(
        tmux=tmux,
        command=(
            'printf "%s\\n" "  up/dn to navigate, Enter to select, Esc to cancel"; '
            'for i in $(seq 1 25); do echo "AFTER-$i"; sleep 0.05; done'
        ),
        settle=settle,
        needle="AFTER-25",
        fail_on_timeout=True,
    )
    calls: list[tuple[str, ...]] = []

    def _recording_tmux(*args: str) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return tmux(*args)

    assert watcher_proposed(tmux=_recording_tmux, target="=wk:") != _PICKER
    assert all("-S" not in call for call in calls)


def test_cprime_a_quoted_footer_wakes_the_shipped_watcher(
    *, tmux: Tmux, settle: Callable[[str, str], str]
) -> None:
    """DEFECT (c') PINNED: prose DISCUSSING a picker is not a picker."""
    _worker(tmux=tmux)
    _run(
        tmux=tmux,
        command='echo "BRIEF: never answer via a picker; the footer reads Enter to select"',
        settle=settle,
        needle="BRIEF: never answer",
    )
    assert watcher_shipped(tmux=tmux, target="wk") == _PICKER


def test_cprime_a_quoted_footer_does_not_wake_the_proposed_watcher(
    *, tmux: Tmux, settle: Callable[[str, str], str]
) -> None:
    """REMEDY. RED: drop the END anchor -> wakes on the supervisor's own text."""
    _worker(tmux=tmux)
    _run(
        tmux=tmux,
        command='echo "BRIEF: never answer via a picker; the footer reads Enter to select"',
        settle=settle,
        needle="BRIEF: never answer",
    )
    assert watcher_proposed(tmux=tmux, target="=wk:") != _PICKER


def test_the_shipped_watcher_misses_the_other_real_footer_string(
    *, tmux: Tmux, settle: Callable[[str, str], str]
) -> None:
    """THE TWO-FOOTER GAP, PINNED IN THE OTHER DIRECTION.

    `Enter to confirm` is a REAL footer the agent binary ships (multi-select).
    The shipped test matches one string only, so it misses a whole dialog class
    — a wake that never fires, which is worse than a false one.
    """
    _worker(tmux=tmux)
    _run(
        tmux=tmux,
        command='clear; printf "%s\\n" "  Space to toggle, Enter to confirm, a to select all"',
        settle=settle,
        needle="Space to toggle",
    )
    assert watcher_shipped(tmux=tmux, target="wk") != _PICKER


def test_the_proposed_watcher_catches_the_other_real_footer_string(
    *, tmux: Tmux, settle: Callable[[str, str], str]
) -> None:
    """REMEDY. RED: match one string only -> misses this dialog class."""
    _worker(tmux=tmux)
    _run(
        tmux=tmux,
        command='clear; printf "%s\\n" "  Space to toggle, Enter to confirm, a to select all"',
        settle=settle,
        needle="Space to toggle",
    )
    assert watcher_proposed(tmux=tmux, target="=wk:") == _PICKER


def test_the_control_a_genuine_visible_footer_still_wakes(
    *, tmux: Tmux, settle: Callable[[str, str], str]
) -> None:
    """THE CONTROL, AND IT IS NOT OPTIONAL.

    Every "must not wake" leg above is satisfied by a watcher that never wakes
    at all. This footer carries trailing text, so the ANCHORED half cannot
    match it and only the SHAPE half can — which is why the union is required.
    """
    _worker(tmux=tmux)
    _run(
        tmux=tmux,
        command='printf "%s\\n" "  up/dn to navigate . Enter to select . Esc to cancel"',
        settle=settle,
        needle="to navigate",
    )
    assert watcher_proposed(tmux=tmux, target="=wk:") == _PICKER


def test_d_the_shipped_watcher_reports_idle_for_a_session_that_does_not_exist(
    *, tmux: Tmux, settle: Callable[[str, str], str]
) -> None:
    """DEFECT (d) PINNED, and it composes with the bare-target defect.

    Only `wk-supervisor` is alive. The BARE target prefix-matches it, so the
    watcher inspects the SUPERVISOR's settled pane and calls it IDLE — a
    confident verdict about a worker that does not exist.
    """
    tmux("new-session", "-d", "-s", "wk-supervisor", "-x", "80", "-y", "20")
    # SETTLE the supervisor pane before measuring. Without this the pane is
    # still rendering its first prompt, consecutive captures differ, and the
    # shipped watcher returns BUSY instead of IDLE — which passed locally and
    # FAILED IN CI, where the shell is slower to draw. The defect being pinned
    # is "reports IDLE for a session that does not exist", so the pane must be
    # genuinely settled or the leg is measuring startup noise instead.
    tmux("send-keys", "-t", "=wk-supervisor:", "echo SUPERVISOR_READY", "Enter")
    settle("=wk-supervisor:", "SUPERVISOR_READY")
    assert watcher_shipped(tmux=tmux, target="wk") == _IDLE


def test_d_the_proposed_watcher_reports_target_lost(*, tmux: Tmux) -> None:
    """REMEDY. RED: revert to `prev=""` -> reports IDLE for an absent session."""
    tmux("new-session", "-d", "-s", "wk-supervisor", "-x", "80", "-y", "20")
    assert watcher_proposed(tmux=tmux, target="=wk:") == _LOST


def test_both_forms_report_busy_while_a_pane_keeps_changing(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmux: Tmux,
    settle: Callable[[str, str], str],
    wait_for: Callable[[str, str], None],
) -> None:
    """Neither form may call a WORKING agent idle.

    This is the third verdict and it is the one that keeps `stable` honest: a
    watcher that reached IDLE too eagerly would wake on a busy worker.
    """
    _worker(tmux=tmux)
    _run(tmux=tmux, command="echo READY", settle=settle, needle="READY")
    # A NON-TERMINATING spinner emitting a DISTINCT value each line. Both
    # properties are load-bearing, and the first draft of this leg lacked them:
    # a bounded `seq` loop can FINISH mid-measurement and the pane then settles
    # to IDLE, which is what made this the one flaky leg of the port. And a
    # repeating constant (`yes TICK`) would fill the pane with identical rows,
    # so consecutive captures would compare EQUAL and also report IDLE — busy
    # by CPU, idle by observation. A monotonic counter cannot do either.
    # THREE properties, each one added because its absence produced a flake:
    #   non-terminating — a bounded `seq` loop can FINISH mid-measurement and
    #     the pane then settles to IDLE (flaked ~1-in-3);
    #   distinct values — `yes TICK` fills the pane with identical rows, so
    #     consecutive captures compare EQUAL and also report IDLE: busy by CPU,
    #     idle by observation;
    #   THROTTLED — a full-speed spinner saturates the CPU it shares with the
    #     observer and tmux coalesces renders, so captures repeat and IDLE
    #     wins anyway (flaked ~1-in-5).
    tmux(
        "send-keys",
        "-t",
        "=wk:",
        "i=0; while :; do i=$((i+1)); echo TICK-$i; sleep 0.6; done",
        "Enter",
    )
    # Wait for `TICK-1`, NOT `TICK-`. The pane also renders the ECHOED COMMAND,
    # which literally contains `echo TICK-$i` — so the shorter sentinel matches
    # the command TEXT and returns before the loop has run once, leaving a
    # settled pane and a deterministic IDLE. Measured: `TICK-` failed 5/5,
    # `TICK-1` passes. That is defect (c') wearing a different hat — a detector
    # fooled by text that MENTIONS the thing rather than by the thing — and it
    # bit the sentinel guarding the test for it.
    wait_for("=wk:", "TICK-1")
    _wait_for_change_on_watcher_sleep(monkeypatch=monkeypatch, tmux=tmux, target="=wk:")
    assert watcher_proposed(tmux=tmux, target="=wk:") == _BUSY
    assert watcher_shipped(tmux=tmux, target="wk") == _BUSY


def test_both_forms_report_idle_while_a_pane_stays_static(
    *, tmux: Tmux, settle: Callable[[str, str], str]
) -> None:
    """CONTROL: the busy leg must still discriminate from a static pane."""
    _worker(tmux=tmux)
    _run(tmux=tmux, command="echo STATIC", settle=settle, needle="STATIC")
    assert watcher_proposed(tmux=tmux, target="=wk:") == _IDLE
    assert watcher_shipped(tmux=tmux, target="wk") == _IDLE


def test_s4_shipped_condition_watcher_omits_the_terminal_success_state() -> None:
    """DEFECT PINNED: a merged PR returns mergeStateStatus=UNKNOWN.

    The shipped watcher switched only on mergeStateStatus, so it missed the
    authoritative terminal success state and reported the opposite of truth.
    """
    pr = {"state": "MERGED", "mergeStateStatus": "UNKNOWN"}
    assert pr_condition_watcher_shipped(pr=pr) != "WAKE: PR state=MERGED"


def test_s4_condition_watcher_wakes_on_terminal_success_first() -> None:
    """REMEDY. RED: restore the derived-field-only predicate -> no MERGED wake."""
    pr = {"state": "MERGED", "mergeStateStatus": "UNKNOWN"}
    assert pr_condition_watcher_proposed(pr=pr) == "WAKE: PR state=MERGED"


def test_s4_condition_watcher_fails_open_on_unrecognized_values() -> None:
    """A total fallback wakes for inspection instead of waiting silently."""
    pr = {"state": "OPEN", "mergeStateStatus": "REVIEW_REQUIRED"}
    assert pr_condition_watcher_proposed(pr=pr) == (
        "WAKE: unrecognized mergeStateStatus=REVIEW_REQUIRED"
    )


def test_s4_shipped_condition_watcher_keeps_known_derived_states_pending() -> None:
    pr = {"state": "OPEN", "mergeStateStatus": "DIRTY"}
    assert pr_condition_watcher_shipped(pr=pr) == _PENDING


def test_s4_condition_watcher_wakes_on_terminal_closed_first() -> None:
    pr = {"state": "CLOSED", "mergeStateStatus": "UNKNOWN"}
    assert pr_condition_watcher_proposed(pr=pr) == "WAKE: PR state=CLOSED"


def test_s4_condition_watcher_wakes_on_unknown_authoritative_state() -> None:
    pr = {"state": "ARCHIVED", "mergeStateStatus": "CLEAN"}
    assert pr_condition_watcher_proposed(pr=pr) == "WAKE: unrecognized PR state=ARCHIVED"


def test_s4_condition_watcher_wakes_on_clean_derived_state() -> None:
    pr = {"state": "OPEN", "mergeStateStatus": "CLEAN"}
    assert pr_condition_watcher_proposed(pr=pr) == "WAKE: PR mergeable state=CLEAN"


def test_s4_condition_watcher_keeps_known_blocking_derived_states_pending() -> None:
    pr = {"state": "OPEN", "mergeStateStatus": "CONFLICTING"}
    assert pr_condition_watcher_proposed(pr=pr) == _PENDING
