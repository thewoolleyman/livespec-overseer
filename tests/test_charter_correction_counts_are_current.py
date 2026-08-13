"""A correction count stated in prose must equal the corrections that exist.

`plan/supervisor-prompt-quality/handoff.md` names this gap and leaves it open:
"**Prefer a rule that recounts over a number that ages**; where a number must
appear, date it... **Nothing gates this — the count sits in prose that no test
reads.**" This module is that rule.

WHAT IT CAUGHT BEFORE IT EXISTED, which is why the count is worth a gate rather
than a proofread. The same handoff asserted "all **16** Corrections (C1-C16).
Verified present with 16 entries" while the charter held **19**, and asserted a
binder of "**126 lines**" against an actual 266. The 16 was not merely stale: the
handoff **cites C19 elsewhere**, as the `date -u -r` correction detector (k)
implements, so the file contradicted itself three lines apart and a reader
trusting the count would have concluded that C17, C18 and C19 do not exist while
reading a sentence that depends on C19.

WHY IT DRIFTS, because the mechanism generalises past this one sentence. A count
is a claim with a timestamp and it is the WORST kind — it looks like a fact
rather than a measurement, "Verified present with 16 entries" reads as though
someone checked (they did, once), and **appending a correction never touches the
sentence that counts them.** Both `## Corrections` sections are append-only by
design, so the number drifts on EVERY append, silently, forever. Nothing else in
the tree reads it: the eleven-class charter gate keys on shell and tmux forms,
and `test_plan_records_agree.py` compares ledger anchors.

KEYED ON THE ENTRY, NOT ON THE MENTION, and that is load-bearing here. The
protocol discusses its own corrections in running prose — `.ai/supervisor-protocol.md`
carries an indented `**C14 IS NOW DEMONSTRATED, NOT MERELY ASSERTED**` note under
the C14 entry, and a rule matching any `C<n>` at line start counts **21** where
the true answer is **19**. A detector fooled by prose that MENTIONS a correction
is the same failure the charter gate and the rig-socket gate each carry a
dedicated control for.

MATCHED OVER WHITESPACE-COLLAPSED PROSE. The asserted count and the noun it
counts sit on opposite sides of a line break ("holding **19**\\nrole-level
Corrections"), and markdown gets rewrapped constantly — a prose rule that depends
on where lines break is one reflow from going blind.

SCOPE, stated rather than hidden. This gates the CORRECTION COUNTS only, not the
line counts the same two bullets carry. That is deliberate: a line count changes
on every edit to either file, so gating it would redden unrelated work and train
the reflex this repo argues against — editing a number until the gate goes green.
A correction count changes only on append, which is rare and always intentional.
The rule is also static and file-versus-file: it needs no ledger and no
credential, so it runs in CI.

APPENDING A CORRECTION WILL REDDEN THIS, and that is the whole point. The fix is
to update the one sentence in `handoff.md` that states the count — not to relax
the rule.
"""

from __future__ import annotations

