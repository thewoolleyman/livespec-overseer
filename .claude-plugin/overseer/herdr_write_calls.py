"""herdr_write_calls.py — the herdr WRITE operations' params and replies. PURE, no I/O.

The write-side twin of :mod:`herdr_calls`, and split from it for the same reason
that module is split from :mod:`herdr_adapter`: this layer knows what each
MUTATION asks for and what its answer means, and nothing else. It opens no
socket and makes no claim that anything it shaped was actually delivered.

Keeping it pure is what lets the wire shape below be asserted without a herdr
server at all, which matters because this repository's CI container does not
ship herdr — the deterministic suite is the only thing covering this code on
that lane.

**The paste's wire shape is part of the CONTRACT, not an implementation detail.**
Measured on this host against herdr 0.9.3 / protocol 22, three delivery forms
exist and only one of them is usable:

  - `pane.send_input` with `keys: []` delivered `\\x1b[200~ONE\\nTWO\\x1b[201~` to
    a raw-mode child — ONE bracketed paste carrying NO carriage return. The
    payload is DELIVERED but NOT EXECUTED, which is precisely what the daemon's
    paste-then-observe-then-submit protocol requires.
  - `pane.send_input` with `text: ""` and `keys: ["Enter"]` appended exactly
    `\\r`, so submission is separable from delivery.
  - `pane.send_text` delivered the same characters with NO bracketing at all.

That last one is the trap, and it is why :func:`paste_params` exists rather than
callers shaping a dict inline. A `send_text` paste looks correct in a screen
capture while letting a multi-line payload fragment into separate submitted
prompts — the exact failure the tmux backend's atomic-paste discipline
(`load-buffer` + `paste-buffer -p`) was adopted to prevent. `keys` is sent as an
EMPTY list rather than omitted because the measured request carries it
explicitly; herdr validates keys before sending, so an empty list is the
statement that no key accompanies this text.
"""

from __future__ import annotations

from dataclasses import dataclass

import herdr_calls
import herdr_protocol
import jsonio

__all__: list[str] = [
    "ENTER_KEY",
    "EXPECT_LAYOUT",
    "EXPECT_OK",
    "EXPECT_PANE_INFO",
    "EXPECT_PANE_SWAP",
    "LAYOUT_METHOD",
    "PASTE_METHOD",
    "RESULT_TYPE_OK",
    "RESULT_TYPE_PANE_INFO",
    "RESULT_TYPE_PANE_LAYOUT",
    "RESULT_TYPE_PANE_SWAP",
    "SPLIT_DIRECTION_DOWN",
    "SPLIT_METHOD",
    "SWAP_METHOD",
    "RetainedShell",
    "created_pane_refusal",
    "enter_params",
    "launch_params",
    "layout_params",
    "new_pane_id",
    "pane_tops",
    "paste_params",
    "retained_shell",
    "split_down_params",
    "swap_params",
    "swap_refusal",
]

# MEASURED: the one method that brackets a paste. `pane.send_text` is NOT an
# alternative spelling of this — see the module docstring.
PASTE_METHOD = herdr_protocol.METHOD_PANE_SEND_INPUT
# MEASURED: the key name herdr accepts for a submit, and the result discriminator
# both write calls answer with.
ENTER_KEY = "Enter"
RESULT_TYPE_OK = "ok"

# MEASURED: the two layout mutations, the read that verifies them, their one
# usable direction, and the discriminators their replies carry.
SPLIT_METHOD = "pane.split"
SWAP_METHOD = "pane.swap"
LAYOUT_METHOD = "pane.layout"
SPLIT_DIRECTION_DOWN = "down"
RESULT_TYPE_PANE_INFO = "pane_info"
RESULT_TYPE_PANE_SWAP = "pane_swap"
RESULT_TYPE_PANE_LAYOUT = "pane_layout"

# A write answers `{"type": "ok"}` and carries no payload members, so there is
# nothing to require beyond the discriminator itself.
EXPECT_OK = herdr_protocol.ReplyExpectation(result_type=RESULT_TYPE_OK)
EXPECT_PANE_INFO = herdr_protocol.ReplyExpectation(
    result_type=RESULT_TYPE_PANE_INFO, required_fields=("pane",)
)
EXPECT_PANE_SWAP = herdr_protocol.ReplyExpectation(
    result_type=RESULT_TYPE_PANE_SWAP, required_fields=("swap",)
)
EXPECT_LAYOUT = herdr_protocol.ReplyExpectation(
    result_type=RESULT_TYPE_PANE_LAYOUT, required_fields=("layout",)
)


def layout_params(*, pane_id: str) -> dict[str, object]:
    """Read the tab layout that `pane_id` belongs to."""
    return {"pane_id": pane_id}


