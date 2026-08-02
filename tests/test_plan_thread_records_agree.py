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

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _thread_file(*, rel: str) -> Path:
    """Resolve a plan-thread file at its LIVE or ARCHIVED location.

    A thread moves to `plan/archive/<topic>/` when its epic closes, so a
    hardcoded live path is guaranteed to become invalid. This gate must keep
    following the REAL artifact rather than a vendored copy: its whole purpose
    is to catch drift in live prose, and a fixture would make it vacuous.
    """
    # Branch-free by construction: a conditional here is an unavoidable PARTIAL
    # branch, because only one arc can ever run in a given tree state, and this
    # repo runs fail-under=100 with branch coverage. `plan/**/` spans the live and
    # archived locations in one pattern. An empty match raises IndexError, which
    # is the loud failure a genuine miss should produce.
    return sorted(_REPO_ROOT.glob(f"plan/**/{rel}"))[0]


# Live AND archived threads. A thread moves to `plan/archive/<topic>/` when its
# epic closes, and an archived pair can still DISAGREE — a wrong record does not
# become right by being archived. Scoping to live threads alone also made this
# module vacuous the moment the only declaring thread archived, which is the
# failure its own anti-vacuous guard exists to catch.
_THREADS = ("plan/*/", "plan/archive/*/")

# The binder states its anchor twice, and BOTH spellings are load-bearing: the
# table is what a human reads, the assignment is what a supervisor executes. They
# can drift from each other, so they are compared to each other as well.
_ANCHOR_TABLE = re.compile(r"^\|\s*`ledger_anchor`\s*\|\s*`([^`]+)`\s*\|", re.MULTILINE)
_ANCHOR_EXEC = re.compile(r"^ledger_anchor='([^']+)'", re.MULTILINE)

# An anchor DECLARED by the handoff, e.g. `**Ledger anchor:** epic **`overseer-yho`**`.
# Keyed on the declaration, not on any mention: a handoff cites dozens of ids
# read-only, and being mentioned is not being anchored.
_HANDOFF_DECLARES = re.compile(r"[Ll]edger anchor:?\*{0,2}[^\n`]*`([a-z0-9-]+(?:\.[0-9]+)?)`")


# The THIRD spelling, which is REAL and lives in the fleet: homelab's five
# binders declare theirs as `- Ledger epic anchor — `x``. Without it a charter
# using that form extracts nothing and is SILENTLY SKIPPED by the loop below —
# the vacuous-pass shape, in the gate whose whole job is catching a stale anchor.
#
# Safe to add here, verified rather than assumed: no charter in this repo uses
# OR quotes this spelling, so it cannot manufacture an anchor out of prose.
# Dashes as ESCAPES, not literals: the linter rejects ambiguous Unicode in
# source, and homelab uses U+2014 EM DASH here.
_BULLET_DASHES = "\u2012\u2013\u2014\u2015-"
_ANCHOR_BULLET = re.compile(
    r"[Ll]edger epic anchor\s*[" + _BULLET_DASHES + r"]\s*`([a-z0-9-]+(?:\.[0-9]+)?)`"
)


def _charter_anchors(*, text: str) -> tuple[list[str], list[str], list[str]]:
    return _ANCHOR_TABLE.findall(text), _ANCHOR_EXEC.findall(text), _ANCHOR_BULLET.findall(text)


def _anchor_from(*, topic: str, table: list[str], executable: list[str], bullet: list[str]) -> str:
    """The charter's anchor, with the table/executable PAIR still mandatory.

    Split out of the loop so the bullet-only branch is reachable from a unit
    test: this repo has no bullet-spelled charter, and a branch exercised only
    by a file that does not exist is a branch nothing checks.

    The pair strictness is deliberately NOT relaxed. A charter using the
    table/executable form must carry BOTH and they must agree — a human reads
    one and a supervisor runs the other. Only a charter using neither falls
    through to the foreign spelling.
    """
    if table or executable:
        assert table == executable, (
            f"{topic}: the charter's own two anchor spellings disagree — "
            f"table {table} vs executable {executable}. A human reads one and a "
            f"supervisor runs the other."
        )
        return table[0]
    return bullet[0]


def _declared_anchors(*, text: str) -> list[str]:
    return _HANDOFF_DECLARES.findall(text)


