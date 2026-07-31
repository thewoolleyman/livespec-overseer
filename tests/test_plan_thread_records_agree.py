"""A plan thread's two durable records must not disagree about its ledger anchor.

`overseer-bak`, caught in this repo's own exemplar thread. A livespec plan thread
keeps TWO durable records — `plan/<topic>/handoff.md`, the only file a restarted
session inherits, and `plan/<topic>/supervisor-handoff.md`, the charter a
supervisor boots from. **Nothing in the fleet reads the charter at all.** Measured
2026-07-31 against a passing positive control: searching all of
`livespec_dev_tooling` for `supervisor-handoff` returns ZERO modules, while
`plan_thread` returns three. The two plan-thread checks that do exist
(`plan-thread-anchor-declared`, `plan-thread-epic-parity`) read `handoff.md` only.

WHAT THIS CAUGHT, and it is not hypothetical. This thread's charter bound
`ledger_anchor='overseer-d4t'` in its **Verification Discipline** block — the very
block whose stated job is "re-measure the filed work item from the ledger before
carrying forward any status or acceptance claim". `overseer-d4t` is a **closed
bug** (closed 2026-07-30T19:34:35Z), and it is not an anchor this thread ever
declared: `handoff.md` declares the epics `overseer-byvxlp` and, for phase 2,
`overseer-yho`. So the block designed to stop stale claims was itself pointed at a
stale id, in the charter this repo holds up as its hardened exemplar, and the
eleven-class charter gate passed it — because those detectors are about shell and
tmux forms, and none of them reads across to the other record.

SCOPE, stated rather than hidden. This is a STATIC, file-versus-file rule: it needs
no ledger and no credential, so it runs in CI. It therefore cannot tell you the
anchor is CLOSED — only that the two records disagree. Closed-ness is
`plan-thread-epic-parity`'s job, and that check is armed-only and reads
`handoff.md` alone. Only charters that DECLARE an anchor are checked; the
pre-layered monolith charters in this repo declare none, and a rule that demanded
one would be a unilateral requirement on other tracks' threads.
"""

from __future__ import annotations

import re
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent
_THREADS = "plan/*/"

# The binder states its anchor twice, and BOTH spellings are load-bearing: the
# table is what a human reads, the assignment is what a supervisor executes. They
# can drift from each other, so they are compared to each other as well.
_ANCHOR_TABLE = re.compile(r"^\|\s*`ledger_anchor`\s*\|\s*`([^`]+)`\s*\|", re.MULTILINE)
_ANCHOR_EXEC = re.compile(r"^ledger_anchor='([^']+)'", re.MULTILINE)

# An anchor DECLARED by the handoff, e.g. `**Ledger anchor:** epic **`overseer-yho`**`.
# Keyed on the declaration, not on any mention: a handoff cites dozens of ids
# read-only, and being mentioned is not being anchored.
_HANDOFF_DECLARES = re.compile(r"[Ll]edger anchor:?\*{0,2}[^\n`]*`([a-z0-9-]+(?:\.[0-9]+)?)`")


def _charter_anchors(*, text: str) -> tuple[list[str], list[str]]:
    return _ANCHOR_TABLE.findall(text), _ANCHOR_EXEC.findall(text)


def _declared_anchors(*, text: str) -> list[str]:
    return _HANDOFF_DECLARES.findall(text)


def _threads_with_a_charter_anchor() -> list[tuple[str, str, list[str]]]:
    """(topic, charter_anchor, anchors_declared_by_handoff) for checkable threads."""
    out: list[tuple[str, str, list[str]]] = []
    for thread in sorted(_REPO_ROOT.glob(_THREADS)):
        charter = thread / "supervisor-handoff.md"
        handoff = thread / "handoff.md"
        if not charter.is_file() or not handoff.is_file():
            continue
        table, executable = _charter_anchors(text=charter.read_text(encoding="utf-8"))
        if not table and not executable:
            continue
        assert table == executable, (
            f"{thread.name}: the charter's own two anchor spellings disagree — "
            f"table {table} vs executable {executable}. A human reads one and a "
            f"supervisor runs the other."
        )
        out.append(
            (thread.name, table[0], _declared_anchors(text=handoff.read_text(encoding="utf-8")))
        )
    return out


def test_at_least_one_thread_declares_a_charter_anchor() -> None:
    """A rule that skips every thread passes vacuously and proves nothing.

    Sabotage that reddens this: delete the `ledger_anchor` binding from every
    charter. Without this, that sabotage would look like a clean repo — which is
    the exact shape of the gap `overseer-bak` describes.
    """
    assert _threads_with_a_charter_anchor() != []


def test_the_charter_anchor_is_one_the_handoff_actually_declares() -> None:
    """THE GATE. A charter anchored to an id its handoff never declared fails here.

    Sabotage that reddens this: set `ledger_anchor` back to `overseer-d4t`, which
    this thread's handoff declares nowhere.
    """
    offences = {
        topic: (anchor, declared)
        for topic, anchor, declared in _threads_with_a_charter_anchor()
        if anchor not in declared
    }
    assert offences == {}


def test_the_charter_anchor_is_the_current_one_the_handoff_declares() -> None:
    """Membership alone would let a SUPERSEDED anchor pass.

    A thread's current anchor is the most recently declared one — phase 2's epic
    supersedes phase 1's, and this thread's handoff declares both in that order.
    Without this, a charter left pointing at a delivered-and-closed phase-1 epic
    would satisfy the rule above forever.

    If a handoff ever declares its anchors in some other order, fix the ORDER or
    relax this rule deliberately — do not silence it by re-pointing the charter.
    """
    stale = {
        topic: (anchor, declared[-1])
        for topic, anchor, declared in _threads_with_a_charter_anchor()
        if declared and anchor != declared[-1]
    }
    assert stale == {}


def test_the_extractors_fire_on_the_shapes_they_are_written_for() -> None:
    """POSITIVE CONTROL. A zero from a scan is indistinguishable from a broken regex."""
    table, executable = _charter_anchors(
        text="| `ledger_anchor` | `overseer-yho` |\n\nledger_anchor='overseer-yho'\n"
    )
    assert table == ["overseer-yho"]
    assert executable == ["overseer-yho"]

    assert _declared_anchors(
        text="**Ledger anchor:** epic **`overseer-byvxlp`** (this repo's beads"
    ) == ["overseer-byvxlp"]
    assert _declared_anchors(text="**Phase-2 ledger anchor: epic `overseer-yho`.**") == [
        "overseer-yho"
    ]

    # A bare MENTION is not a declaration; a handoff cites many ids read-only.
    assert _declared_anchors(text="see `overseer-d4t` for the adopter argument") == []