def pane_tops(*, result: dict[str, object]) -> dict[str, int] | None:
    """Each pane's TOP row on the tab, or `None` when the layout is unreadable.

    Only the vertical offset is kept, because the one question this answers is
    whether one pane sits above another. Fail-closed like every reader here: a
    layout that cannot be parsed, or a pane row without a usable id and `y`,
    yields no geometry rather than a partial picture something could be
    launched against.
    """
    layout = jsonio.as_object(value=result.get("layout"))
    if layout is None:
        return None
    rows = jsonio.as_list(value=layout.get("panes"))
    if rows is None:
        return None
    tops: dict[str, int] = {}
    for row in rows:
        pane = jsonio.as_object(value=row)
        if pane is None:
            return None
        identifier = pane.get("pane_id")
        rect = jsonio.as_object(value=pane.get("rect"))
        if not isinstance(identifier, str) or not identifier or rect is None:
            return None
        top = rect.get("y")
        if not isinstance(top, int) or isinstance(top, bool):
            return None
        tops[identifier] = top
    return tops


def created_pane_refusal(*, created: str, original: str, known: frozenset[str]) -> str:
    """Why `created` may not be treated as this operation's new pane, or `""`.

    **A split acknowledgement is a CLAIM, not evidence.** It proves the server
    named some pane; it cannot prove that pane is new or that it is not the one
    being supervised. Both failures were reproduced: an acknowledgement naming
    the ORIGINAL pane led to a self-swap and a daemon command pasted into the
    live agent, and the same shape naming any pre-existing neighbour would move
    somebody else's session instead.

    The original check is kept separate from the pre-existing check even though
    the original is always in `known`, because the two are different accidents
    and an operator reading the refusal should be told which one happened.
    """
    if created == original:
        return (
            "herdr split reply names the ORIGINAL pane "
            f"{original!r} as the pane it created; refusing before any write"
        )
    if created in known:
        return f"herdr split reply names pre-existing pane {created!r} as newly created"
    return ""


@dataclass(frozen=True, kw_only=True)
class RetainedShell:
    """A pane's idle retained shell, or why it may not be written into.

    `shell_pid` is 0 on a refusal rather than left as a plausible value, for the
    same reason every reader here fails closed: a caller that carried a pid out
    of a refused reading could use it as the EXPECTED shell on a later check and
    certify the comparison against itself.
    """

    shell_pid: int
    error: str


def retained_shell(
    *, result: dict[str, object], pane_id: str, expected_shell_pid: int | None
) -> RetainedShell:
    """The pane's live idle retained shell, or why it does not authorize a write.

    **An executable NAME is not shell identity.** Anything can be called `bash`,
    so the judgement is made entirely on pids: `shell_pid` is the identity, and
    its relationship to `foreground_process_group_id` is the state. Measured on
    herdr 0.9.3, a pane at its prompt reports the two EQUAL with the shell itself
    as the listed group leader (`shell_pid 22420` / group `22420`, leader
    `bash`), and the same pane running a child reports them DIFFERENT (`22420` /
    group `22447`, leader `sleep`). Equality is therefore the idle reading, and
    anything else is a pane whose foreground belongs to something that would
    receive the command instead of the shell.

    `expected_shell_pid` carries the two uses apart with one function rather than
    two that could drift. `None` ESTABLISHES the expectation from this reading;
    a pid REQUIRES it, which is the only way a shell replaced between the
    establish and the recheck is detectable at all — a replaced shell is idle,
    in the right pane, and reports perfectly well about a process the command was
    never meant for.

    Fail-closed on every other shape too, by delegating the parse to
    :func:`herdr_calls.foreground_process`: a payload that cannot be read, a
    non-positive pid, and a foreground list whose group leader cannot be
    selected unambiguously all arrive here as `None` and refuse. The pane echo is
    checked for the same reason the observation adapter checks it — a matching
    request id proves the reply answers THIS REQUEST, not that it describes THIS
    PANE.
    """
    process = herdr_calls.foreground_process(result=result)
    if process is None:
        return RetainedShell(
            shell_pid=0,
            error=f"herdr process reading for {pane_id!r} is unreadable or ambiguous",
        )
    if process.pane_id != pane_id:
        return RetainedShell(
            shell_pid=0,
            error=(
                f"herdr process reading describes pane {process.pane_id!r}, "
                f"not the created {pane_id!r}"
            ),
        )
    if expected_shell_pid is not None and process.shell_pid != expected_shell_pid:
        return RetainedShell(
            shell_pid=0,
            error=(
                f"herdr reports shell {process.shell_pid} in {pane_id!r}, not the "
                f"expected {expected_shell_pid}; the retained shell was replaced"
            ),
        )
    if process.process_group_id != process.shell_pid:
        return RetainedShell(
            shell_pid=0,
            error=(
                f"{pane_id!r} is OCCUPIED: foreground group {process.process_group_id} "
                f"is not its retained shell {process.shell_pid}"
            ),
        )
    return RetainedShell(shell_pid=process.shell_pid, error="")


def paste_params(*, pane_id: str, text: str) -> dict[str, object]:
    """Deliver `text` to `pane_id` as ONE bracketed paste, submitting nothing."""
    return {"pane_id": pane_id, "text": text, "keys": []}


