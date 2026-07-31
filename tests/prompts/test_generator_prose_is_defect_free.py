"""The GENERATOR's own prose must carry none of the known defect classes.

`test_charters_carry_no_known_defects.py` scans charters that have already been
EMITTED. This scans the file they are emitted FROM. Those are different surfaces
and only one of them was covered.

WHY THIS IS THE MISSING RUNG, in this thread's own terms. The charter gate's
scope has been widened once before, and the widening immediately paid: the
two-layer split moved the role contract into `.ai/supervisor-protocol.md`, the
glob was never widened to follow it, and the gate "went on reporting a clean
repo while the larger half of what a supervisor actually reads was never
examined" -- it carried the (h) defect when it was finally looked at. That
module's own conclusion is the rule this one applies: **a gate's SCOPE is as
load-bearing as its detectors; widening the detectors while the glob stays
behind buys nothing.** The generator prose is the last unscanned surface, and it
is the most upstream one.

WHAT IT BUYS THAT THE CHARTER GATE CANNOT. A defect reintroduced into the
generator template ships to every adopter and is caught HERE only after somebody
regenerates a charter in this repo and commits it -- and this thread's central
finding is that **nothing schedules regeneration**. So a generator regression
could sit behind a green board for as long as no charter happens to be
regenerated. Two other modules read this same prose and neither would see it:
`test_generated_supervisor_handoff_contract.py` checks CONTRACT REQUIREMENTS
(what must be present), not defect classes (what must be absent), and the
cold-open gate checks that emitted blocks EXECUTE, which a defective-but-runnable
block does.

MEASURED 2026-07-31 before this was written: the prose is CLEAN on all eleven
classes across its 16 fenced blocks, so this lands green and is a REGRESSION
gate, exactly as the charter gate was for the charters already hardened.

SCOPE, stated rather than hidden -- and `overseer.md` IS DELIBERATELY OUT.
The sibling prose `.claude-plugin/prose/overseer.md` reports one (a) hit,
`tmux switch-client -t livespec-autonomous-mode`, and it is NOT a defect:

  - It is the OPERATOR CONSOLE's copy-pasteable jump command, not a charter
    instruction, and the daemon really does emit the bare name -- deliberately,
    asserted in `overseer/test_supervisor_tmux_column_annotates.py` and
    commented in `overseer/_supervisor_render.py`.
  - Class (a) exists because a supervisor `send-keys` to a prefix-matched target
    types into the WRONG live session, silently, mutating someone else's work.
    A mis-targeted `switch-client` moves a human's view, which that human sees
    immediately and undoes. **The rationale does not transfer, so neither should
    the rule.**

Scanning it anyway would be a category error dressed as thoroughness: it would
redden the board over a tested, intentional, human-visible choice on a surface
this class was never written for. Recorded here so the next reader who runs the
detectors over `overseer.md` finds the answer instead of re-litigating it.
"""

from __future__ import annotations

from pathlib import Path

from test_charters_carry_no_known_defects import _code_blocks, defects_in

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GENERATOR_PROSE = _REPO_ROOT / ".claude-plugin" / "prose" / "supervise-plan.md"

# One defective line per class, in the shape the class was written for. Injected
# into the REAL prose rather than a synthetic stub, so the control proves the
# detectors reach this FILE and not merely a string that resembles it.
_INJECTIONS: dict[str, str] = {
    "a": "tmux send-keys -t my-session -- 'echo hi'",
    "d": 'prev=""; stable=0',
    "g": 'just check | tail -5; echo "EXIT=${PIPESTATUS[0]}"',
    "k": "stamped=$(date -u -r \"$marker\" '+%Y-%m-%dT%H:%M:%SZ')",
}


def _prose() -> str:
    return _GENERATOR_PROSE.read_text(encoding="utf-8")


def test_the_generator_prose_is_present_and_carries_fenced_blocks() -> None:
    """A gate over a missing or block-free file passes vacuously.

    The blocks are the point: the detectors read fenced code only, so a prose
    file with none of it would satisfy the gate below while proving nothing.

    Sabotage that reddens this: point `_GENERATOR_PROSE` at a file with no
    fenced blocks, such as this repo's `README.md`.
    """
    assert _GENERATOR_PROSE.is_file()
    assert len(_code_blocks(text=_prose())) > 1


def test_the_generator_prose_carries_none_of_the_known_defects() -> None:
    """THE GATE. A defect reintroduced into the template fails at SOURCE.

    Without this, the same defect is caught only once a charter generated from
    the template is committed to this repo -- and nothing schedules that.

    Sabotage that reddens this: add a bare `-t <session>` target to any fenced
    block in `.claude-plugin/prose/supervise-plan.md`.
    """
    assert defects_in(text=_prose()) == []


def test_the_detectors_reach_this_file() -> None:
    """POSITIVE CONTROL. A clean result is worthless without one.

    Each defect is appended to the REAL prose inside a fenced block and must be
    found. A control built on a synthetic stub would prove only that
    `defects_in` still works -- not that it sees THIS file, which is the claim
    the gate above actually makes.
    """
    unreached = [
        cls
        for cls, defect in sorted(_INJECTIONS.items())
        if not [
            found
            for found in defects_in(text=_prose() + "\n\n```sh\n" + defect + "\n```\n")
            if found.startswith(cls + "-")
        ]
    ]
    assert unreached == []
