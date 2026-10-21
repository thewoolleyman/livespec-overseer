"""The widened gate region is entered on a picker's own STRUCTURE, not on any `N.` line.

`overseer-xe2mka`, review finding R1. Widening the gate tail upward is what lets a tall
picker read as a live gate, but keying the widening on "the tail holds a numbered line"
re-opens the `overseer-i6eu2k` quotation false positive wherever
:func:`signals._input_box_present` cannot hold it out — on Codex, which renders no `❯`
box AT ALL, and on any Claude pane whose picker displaces that box. An ordinary agent
turn routinely prints an indented numbered plan, and an indented block does not supply
the flush-left line an upward walk stops at, so a QUOTED cursor far above the bottom was
dragged into the region.

So the widening is anchored on the picker's own footer — the key-hint line it renders
directly below its option block (`Enter to select · ↑/↓ to navigate · Esc to cancel`,
measured 2026-10-14 on the pane this item was filed for). A numbered plan carries no
such footer; a live picker always does.
"""

import signals
from test_picker_tail_gate_detection import live_picker_capture, quoted_picker_capture
from test_supervisor_builders import idle_capture

__all__: list[str] = []

_FOOTER = "  Enter to select · ↑/↓ to navigate · Esc to cancel"
_STATUSLINE = "  gpt-5.5 high · /x/repo · Context 60% left · topic"


def codex_quoted_plan_capture(*, footer: str = "") -> str:
    """A Codex-shaped pane quoting a picker cursor above its own indented plan.

    Codex renders no `❯` input box, so `_input_box_present` is False BY CONSTRUCTION
    and `is_structured_gate` has no second guard here. The quoted `❯ 1.` sits TEN
    non-empty lines above the bottom — outside the fixed eight-line tail, so a narrow
    read never saw it — and every line between it and the bottom is indented or
    numbered, so an upward walk reaches it unless something anchors the entry.
    """
    lines = [
        "I read the peer pane and it quoted this picker at me:",
        "  ❯ 1. Continue with the recorded next action",
        "  Here is the plan I am following instead:",
        "  1. Re-read the ledger-held plan state",
        "     and reconcile it against the worktree",
        "  2. Land the accepted review fix",
        "     against the delivered module",
        "  3. Re-run the full aggregate",
        "  4. Open the pull request",
        "  5. Report the outcome",
        *([footer] if footer else []),
        "  Working on step 1 now",
        _STATUSLINE,
    ]
    return "\n".join(lines) + "\n"


def test_an_indented_numbered_plan_never_drags_a_quoted_cursor_into_the_region() -> None:
    """The finding, as measured: no picker footer, so no widening, so no gate."""
    capture = codex_quoted_plan_capture()
    lines = [line for line in capture.splitlines() if line.strip()]
    cursor = next(index for index, line in enumerate(lines) if "❯ 1." in line)

    assert len(lines) - 1 - cursor == 10
    assert signals.is_structured_gate(capture_text=capture) is False


def test_prose_naming_enter_once_is_not_a_picker_footer() -> None:
    """A footer joins at least two `<key> to <verb>` clauses; a sentence names one.

    The same capture, with the quoted picker introduced in prose that mentions Enter.
    One clause is a mention, not the key-hint line a picker renders.
    """
    capture = codex_quoted_plan_capture(footer="  I would have to press Enter to select")

    assert signals.is_structured_gate(capture_text=capture) is False


def test_a_bare_enter_to_select_footer_still_anchors_the_widening() -> None:
    """The other measured footer shape: the hint line carries nothing but the key.

    Pinned because the clause-count half cannot match it, so dropping the anchored half
    would lose a whole dialog class — a MISSED gate, which is the dangerous direction.
    """
    capture = tall_picker_capture(footer="  Enter to select")

    assert signals.is_structured_gate(capture_text=capture) is True


def tall_picker_capture(*, footer: str = _FOOTER, rules: bool = False) -> str:
    """A picker whose cursor sits outside the eight-line tail, with optional rules.

    `rules` renders the two horizontal rules the measured pane carried between its
    option block and its footer. They are flush-left, so they are exactly the lines an
    upward walk would stop at if it admitted only options and indented continuations —
    and the real pane puts them between the footer and the cursor the walk is for.
    """
    rule = "─" * 40
    lines = [
        "How should this session proceed?",
        "❯ 1. Continue steps 1-4 (Recommended)",
        "     Finish the remaining work as planned",
        "  2. Stop here and hand off",
        "     Leave the rest for the next session",
        "  3. Ask the maintainer first",
        "     Escalate before touching anything",
        "  4. Re-plan the whole batch",
        "     Throw the current ordering away",
        "  5. Abort the pass",
        "     Discard the work in flight",
        *([rule, rule] if rules else []),
        footer,
        "  Opus 4.8 (1M context) | /x/repo | Ctx: 80% left",
    ]
    return "\n".join(lines) + "\n"


def test_the_measured_rules_between_the_options_and_the_footer_are_crossed() -> None:
    """The faithful shape of the pane `overseer-xe2mka` was filed for."""
    assert signals.is_structured_gate(capture_text=tall_picker_capture(rules=True)) is True


def test_a_picker_whose_question_scrolled_off_the_top_is_still_a_gate() -> None:
    """The walk runs out of pane rather than out of block, and must stop there."""
    capture = tall_picker_capture()
    headless = capture.split("\n", 1)[1]

    assert headless.startswith("❯ 1.")
    assert signals.is_structured_gate(capture_text=headless) is True


def test_the_quotation_and_short_picker_controls_are_unchanged() -> None:
    """`overseer-i6eu2k`'s control, and a short live picker under long scrollback."""
    scrollback = "\n".join(f"● earlier turn {index}" for index in range(1, 10))

    assert signals.is_structured_gate(capture_text=quoted_picker_capture()) is False
    assert signals.is_structured_gate(capture_text=idle_capture(ctx=80)) is False
    assert signals.is_structured_gate(capture_text=live_picker_capture()) is True
    assert signals.is_structured_gate(capture_text=f"{scrollback}\n{live_picker_capture()}") is True
