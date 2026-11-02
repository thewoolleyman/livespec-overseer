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

from overseer.tmuxio import new_session_args

__all__: list[str] = []

_PICKER, _IDLE, _LOST, _BUSY = "PICKER", "IDLE", "LOST", "BUSY"
_PENDING = "PENDING"
_POLLS = 4
_STABLE_TO_IDLE = 3
_VISIBLE_TAIL = 8
_PANE_RENDER_GUARD_S = 60.0

# END-anchored: a wrapped continuation line can BEGIN with "Enter to select"
# (measured — the echoed command wrapped at that exact column), so anchoring
# only the start re-introduces the (c') false positive.
_ANCHORED = re.compile(r"^[ \t]*Enter to (select|confirm)[ \t]*$", re.MULTILINE)
# The footer SHAPE: two "<key> to <verb>" clauses joined by a separator. This
# is the half that catches a REAL footer carrying trailing text, which the
# anchored half cannot match.
_SHAPE = re.compile(r"[^ ]+ to [a-z]+([,]| [^ a-zA-Z0-9]+) +[^ ]+ to [a-z]+")
_SCROLLBACK_WITH_FOOTER = "\n".join(
    [
        "  up/dn to navigate, Enter to select, Esc to cancel",
        *(f"AFTER-{i}" for i in range(1, 26)),
    ]
)
_VISIBLE_AFTER_FOOTER = "\n".join(f"AFTER-{i}" for i in range(18, 26))
_SHIPPED_SCROLLBACK_CAPTURE = ("capture-pane", "-p", "-t", "wk", "-S", "-40")
_PROPOSED_VISIBLE_CAPTURE = ("capture-pane", "-p", "-t", "=wk:")

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
    tmux(*new_session_args(args=["-d", "-s", "wk", "-x", "80", "-y", rows]))
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