def enter_params(*, pane_id: str) -> dict[str, object]:
    """Submit whatever `pane_id` currently holds, delivering no new text."""
    return {"pane_id": pane_id, "text": "", "keys": [ENTER_KEY]}


def launch_params(*, pane_id: str, command: str) -> dict[str, object]:
    """Run `command` in `pane_id`'s own shell, as one atomic text-plus-submit.

    The ATOMIC form is correct here and wrong for a paste, which is why the two
    are separate functions rather than one with a flag. Launching a known shell
    command has no observe step to preserve — there is nothing to inspect
    between delivery and execution — whereas a payload pasted into a supervised
    agent must be seen before it runs. Measured: this leaves the pane's own
    shell RUNNING with the command as its foreground process, where an `exec`
    launch would discard that shell and a pane whose process exits is closed.
    """
    return {"pane_id": pane_id, "text": command, "keys": [ENTER_KEY]}


def split_down_params(*, pane_id: str, cwd: str, ratio: float) -> dict[str, object]:
    """Split `pane_id` DOWNWARD, giving the original `ratio` of the column.

    Down is not a preference: herdr supports only `right` and `down` (measured),
    so placing a pane ABOVE another is necessarily this split followed by
    :func:`swap_params`. `ratio` is the ORIGINAL pane's share, so after that
    swap the NEW pane holds it — which is what lets a caller ask for a
    percentage and get it at any terminal size.

    `focus` is false because the supervised pane must keep it; the swap below
    preserves whatever focus this call leaves in place.

    **The key is `target_pane_id`, and sending `pane_id` here is a SILENT
    wrong-pane split.** `pane.split` does not alias the two, and herdr 0.9.3
    tolerates unknown members rather than rejecting them, so a `pane_id` is
    simply dropped and the call falls back to its default of splitting the
    FOCUSED pane — under an ordinary successful `pane_info` reply. Measured
    with `w1:p1` targeted and `w1:p2` focused: `w1:p1` stayed `(0,0,60,40)`
    while `w1:p2` was split `(60,0,60,40)` → `(60,0,60,10)`. Note that this is
    the opposite of :func:`paste_params` and :func:`launch_params`, which take
    `pane_id` and DO honour an unfocused pane exactly (also measured); the
    inconsistency is herdr's, not a mistake here.
    """
    return {
        "target_pane_id": pane_id,
        "direction": SPLIT_DIRECTION_DOWN,
        "ratio": ratio,
        "cwd": cwd,
        "focus": False,
    }


def swap_params(*, source_pane_id: str, target_pane_id: str) -> dict[str, object]:
    """Exchange two panes' POSITIONS, keeping both identities and both shells.

    Measured: pane ids, shell pids and the focused pane are all unchanged by
    this; only the rectangles trade places.
    """
    return {"source_pane_id": source_pane_id, "target_pane_id": target_pane_id}


def swap_refusal(*, result: dict[str, object], source_pane_id: str, target_pane_id: str) -> str:
    """Why this swap may NOT be believed, or `""` when it may.

    **A refused swap arrives as a SUCCESS envelope**, which is why this exists
    rather than a `ReplyExpectation`. Measured on herdr 0.9.3: a cross-tab swap
    answers `{"changed": false, "reason": "cross_tab", ...}` and a same-pane
    swap answers `{"changed": false, "reason": "same_pane", ...}`, both under
    `result` with the declared type and members all present. The expectation
    gate therefore passes them, and a caller that trusted it would go on to
    launch a command into a pane that was never moved.

    The echoed identities are checked for the same reason the observation
    adapter checks a reply's pane id: matching the reply's REQUEST id proves
    the answer is to this call, not that it concerns the panes this call named.
    """
    swap = jsonio.as_object(value=result.get("swap"))
    if swap is None:
        return "herdr swap reply carries no readable swap"
    if swap.get("changed") is not True:
        reason = swap.get("reason")
        detail = f" ({reason})" if isinstance(reason, str) and reason else ""
        return f"herdr refused the swap{detail}"
    echoed_source = swap.get("source_pane_id")
    echoed_target = swap.get("target_pane_id")
    if echoed_source != source_pane_id or echoed_target != target_pane_id:
        return (
            f"herdr swap reply describes {echoed_source!r}/{echoed_target!r}, "
            f"not the requested {source_pane_id!r}/{target_pane_id!r}"
        )
    return ""


def new_pane_id(*, result: dict[str, object]) -> str | None:
    """The pane id a split reports creating, or `None` when it is unreadable.

    Fail-closed in the same sense as every reader in :mod:`herdr_calls`: a split
    whose new pane cannot be named has not given the caller anything to act on,
    and an empty string is not a usable pane id. Returning `None` keeps the
    caller from addressing a later swap or launch at nothing.
    """
    pane = jsonio.as_object(value=result.get("pane"))
    if pane is None:
        return None
    identifier = pane.get("pane_id")
    if not isinstance(identifier, str) or not identifier:
        return None
    return identifier