import re
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _thread_file(*, rel: str) -> Path:
    """Resolve a plan file at its LIVE or ARCHIVED location.

    A plan moves to `plan/archive/<topic>/` when its epic closes, so a
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


_PROTOCOL = _REPO_ROOT / ".ai" / "supervisor-protocol.md"
_BINDER = _thread_file(rel="supervisor-prompt-quality/supervisor-handoff.md")
_HANDOFF = _thread_file(rel="supervisor-prompt-quality/handoff.md")

# An ENTRY in a `## Corrections` list: a top-level bullet opening with the bolded
# id. The leading `- ` is what distinguishes an entry from prose about an entry.
_ROLE_ENTRY = re.compile(r"^- \*\*C(\d+)\b", re.MULTILINE)
_THREAD_ENTRY = re.compile(r"^- \*\*T(\d+)\b", re.MULTILINE)

# Every dash a prose author might type between C1 and the last id. Spelled as
# ESCAPES rather than literal characters: the linter rejects ambiguous Unicode in
# source, and a rule that accepted only the one dash in the file today would go
# blind the first time someone retyped the range. The live handoff uses U+2013.
_DASHES = "\u2010\u2011\u2012\u2013\u2014\u2015-"

# The counts the handoff ASSERTS. Matched against whitespace-collapsed text, so
# these patterns must not assume any particular wrapping. The role bullet states
# the count AND the range endpoint; both are captured, because they can drift
# from each other as well as from the charter.
_ASSERTS_ROLE = re.compile(
    r"holding \*\*(\d+)\*\* role-level Corrections, C1[" + _DASHES + r"]C(\d+)"
)
_ASSERTS_THREAD = re.compile(r"carrying \*\*(\d+)\*\* thread-specific correction")


def _entries(*, text: str, pattern: re.Pattern[str]) -> list[int]:
    """The correction numbers actually present, in document order."""
    return [int(n) for n in pattern.findall(text)]


def _flat(*, text: str) -> str:
    """Collapse whitespace so a rule cannot be defeated by a reflow."""
    return re.sub(r"\s+", " ", text)


def _read(*, path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_two_charter_layers_and_the_handoff_are_all_present() -> None:
    """A rule over missing files passes vacuously and proves nothing.

    Sabotage that reddens this: rename `.ai/supervisor-protocol.md`.
    """
    assert _PROTOCOL.is_file()
    assert _BINDER.is_file()
    assert _HANDOFF.is_file()


def test_the_handoff_actually_states_both_counts() -> None:
    """ANTI-VACUOUS GUARD. A deleted or rephrased sentence must not read as clean.

    Without this, dropping the counting sentence would silence the gate below
    rather than fail it — the extraction would return nothing and the comparison
    would hold trivially. That is the failure mode this whole module exists to
    stop, so it must not be reachable through the module's own front door.

    Sabotage that reddens this: delete the two bullets naming the counts.
    """
    flat = _flat(text=_read(path=_HANDOFF))
    assert _ASSERTS_ROLE.findall(flat) != []
    assert _ASSERTS_THREAD.findall(flat) != []


def test_the_role_level_count_in_prose_matches_the_shared_layer() -> None:
    """THE GATE. Appending C20 without updating the handoff fails here.

    Sabotage that reddens this: change the stated count to 16, which is what it
    actually said while the charter held 19.
    """
    stated_count, stated_last = _ASSERTS_ROLE.findall(_flat(text=_read(path=_HANDOFF)))[0]
    actual = _entries(text=_read(path=_PROTOCOL), pattern=_ROLE_ENTRY)

    assert int(stated_count) == len(actual), (
        f"handoff.md says {stated_count} role-level Corrections; "
        f"{_PROTOCOL.name} carries {len(actual)}. Update the sentence, not this rule."
    )
    assert int(stated_last) == actual[-1], (
        f"handoff.md says the range ends at C{stated_last}; " f"the last entry is C{actual[-1]}."
    )


def test_the_thread_specific_count_in_prose_matches_the_binder() -> None:
    """THE GATE, thread layer. A second T-correction without a prose update fails.

    Sabotage that reddens this: append a `- **T2 — ...**` entry to the binder.
    """
    stated = _ASSERTS_THREAD.findall(_flat(text=_read(path=_HANDOFF)))[0]
    actual = _entries(text=_read(path=_BINDER), pattern=_THREAD_ENTRY)

    assert int(stated) == len(actual), (
        f"handoff.md says {stated} thread-specific correction(s); "
        f"{_BINDER.name} carries {len(actual)}."
    )


def test_correction_ids_are_contiguous_from_one() -> None:
    """An append that reuses or skips a number is a defect the counts would hide.

    Two entries numbered C14 give a count of 20 for a range ending at C19, and
    the length check alone would be satisfied by adding any 20th entry. Ordering
    is asserted too: these are append-only logs, so document order IS numeric
    order, and a correction inserted in the middle is a rewritten history.

    Sabotage that reddens this: renumber the C19 entry to C21.
    """
    role = _entries(text=_read(path=_PROTOCOL), pattern=_ROLE_ENTRY)
    thread = _entries(text=_read(path=_BINDER), pattern=_THREAD_ENTRY)

    assert role == list(range(1, len(role) + 1)), f"role-level ids are not 1..N: {role}"
    assert thread == list(range(1, len(thread) + 1)), f"thread ids are not 1..N: {thread}"


def test_the_extractors_fire_on_the_shapes_they_are_written_for() -> None:
    """POSITIVE CONTROL. A zero from a scan is indistinguishable from a broken regex.

    The control uses FOREIGN text rather than the live files, so it proves the
    patterns match the shape and not merely that today's tree happens to parse.
    """
    assert _entries(
        text="- **C1 (2026-07-26) — I trusted `tmux has-session`\n- **C2 (2026-07-26) — x",
        pattern=_ROLE_ENTRY,
    ) == [1, 2]
    assert _entries(text="- **T1 — `ledger_anchor` pointed at a", pattern=_THREAD_ENTRY) == [1]

    # The asserted-count patterns, against text wrapped where the live file wraps.
    wrapped = "the shared role layer, holding **19**\nrole-level Corrections, C1\u2013C19."
    assert _ASSERTS_ROLE.findall(_flat(text=wrapped)) == [("19", "19")]

    wrapped_thread = (
        "the thin binder,\n**266 lines**, carrying **1** thread-specific correction (T1)."
    )
    assert _ASSERTS_THREAD.findall(_flat(text=wrapped_thread)) == ["1"]


def test_prose_about_a_correction_is_not_counted_as_a_correction() -> None:
    """A mention is not an entry, and the difference is 21 versus 19.

    NOT hypothetical. `.ai/supervisor-protocol.md` carries an indented
    `**C14 IS NOW DEMONSTRATED, NOT MERELY ASSERTED (2026-07-30).**` note beneath
    the C14 entry, and `handoff.md` discusses C19 by name. A rule anchored to any
    `C<n>` at line start counts both and reports 21 — a count that is wrong in the
    direction that looks like MORE evidence, which is the hardest kind to doubt.

    Sabotage that reddens this: relax `_ROLE_ENTRY` to `^\\s*\\*{0,2}C(\\d+)`.
    """
    assert (
        _entries(text="  **C14 IS NOW DEMONSTRATED, NOT MERELY ASSERTED**", pattern=_ROLE_ENTRY)
        == []
    )
    assert (
        _entries(text="This is charter correction C19 and detector (k).", pattern=_ROLE_ENTRY) == []
    )
    assert (
        _entries(
            text="  - **C7 (2026-07-28) — nested, so not a top-level entry", pattern=_ROLE_ENTRY
        )
        == []
    )

    # And the live protocol yields exactly its entries under the strict rule while
    # a loose one over-counts — the end-to-end form of the same claim.
    protocol = _read(path=_PROTOCOL)
    loose = re.compile(r"^\s*[-*]?\s*\*{0,2}C(\d+)\b", re.MULTILINE)
    assert len(loose.findall(protocol)) > len(_entries(text=protocol, pattern=_ROLE_ENTRY))