def _scrollback_tmux_double(
    *, calls: list[tuple[str, ...]] | None = None
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Return scrollback only when the watcher asks tmux for scrollback."""

    def _tmux(*args: str) -> subprocess.CompletedProcess[str]:
        if calls is not None:
            calls.append(args)
        if args == _SHIPPED_SCROLLBACK_CAPTURE:
            pane = _SCROLLBACK_WITH_FOOTER
        elif args == _PROPOSED_VISIBLE_CAPTURE:
            pane = _VISIBLE_AFTER_FOOTER
        else:
            raise AssertionError(f"unexpected tmux call: {args!r}")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=pane, stderr="")

    return _tmux


def test_scrollback_tmux_double_rejects_unexpected_capture_contract() -> None:
    tmux = _scrollback_tmux_double()

    assert tmux(*_PROPOSED_VISIBLE_CAPTURE).stdout == _VISIBLE_AFTER_FOOTER
    with pytest.raises(AssertionError, match="unexpected tmux call"):
        tmux("capture-pane", "-p", "-t", "wk")


def _advance_pane_on_watcher_sleep(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmux: Tmux,
    target: str,
) -> list[str]:
    """Make every watcher sleep DRIVE one pane change and wait until it renders.

    The pane runs `cat`, so a line the test types is echoed and then printed
    back. Each sleep sends the next distinct `TICK-<n>` and returns only once
    the pane shows `cat`'s copy of it, so consecutive watcher captures differ
    by construction. No background spinner has to win a race against the
    watcher's cadence, which is what a loaded host broke (overseer-em5b): the
    0.6s-throttled spinner did not render inside the observation window.
    The deadline is a rig-failure guard on an EVENT wait, never a sleep the
    verdict depends on. Returns the ticks sent, so the leg can prove the
    watcher actually slept between captures.
    """
    real_sleep = time.sleep
    sent: list[str] = []

    def _sleep_after_advancing(_seconds: float) -> None:
        tick = f"TICK-{len(sent) + 1}"
        sent.append(tick)
        tmux("send-keys", "-t", target, tick, "Enter")
        deadline = time.monotonic() + _PANE_RENDER_GUARD_S
        while time.monotonic() < deadline:
            # `cat` prints the line back after the tty echo, so the tick
            # appears TWICE once the pane has caught up with the keystroke.
            if tmux("capture-pane", "-p", "-t", target).stdout.count(tick) >= 2:
                return
            real_sleep(0.02)
        # COVERAGE-EXEMPT: reached only if tmux stops rendering typed input
        # for the whole guard. This makes a rig failure loud instead of
        # letting the watcher compare two identical captures.
        pytest.fail(
            f"pane never rendered {tick} within {_PANE_RENDER_GUARD_S}s"
        )  # pragma: no cover

    monkeypatch.setattr(time, "sleep", _sleep_after_advancing)
    return sent


def test_settle_can_fail_loudly_on_expiry(
    *, monkeypatch: pytest.MonkeyPatch, settle: Settle
) -> None:
    import conftest as prompt_conftest

    monkeypatch.setattr(prompt_conftest, "_SETTLE_TIMEOUT_S", 0.0)

    with pytest.raises(pytest.fail.Exception) as exc_info:
        settle("=wk:", "NEVER-APPEARS", fail_on_timeout=True)

    assert "tmux pane did not settle before the timeout" in str(exc_info.value)


def test_settle_waits_through_echo_only_before_payload_output(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    import conftest as prompt_conftest

    echoed_command = "for i in $(seq 1 25); do echo AFTER-$i; done"
    captures = [
        echoed_command,
        echoed_command,
        echoed_command,
        echoed_command,
        f"{echoed_command}\nAFTER-25",
        f"{echoed_command}\nAFTER-25",
    ]

    def _tmux(*args: str) -> subprocess.CompletedProcess[str]:
        pane = captures.pop(0) if captures else f"{echoed_command}\nAFTER-25"
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=pane, stderr="")

    monkeypatch.setattr(prompt_conftest, "_SETTLE_TIMEOUT_S", 0.2)
    monkeypatch.setattr(prompt_conftest, "_SETTLE_COMMAND_START_TIMEOUT_S", 1.0)
    monkeypatch.setattr(prompt_conftest, "_SETTLE_ABSOLUTE_TIMEOUT_S", 2.0)

    settled = prompt_conftest.make_settle(tmux=_tmux)(
        "=wk:",
        "AFTER-25",
        fail_on_timeout=True,
    )

    assert settled.endswith("AFTER-25")


def test_settle_fails_loudly_when_payload_never_starts_after_echo(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    import conftest as prompt_conftest

    now = 0.0
    echoed_command = "for i in $(seq 1 25); do echo AFTER-$i; done"

    def _monotonic() -> float:
        return now

    def _sleep(seconds: float) -> None:
        nonlocal now
        now += seconds

    def _tmux(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=echoed_command,
            stderr="",
        )

    monkeypatch.setattr(prompt_conftest.time, "monotonic", _monotonic)
    monkeypatch.setattr(prompt_conftest.time, "sleep", _sleep)
    monkeypatch.setattr(prompt_conftest, "_SETTLE_TIMEOUT_S", 0.05)
    monkeypatch.setattr(prompt_conftest, "_SETTLE_COMMAND_START_TIMEOUT_S", 0.2)
    monkeypatch.setattr(prompt_conftest, "_SETTLE_ABSOLUTE_TIMEOUT_S", 1.0)

    with pytest.raises(pytest.fail.Exception) as exc_info:
        prompt_conftest.make_settle(tmux=_tmux)(
            "=wk:",
            "AFTER-25",
            fail_on_timeout=True,
        )

    assert "tmux pane did not settle before the timeout" in str(exc_info.value)


def test_settle_fails_loudly_when_a_pane_changes_forever_without_the_needle(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    import conftest as prompt_conftest

    now = 0.0
    calls = 0

    def _monotonic() -> float:
        return now

    def _sleep(seconds: float) -> None:
        nonlocal now
        now += seconds

    def _tmux(*args: str) -> subprocess.CompletedProcess[str]:
        nonlocal calls, now
        calls += 1
        now += 0.03
        if calls > 20:
            raise AssertionError(  # pragma: no cover
                "settle kept polling after the absolute deadline"
            )
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=f"still-changing-{calls}",
            stderr="",
        )

    monkeypatch.setattr(prompt_conftest.time, "monotonic", _monotonic)
    monkeypatch.setattr(prompt_conftest.time, "sleep", _sleep)
    monkeypatch.setattr(prompt_conftest, "_SETTLE_TIMEOUT_S", 0.05)
    monkeypatch.setattr(prompt_conftest, "_SETTLE_COMMAND_START_TIMEOUT_S", 0.5)
    monkeypatch.setattr(prompt_conftest, "_SETTLE_ABSOLUTE_TIMEOUT_S", 0.2)

    with pytest.raises(pytest.fail.Exception) as exc_info:
        prompt_conftest.make_settle(tmux=_tmux)(
            "=wk:",
            "NEVER-APPEARS",
            fail_on_timeout=True,
        )

    assert "tmux pane did not settle before the timeout" in str(exc_info.value)
    assert calls < 20


def test_c_a_footer_in_scrollback_wakes_the_shipped_watcher() -> None:
    """DEFECT (c) PINNED: the footer has SCROLLED OFF and it still wakes."""
    calls: list[tuple[str, ...]] = []
    tmux = _scrollback_tmux_double(calls=calls)

    assert watcher_shipped(tmux=tmux, target="wk") == _PICKER
    assert calls == [_SHIPPED_SCROLLBACK_CAPTURE]


def test_c_a_footer_in_scrollback_does_not_wake_the_proposed_watcher() -> None:
    """REMEDY. RED: restore `-S -40` -> wakes on the first poll."""
    calls: list[tuple[str, ...]] = []
    tmux = _scrollback_tmux_double(calls=calls)

    assert watcher_proposed(tmux=tmux, target="=wk:") != _PICKER
    assert calls == [_PROPOSED_VISIBLE_CAPTURE] * _POLLS


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
    *, tmux: Tmux, settle: Settle
) -> None:
    """DEFECT (d) PINNED, and it composes with the bare-target defect.

    Only `wk-supervisor` is alive. The BARE target prefix-matches it, so the
    watcher inspects the SUPERVISOR's settled pane and calls it IDLE — a
    confident verdict about a worker that does not exist.
    """
    # The supervisor pane prints once and then runs `sleep`, so NOTHING in it
    # can redraw: no shell prompt, no line editor, no startup output racing the
    # watcher. The earlier form ran an interactive shell and settled it with a
    # needle; under host load that settle could expire silently while the
    # prompt was still drawing, consecutive captures differed, and the shipped
    # watcher returned BUSY (failed in CI on 2026-11-02, blocking PR #2771).
    # The defect being pinned is "reports IDLE for a session that does not
    # exist", so the pane must be static by construction, not by luck.
    created = tmux(
        *new_session_args(
            args=[
                "-d",
                "-s",
                "wk-supervisor",
                "-x",
                "80",
                "-y",
                "20",
                "printf '%s\\n' SUPERVISOR_READY; exec sleep 600",
            ]
        )
    )
    assert created.returncode == 0, created.stderr
    settle("=wk-supervisor:", "SUPERVISOR_READY", fail_on_timeout=True)
    assert watcher_shipped(tmux=tmux, target="wk") == _IDLE


def test_d_the_proposed_watcher_reports_target_lost(*, tmux: Tmux) -> None:
    """REMEDY. RED: revert to `prev=""` -> reports IDLE for an absent session."""
    tmux(*new_session_args(args=["-d", "-s", "wk-supervisor", "-x", "80", "-y", "20"]))
    assert watcher_proposed(tmux=tmux, target="=wk:") == _LOST


def test_both_forms_report_busy_while_a_pane_keeps_changing(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmux: Tmux,
    settle: Settle,
) -> None:
    """Neither form may call a WORKING agent idle.

    This is the third verdict and it is the one that keeps `stable` honest: a
    watcher that reached IDLE too eagerly would wake on a busy worker.

    The change between captures is DRIVEN by the test, not raced against it.
    Four earlier forms used a background spinner, and each flaked for a timing
    reason: a bounded loop finished mid-measurement, a constant line compared
    equal, an unthrottled spinner made tmux coalesce renders, and the throttled
    spinner missed the observation window at host load 50-60 (overseer-em5b).
    Here every watcher sleep types the next tick into `cat` and waits until it
    has rendered, so the pane changes between every pair of captures whatever
    the host's load. A watcher that calls this pane idle is wrong by
    construction, which is the claim the leg exists to make.
    """
    created = tmux(*new_session_args(args=["-d", "-s", "wk", "-x", "80", "-y", "20", "exec cat"]))
    assert created.returncode == 0, created.stderr
    tmux("send-keys", "-t", "=wk:", "CAT-READY", "Enter")
    settle("=wk:", "CAT-READY", fail_on_timeout=True)
    ticks = _advance_pane_on_watcher_sleep(monkeypatch=monkeypatch, tmux=tmux, target="=wk:")
    assert watcher_proposed(tmux=tmux, target="=wk:") == _BUSY
    assert watcher_shipped(tmux=tmux, target="wk") == _BUSY
    # Each watcher sleeps between its polls, so both together drove the pane
    # through 2 * (_POLLS - 1) distinct ticks or more; fewer would mean a
    # watcher returned before observing any change at all.
    assert len(ticks) >= 2 * (_POLLS - 1)


def test_both_forms_report_idle_while_a_pane_stays_static(*, tmux: Tmux, settle: Settle) -> None:
    """CONTROL: the busy leg must still discriminate from a static pane."""
    created = tmux(
        *new_session_args(
            args=[
                "-d",
                "-s",
                "wk",
                "-x",
                "80",
                "-y",
                "20",
                "printf '%s\\n' STATIC; exec sleep 600",
            ]
        )
    )
    assert created.returncode == 0, created.stderr
    settle("=wk:", "STATIC", fail_on_timeout=True)
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
