"""The three authoritative module docs must not deny a directory that exists.

`.claude/CLAUDE.md` tells every agent to read `overseer/marker-protocol.md`,
`overseer/SKILL.md` and `overseer/AGENTS.md` as AUTHORITATIVE before changing
anything under `overseer/`. Two of them stated, in the PRESENT TENSE, that this
repo has no `.ai/` directory. It has one: `7e246e0` added
`.ai/supervisor-protocol.md` on 2026-07-30, and that file is half of every
deployed supervisor charter. So a reader following CLAUDE.md's own instruction
was told a directory they were about to work with did not exist.

WHY THE NOTES ARE RE-TENSED AND NOT DELETED. Both are DATED notes (2026-07-26)
recording why two dead pointers were removed, and THE REMOVALS REMAIN CORRECT —
the pointer was to `.ai/agent-disciplines.md`, which still does not exist. Only
the supporting premise rotted. Deleting the notes would lose the record a reader
arriving from the archived predecessor thread comes looking for, which is the
reason those notes say they were "recorded rather than silently deleted".

WHY A GATE FOR TWO SENTENCES. Because the failure is a CLASS, not an instance:
a dated note's premise goes stale and nothing notices, which is the same shape as
a charter emitted by a stale generator. Fixing the sentences without fixing the
detection would remediate the instance and leave the class, which is the pattern
this repo's supervisor-prompt-quality work exists to stop.

SCOPE, stated rather than hidden. This gate is narrow on purpose: it knows about
`.ai/` and nothing else, because "a dated premise rotted" is not mechanically
decidable in general. It pins the one premise that HAS rotted and that a live
file now contradicts. It is keyed on the PRESENT TENSE, so the corrected
past-tense wording — the fix itself — is not flagged; a detector that fired on
the documentation of its own fix is what made the charter-gate prototype
unusable, and that lesson is re-applied here rather than re-learned.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# The three documents `.claude/CLAUDE.md` names authoritative, in its own order.
_MODULE_DOCS = (
    _REPO_ROOT / "overseer" / "marker-protocol.md",
    _REPO_ROOT / "overseer" / "SKILL.md",
    _REPO_ROOT / "overseer" / "AGENTS.md",
)
_OVERSEER_AGENTS = _REPO_ROOT / "overseer" / "AGENTS.md"

# The layered supervisor prompt's shared role layer. Named explicitly rather than
# globbing `.ai/`: an empty directory would satisfy a glob while the file that
# makes the denial false was gone, and it is the FILE that is half of every
# charter.
_SHARED_LAYER = _REPO_ROOT / ".ai" / "supervisor-protocol.md"

# A PRESENT-TENSE denial that the `.ai/` directory exists. Deliberately not
# matching the past tense: "there WAS no `.ai/` directory when this pointer was
# removed" is true, is the corrected wording, and must stay clean.
_PRESENT_TENSE_DENIAL = re.compile(
    r"(?:there\s+is\s+no|there\s+are\s+no|has\s+no)\s+`?\.ai\b[^`\s]*`?\s*(?:directory|dir)\b",
    re.IGNORECASE,
)


# Markdown blockquote markers, stripped before matching. Both live instances sit
# inside `>` quotes, and one of them WRAPS MID-CLAIM.
_BLOCKQUOTE = re.compile(r"^[ \t]*>[ \t]?", re.MULTILINE)


def _flattened(*, text: str) -> str:
    """Blockquote markers removed and whitespace collapsed to single spaces.

    LINE-SCOPED MATCHING MISSED THE INSTANCE THIS GATE WAS WRITTEN FOR. The
    `AGENTS.md` denial breaks as "there is no `.ai/`" / "directory in this repo",
    so a per-line search saw only `marker-protocol.md` and reported the other
    file clean. Markdown gets rewrapped, so any prose rule that depends on where
    the lines happen to break is one reflow away from going blind — the same
    failure that made a set of prose needles fail for formatting rather than for
    meaning earlier in this same epic.
    """
    return " ".join(_BLOCKQUOTE.sub("", text).split())


def denials_of_the_ai_directory(*, text: str) -> list[str]:
    """Every present-tense claim that `.ai/` does not exist, as matched spans."""
    return [match.group(0) for match in _PRESENT_TENSE_DENIAL.finditer(_flattened(text=text))]


def test_the_shared_supervisor_layer_exists():
    """The premise the denial contradicts, asserted rather than assumed.

    Without this the module below could go green because `.ai/` had been REMOVED,
    which would make the denials true again and the gate meaningless. Pinning the
    file first is what makes the absence of denials mean something.
    """
    assert _SHARED_LAYER.is_file(), (
        f"{_SHARED_LAYER} is missing. It is the shared role layer of every "
        "generated supervisor charter; if it genuinely moved, update this module "
        "and the module docs together rather than deleting this assertion."
    )


def test_no_authoritative_module_doc_denies_the_ai_directory():
    """The gate. A reader told to treat these as authoritative must not be lied to."""
    found = {
        doc.relative_to(_REPO_ROOT).as_posix(): denials_of_the_ai_directory(
            text=doc.read_text(encoding="utf-8")
        )
        for doc in _MODULE_DOCS
    }
    assert {path: lines for path, lines in found.items() if lines} == {}


def test_the_detector_fires_on_the_wording_that_actually_shipped():
    """POSITIVE CONTROL. Without it, a clean result is indistinguishable from a
    broken pattern — the hazard this repo has recorded three times.

    Both strings below are the verbatim wording that was live in
    `marker-protocol.md` and `AGENTS.md` until this change.
    """
    marker = ">   there is no `.ai/` directory in this repo at all. That section stated this"
    # VERBATIM, INCLUDING THE LINE BREAK MID-CLAIM. This is the instance a
    # line-scoped detector missed, so it is pinned exactly as it shipped rather
    # than re-joined to suit the pattern.
    agents = (
        "> - **the root `AGENTS.md`'s `.ai/agent-disciplines` topic** — there is no `.ai/`\n"
        ">   directory in this repo at all, and the root `AGENTS.md` contains no `.ai/`\n"
    )
    assert denials_of_the_ai_directory(text=marker) != []
    assert denials_of_the_ai_directory(text=agents) != []


def test_the_corrected_past_tense_wording_is_not_flagged():
    """THE CONTROL THAT MAKES THE FIX LANDABLE, and the reason for tense-keying.

    A detector that flagged the corrected sentence would make documenting the
    correction reopen the defect — the exact property that made the whole-file
    charter-gate prototype unusable.
    """
    corrected = (
        "there was no `.ai/` directory in this repo when this pointer was removed. "
        "A `.ai/` directory exists today and holds only `supervisor-protocol.md`; "
        "`.ai/agent-disciplines.md` still does not exist, so the removal stands."
    )
    assert denials_of_the_ai_directory(text=corrected) == []


def test_overseer_isolation_tip_keeps_session_discovery_visible():
    """The scratch-HOME recipe must not silently blind adoption.

    The operator guide's worked example is also the only documented safe live
    exercise path. A pure scratch HOME correctly isolates the store but also
    hides `~/.claude/sessions` and `~/.codex`, making adoption look broken.
    """
    text = _OVERSEER_AGENTS.read_text(encoding="utf-8")
    section = text.split("**Isolation tip for exercising `overseerd`", maxsplit=1)[1].split(
        "The daemon's diagnostics", maxsplit=1
    )[0]

    assert 'ln -s ~/.claude "$SCRATCH_HOME/.claude"' in section
    assert 'ln -s ~/.codex  "$SCRATCH_HOME/.codex"' in section
    assert 'ln -s ~/.cache  "$SCRATCH_HOME/.cache"' in section
    assert "`~/.claude/sessions` for Claude Code and `~/.codex`" in section
    assert "Adoption is bounded by the\n   watch-set, not by the registry" in section
    assert "all-`unassigned` render" in section
    assert "blinded session\n   discovery" in section
