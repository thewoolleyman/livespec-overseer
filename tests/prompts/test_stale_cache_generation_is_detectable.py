"""RED against a real STALE-CACHE generation, which nothing has demonstrated yet.

This is `overseer-yho.2`'s acceptance clause, inherited from `overseer-d4t`:
demonstrate red against a stale-cache generation SPECIFICALLY, not against repo
prose. Every fixture in `tests/prompts/` today reads
`.claude-plugin/prose/supervise-plan.md` from the working tree — the file we
edit — so each is green the instant a fix lands and none of them can say
anything about the artifact that actually generates charters on an adopter host.
All of them were green while commit `d49acc620` emitted a charter carrying
twelve bare targets and turned master red fleet-wide.

WHAT ACTUALLY GENERATES. Adopters emit from
`~/.claude/plugins/cache/<marketplace>/<plugin>/<ref>/prose/`. Measured
2026-07-30 on this host, that directory holds ELEVEN refs and THREE distinct
prose generations — not the stale/current pair the thread had recorded:

    ref                          prose md5   lines  plugin.json
    0.12.2 .. efe607c6a3e7 (x9)  2283862c     291   0.12.2 - 0.13.3
    1af636d4a61e                 30b59fcf     491   0.14.0
    013d35d48cde                 9ca18d56     567   0.15.0  (= this repo's prose)

Two of those ref directories are named for a VERSION and nine for a commit sha,
so the directory name is not a usable identity key in either direction; and
`.in_use` is present on nine of the eleven, including every stale one, so it does
not mark the active cache either. The digest is the only thing that identifies a
generation, which is why every row below is pinned by one.

WHY THE STALE ARTIFACTS ARE VENDORED, having first been done the other way. CI
has no plugin cache and never will, so reading one would force a skip — and a
skipped leg on the single axis every other fixture is blind to is the
verifier-that-cannot-fail shape this epic exists to remove. The first attempt
reached them through git history instead, which works locally and FAILED IN CI:
the py-gated matrix checks out at depth 1 deliberately, and `ci.yml` classifies
anything needing full history into the always-run `fetch-depth: 0` metadata
matrix, "NOT the py-gated one". A pytest module cannot move matrices, so the
history dependency had to go rather than the workflow. Each artifact below is
therefore committed byte-exact, extracted from the commit named in its row, and
pinned by the md5 MEASURED IN THE LIVE CACHE — re-derivable with
`git show <commit>:.claude-plugin/prose/supervise-plan.md | md5sum`.

WHAT IT FINDS, and it is not what the ticket assumed. Running the SHIPPED
validators — imported, never re-implemented — over all three:

    generation                 contract failures   defect classes (a..k)
    frozen  0.12.2-0.13.3          31              15  (a, b, c, d)
    stale   0.14.0                  0               3  (h, i, j)
    current 0.15.0                  0               0

The frozen generation is red, which discharges the acceptance clause. The
0.14.0 generation is the finding: TODAY'S contract floor — the most evolved one
this repo has — reports it as fully conformant while it is provably stale and
provably defective. Its verdict is byte-identical to the current generation's,
so the floor cannot rank the two at all. Every defect it does carry is visible
only to detectors (h), (i) and (j), all three of which were written AFTER it
shipped; no detector that existed at the time can see any of them.

THE CONSEQUENCE FOR THE FIX. A content gate can only recognise staleness it
already has a detector for, so it is always exactly one release behind. That is
the case for recording provenance, and it is a stronger case than the ticket
made: the point is not that a stale charter carries known defects, it is that
the NEXT stale generation will carry defects nobody has named yet and will score
zero on everything here.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import NamedTuple

import pytest
import test_charters_carry_no_known_defects as defect_gate
import test_generated_supervisor_handoff_contract as contract_gate

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Detector classes that already existed when the 0.14.0 generation shipped
# (`283fb5e`, 2026-07-30T05:14:39Z). (g) landed at `c690d22` earlier that night;
# (h), (i) and (j) at `814c1da` seven hours LATER, and (k) later still. The set
# is what makes "only detectors written after it can see it" a mechanical claim
# instead of a sentence in a comment.
_CLASSES_PREDATING_THE_STALE_GENERATION = frozenset("abcdefg")


class _Generation(NamedTuple):
    """One prose generation that really exists in an adopter's plugin cache.

    `md5` and `lines` are measured from the CACHE. `path` is where those exact
    bytes live in this repo, and `commit` is where they were extracted from, so
    a reader can re-derive the vendored copy rather than trusting it.
    """

    label: str
    path: str
    md5: str
    lines: int
    cache_refs: int
    versions: str
    commit: str


_GENERATIONS = (
    _Generation(
        label="frozen",
        path="tests/prompts/fixtures/cached-prose-2283862c.md",
        md5="2283862cf32b60b2e82c02164c9b3b83",
        lines=291,
        cache_refs=9,
        versions="0.12.2 through 0.13.3",
        commit="adff90ad6ecb99fb88219631e56afcae6bd5e7f8",
    ),
    _Generation(
        label="stale",
        path="tests/prompts/fixtures/cached-prose-30b59fcf.md",
        md5="30b59fcf0ea5f3cf78402129826b1ffa",
        lines=491,
        cache_refs=1,
        versions="0.14.0",
        commit="283fb5e3e860cd06c4a43dce22724b8b6625f69f",
    ),
    # The current generation is NOT vendored: the cache ref `013d35d48cde` is
    # byte-identical to the working tree's prose, so the live file IS the
    # artifact. Freezing a copy of it would go stale on the next legitimate
    # prose change and redden master for the wrong reason.
    _Generation(
        label="current",
        path=".claude-plugin/prose/supervise-plan.md",
        md5="9ca18d56772dcf8fcdc2cf78ed8108a8",
        lines=567,
        cache_refs=1,
        versions="0.15.0",
        commit="0eb809f029cf1ee98a57c6232f6070698641a558",
    ),
)

_BY_LABEL = {generation.label: generation for generation in _GENERATIONS}


def cached_generation(*, label: str) -> str:
    """One real cached generation, verified byte-exact against the live cache.

    The digest assertion is what makes a committed copy equivalent to reading
    the cache. Without it this module would be testing whatever the file happens
    to hold today, which is the repo-prose failure it exists to escape. A
    MISSING artifact fails loudly rather than skipping, for the same reason
    `check-prose-release-hygiene` rejects an unresolvable base ref instead of
    passing: a skip here would make the one gate covering the stale-cache axis
    silently absent in exactly the environment where nobody is watching.
    """
    generation = _BY_LABEL[label]
    path = _REPO_ROOT / generation.path
    if not path.is_file():
        raise AssertionError(
            f"the {label!r} cached generation is missing at {generation.path}. "
            "Restore it byte-exact with "
            f"`git show {generation.commit}:.claude-plugin/prose/supervise-plan.md` "
            "rather than deleting this leg."
        )
    text = path.read_text(encoding="utf-8")
    digest = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
    assert digest == generation.md5, (
        f"generation {label!r} at {generation.path} has md5 {digest}, but the "
        f"cache directories hold {generation.md5}. The pin identifies WHICH "
        "artifact this is; re-measure the cache rather than relaxing it."
    )
    return text


def _contract_failures(*, text: str) -> list[str]:
    """The SHIPPED contract validator's verdict. Never a local re-implementation.

    A fixture that tests a COPY of a rule goes green while the shipped rule rots
    — `tests/test_prose_release_hygiene.py`'s reasoning, applied here.
    """
    return contract_gate.missing_requirements(charter=text)


def _defect_classes(*, text: str) -> set[str]:
    """The letter of every defect class the shipped (a)..(k) gate reports."""
    return {finding.split("-", 1)[0] for finding in defect_gate.defects_in(text=text)}


def test_every_real_generation_matches_the_digest_measured_in_the_cache():
    """THE PIN. Each row must hold exactly the bytes a cache directory holds.

    This is what lets the rest of the module claim it is measuring the artifact
    that really generates charters rather than one that resembles it.
    """
    for generation in _GENERATIONS:
        text = cached_generation(label=generation.label)
        assert len(text.splitlines()) == generation.lines, generation.label


def test_a_missing_artifact_fails_loudly_rather_than_skipping():
    """Deleting a vendored generation must redden, not quietly reduce coverage.

    The no-skip leg. If this ever became a skip, the only fixture covering the
    stale-cache axis would vanish while still reporting success.
    """
    absent = _Generation(
        label="absent",
        path="tests/prompts/fixtures/no-such-cached-prose.md",
        md5="0" * 32,
        lines=0,
        cache_refs=0,
        versions="none",
        commit="0" * 40,
    )
    _BY_LABEL[absent.label] = absent
    try:
        with pytest.raises(AssertionError, match="missing") as raised:
            cached_generation(label=absent.label)
    finally:
        del _BY_LABEL[absent.label]
    # The message must name the path AND how to restore it: a HALT with no
    # remedy is this epic's family-3 defect, and a fixture that fails without
    # saying how to repair it invites deletion instead.
    assert absent.path in str(raised.value)
    assert "git show" in str(raised.value)


def test_the_frozen_generation_is_red_on_the_contract_floor():
    """RED AGAINST A STALE-CACHE GENERATION — the clause `overseer-d4t` insisted on.

    Nine of the eleven cache refs on this host still hold exactly these bytes,
    spanning six released versions. This is not a synthetic charter that
    resembles a stale one; it is the artifact.
    """
    failures = _contract_failures(text=cached_generation(label="frozen"))
    assert len(failures) == 31, failures
    # Named rather than counted alone: a bare count goes stale the moment the
    # contract grows, and would then be "fixed" by editing the number.
    assert "supervisor-state-location" in failures
    assert "watcher-wait-channel-bootstrap" in failures
    assert "executable-live-supervisor-precondition" in failures


def test_the_frozen_generation_carries_the_defects_that_reddened_master():
    """The same generation, through the other shipped gate.

    Classes (a)-(d) are what `d49acc620`'s emitted charter carried when it turned
    master red — bare targets, an unguarded `readlink -f`, history-fed capture and
    an empty watcher seed. Both gates agreeing is the point: this artifact is
    unambiguously defective, and it is what nine cache refs still hold.
    """
    assert _defect_classes(text=cached_generation(label="frozen")) == {"a", "b", "c", "d"}


def test_the_stale_generation_is_invisible_to_the_contract_floor():
    """THE FINDING, and the reason a content gate cannot close this item.

    The 0.14.0 generation is stale — its bytes differ from the prose this repo
    ships — and today's contract floor, the most evolved one this repo has,
    reports it as fully conformant. Its verdict is IDENTICAL to the current
    generation's, so the floor cannot rank the two at all.
    """
    stale = cached_generation(label="stale")
    current = cached_generation(label="current")
    assert stale != current
    assert _contract_failures(text=stale) == []
    assert _contract_failures(text=stale) == _contract_failures(text=current)


def test_only_detectors_written_after_it_can_see_the_stale_generation():
    """...and every detector that existed when it shipped is blind to it.

    A content gate recognises only the staleness it already has a detector for,
    so it is always one release behind. Asserted as a set intersection rather
    than left as a claim about commit dates: NO class that predated this
    artifact fires on it, and the three that do were all written afterwards.
    """
    classes = _defect_classes(text=cached_generation(label="stale"))
    assert classes & _CLASSES_PREDATING_THE_STALE_GENERATION == frozenset()
    assert classes == {"h", "i", "j"}


def test_the_current_generation_is_clean_on_both_gates():
    """THE POSITIVE CONTROL. Without it, three reds prove only that reds happen.

    The current cache ref is byte-identical to the working tree's prose, so the
    release-to-adopter chain demonstrably works; what is missing is detection,
    not delivery. This is also why the current row is not vendored — the live
    file IS the artifact.
    """
    current = cached_generation(label="current")
    assert _contract_failures(text=current) == []
    assert _defect_classes(text=current) == set()


def test_the_three_generations_are_distinct_artifacts():
    """Guards the whole module against silently collapsing to one input.

    If two rows ever resolved to the same bytes the reds and the green above
    would still pass individually while comparing an artifact with itself.
    """
    digests = {
        hashlib.md5(cached_generation(label=g.label).encode(), usedforsecurity=False).hexdigest()
        for g in _GENERATIONS
    }
    assert len(digests) == 3