def _threads_with_a_charter_anchor(*, root: Path = _REPO_ROOT) -> list[tuple[str, str, list[str]]]:
    """(topic, charter_anchor, anchors_declared_by_handoff) for checkable threads.

    `root` exists so every arc below is reachable from a synthetic tree — the
    same reason `_anchor_from` was split out of this loop. Without it, which
    arcs execute depends on which threads happen to be LIVE, and coverage
    becomes a quantity over repo state: archiving the last live thread with
    both files and no anchor made the no-anchor `continue` unreachable and
    turned master's coverage gates red at 99% with every test passing
    (2026-08-02, the codex-parity-and-rollout-safety archive, reverted).
    """
    out: list[tuple[str, str, list[str]]] = []
    threads = sorted({d for pattern in _THREADS for d in root.glob(pattern)})
    for thread in threads:
        charter = thread / "supervisor-handoff.md"
        handoff = thread / "handoff.md"
        if not charter.is_file() or not handoff.is_file():
            continue
        table, executable, bullet = _charter_anchors(text=charter.read_text(encoding="utf-8"))
        if not table and not executable and not bullet:
            continue
        anchor = _anchor_from(topic=thread.name, table=table, executable=executable, bullet=bullet)
        out.append(
            (thread.name, anchor, _declared_anchors(text=handoff.read_text(encoding="utf-8")))
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
    table, executable, bullet = _charter_anchors(
        text="| `ledger_anchor` | `overseer-yho` |\n\nledger_anchor='overseer-yho'\n"
    )
    assert table == ["overseer-yho"]
    assert executable == ["overseer-yho"]
    assert bullet == []

    assert _declared_anchors(
        text="**Ledger anchor:** epic **`overseer-byvxlp`** (this repo's beads"
    ) == ["overseer-byvxlp"]
    assert _declared_anchors(text="**Phase-2 ledger anchor: epic `overseer-yho`.**") == [
        "overseer-yho"
    ]

    # A bare MENTION is not a declaration; a handoff cites many ids read-only.
    assert _declared_anchors(text="see `overseer-d4t` for the adopter argument") == []


def test_documenting_the_defect_does_not_recreate_it() -> None:
    """The handoff DISCUSSES anchors, including wrong ones. Prose must not count.

    NOT hypothetical, and not a style point — every line below is real prose from
    `plan/supervisor-prompt-quality/handoff.md`, written to document the very
    defect this module gates. A shell-side version of this rule was drafted and
    REJECTED because it fell for exactly these: `grep -iE 'ledger.{0,24}anchor'`
    over the handoff matches the sentence recording that the anchor used to be
    `overseer-d4t`, so a charter still bound to `overseer-d4t` would have passed a
    check whose whole purpose is to catch that binding.

    That is the same failure the charter gate carries
    `test_prose_describing_a_hazard_is_not_counted_as_the_hazard` for, and it is
    the reason this extractor keys on `ledger anchor` with a SPACE plus a
    same-line backticked id: `ledger_anchor` with an underscore is how the defect
    gets QUOTED, and `Ledger epic anchor` is a foreign spelling that appears here
    only as quoted evidence.

    Sabotage that reddens this: relax `_HANDOFF_DECLARES` to allow an underscore
    or an intervening word.
    """
    quoted_defect = (
        "The only divergence in the fleet was THIS repo's own — " "`ledger_anchor='overseer-d4t'`,"
    )
    assert _declared_anchors(text=quoted_defect) == []

    table_row = "| charters DECLARING a ledger anchor | 7 |"
    assert _declared_anchors(text=table_row) == []

    foreign_spelling_quoted = "`- Ledger epic anchor — `x`` (bullet prose, homelab x5). My first"
    assert _declared_anchors(text=foreign_spelling_quoted) == []

    # And the live file still yields exactly the two anchors it declares — the
    # end-to-end form of the same claim, so a future edit to the handoff that
    # smuggles in a third cannot pass unnoticed.
    handoff = _thread_file(rel="supervisor-prompt-quality/handoff.md")
    assert _declared_anchors(text=handoff.read_text(encoding="utf-8")) == [
        "overseer-byvxlp",
        "overseer-yho",
    ]


def test_the_foreign_bullet_spelling_is_read_rather_than_silently_skipped() -> None:
    """A charter using homelab's spelling must be COMPARED, not passed over.

    The loop's `continue` is the danger: a spelling the extractor cannot read is
    indistinguishable from a charter that declares nothing, so the gate reports
    a clean repo over a charter it never examined. That is the vacuous pass this
    suite guards against everywhere else.

    Measured 2026-07-31: this spelling is REAL — five homelab binders use it,
    and a scan that omitted it reported 2 charters declaring an anchor fleet-wide
    against a true 7.

    Sabotage that reddens this: delete `_ANCHOR_BULLET` from `_charter_anchors`.
    """
    table, executable, bullet = _charter_anchors(text="- Ledger epic anchor — `homelab-x9q`\n")
    assert (table, executable) == ([], [])
    assert bullet == ["homelab-x9q"]
    assert _anchor_from(topic="t", table=[], executable=[], bullet=bullet) == "homelab-x9q"


def test_the_table_and_executable_pair_is_still_mandatory_together() -> None:
    """Adding a third spelling must not weaken the rule for the first two.

    A charter using the table/executable form has to carry BOTH and they must
    agree; only a charter using NEITHER falls through to the foreign spelling.
    Without this, the `or` added for the bullet would silently let a charter
    declare a table anchor with no executable binding — readable by a human,
    unrunnable by a supervisor.

    Sabotage that reddens this: relax `_anchor_from` to `if table and executable`.
    """
    with pytest.raises(AssertionError, match="two anchor spellings disagree"):
        _anchor_from(topic="t", table=["a"], executable=[], bullet=[])
    with pytest.raises(AssertionError, match="two anchor spellings disagree"):
        _anchor_from(topic="t", table=["a"], executable=["b"], bullet=[])


def test_a_charter_that_merely_mentions_an_anchor_declares_none() -> None:
    """Prose in a CHARTER must not be read as a declaration — a real near-miss.

    Every line below is real text from this repo's charters. The first is why a
    broader "looks like a declaration but did not extract" guard was DESIGNED
    AND REJECTED: `plan/fabro-review-classifier-defect/supervisor-handoff.md`
    discusses the ledger anchor in prose while declaring none, so a rule keyed on
    the PHRASE would have reddened a correct charter. Measured before writing,
    which is the only reason it was not shipped.

    Sabotage that reddens this: widen `_ANCHOR_BULLET` to match the phrase
    without requiring the dash and the backticked id.
    """
    mention = "`plan/*/handoff.md` **only**, and both are about the **ledger anchor** —"
    assert _charter_anchors(text=mention) == ([], [], [])

    listed_as_a_binding_name = (
        "  `supervisor_session`, `WORKER_TARGET`, `SUPERVISOR_TARGET`, `ledger_anchor`."
    )
    assert _charter_anchors(text=listed_as_a_binding_name) == ([], [], [])


def test_every_scan_arc_is_reachable_on_a_synthetic_tree(*, tmp_path: Path) -> None:
    """Which arcs of the thread scan execute must not depend on the LIVE plan/ set.

    NOT hypothetical — measured 2026-08-02 on master. Archiving
    `plan/codex-parity-and-rollout-safety/` (the LAST live thread carrying both
    records while declaring no anchor) made the no-anchor `continue` in
    `_threads_with_a_charter_anchor` unreachable: `check-coverage` and
    `check-per-file-coverage` went RED at 99% < 100 with all 804 tests PASSING,
    and only on master — the docs-only PR lane skips the suite jobs, so the
    branch was green. `fabro-review-classifier-defect`'s archive had stayed
    green purely because ours still covered the arc: musical chairs, not
    safety. This leg drives every arc from a synthetic tree so no `git mv` of a
    plan thread can move this module's coverage again.

    SCOPE, stated because the neighbouring rule is deliberately different:
    `test_at_least_one_thread_declares_a_charter_anchor` still quantifies over
    the LIVE set, and must — "at least one live thread declares an anchor" is a
    real invariant that SHOULD fail when the last anchored thread archives.
    This leg makes coverage independent of repo state; it does not make that
    assertion tolerate an empty set.

    Sabotage that reddens this: drop the `root` parameter and glob `_REPO_ROOT`
    unconditionally — this leg then stops reaching the no-anchor arc the moment
    no live thread exercises it, which is exactly the 2026-08-02 shape.
    """
    plan = tmp_path / "plan"
    (plan / "only-handoff").mkdir(parents=True)
    (plan / "only-handoff" / "handoff.md").write_text("no charter beside me\n", encoding="utf-8")
    (plan / "only-charter").mkdir()
    (plan / "only-charter" / "supervisor-handoff.md").write_text(
        "no handoff beside me\n", encoding="utf-8"
    )
    (plan / "no-anchor").mkdir()
    (plan / "no-anchor" / "supervisor-handoff.md").write_text(
        "a pre-layered monolith charter: prose, tmux forms, no anchor declared\n",
        encoding="utf-8",
    )
    (plan / "no-anchor" / "handoff.md").write_text("thread prose only\n", encoding="utf-8")
    (plan / "anchored").mkdir()
    (plan / "anchored" / "supervisor-handoff.md").write_text(
        "| `ledger_anchor` | `overseer-zz1` |\n\nledger_anchor='overseer-zz1'\n",
        encoding="utf-8",
    )
    (plan / "anchored" / "handoff.md").write_text(
        "**Ledger anchor:** epic `overseer-zz1`.\n", encoding="utf-8"
    )

    assert _threads_with_a_charter_anchor(root=tmp_path) == [
        ("anchored", "overseer-zz1", ["overseer-zz1"])
    ]
