"""Guard that this repo ships EXACTLY the three operator skills, in every harness.

The three ``test_*_seat_removed.py`` guards each pin the NEGATIVE for one
retired seat: no ``foreman``/``grooming``/``supervise-plan`` surface survives.
That is necessary but not sufficient — three name-specific absences say nothing
about a fourth seat reappearing, and nothing at all about the surfaces that
are supposed to REMAIN. After the bucket-2 trim (console plan decision D5,
maintainer ruling 2026-09-06) livespec-overseer was the two-pane overseer daemon
plus the caam-anthropic-loop and nothing else, so the shipped surface became a
closed set worth asserting POSITIVELY.

D5's COUNT was deliberately reopened on 2026-09-09 (maintainer request,
`overseer-f4664u`): ``drain-backlog`` moved out of the repo-local
``.claude/skills/`` tree and INTO this plugin as a third first-class operation,
``/livespec-overseer:drain-backlog``. That reversal is recorded here rather than
smuggled in, because the set below is the artifact D5 was expressed as. What D5
retired — the three SEATS — is untouched by it; only the count of shipped
operations changed, and the closed-set property this test exists for is exactly
what forced the reversal to be explicit.

So this test asserts set EQUALITY, not membership, across all four shipped
trees — the Claude skills, the nested Codex bindings, the pi bindings, and the
harness-neutral prose both harnesses read — plus the manifests' own advertising
text. A new seat cannot be added to any one tree without this failing, which is
the property the per-seat guards cannot give.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / ".claude-plugin"

# The whole shipped operator surface: D5 bucket 1, plus the drain-backlog
# operation the maintainer moved in on 2026-09-09 (`overseer-f4664u`).
SHIPPED_SKILLS = ("caam-anthropic-loop", "drain-backlog", "overseer")

# The pi bindings namespace each skill with the plugin name.
PI_PREFIX = "livespec-overseer-"

# The seats retired by SPECIFICATION v047 and removed in releases 3.0.0, 4.0.0
# and 5.0.0. Named here so the advertising-text assertion below is explicit
# about what it is looking for rather than merely counting skills.
RETIRED_SEATS = ("foreman", "grooming", "supervise-plan")

MANIFESTS = (
    PLUGIN / "plugin.json",
    PLUGIN / ".codex-plugin" / "plugin.json",
    PLUGIN / "marketplace.json",
)


def _subdirectory_names(*, directory: Path) -> set[str]:
    return {path.name for path in directory.iterdir() if path.is_dir()}


def test_the_claude_skills_tree_ships_exactly_the_operator_skills() -> None:
    assert _subdirectory_names(directory=PLUGIN / "skills") == set(SHIPPED_SKILLS)


def test_the_codex_skills_tree_ships_exactly_the_operator_skills() -> None:
    """The Codex surface is NESTED inside `.claude-plugin/`, and stays in lockstep."""
    codex_skills = PLUGIN / ".codex-plugin" / "skills"
    assert _subdirectory_names(directory=codex_skills) == set(SHIPPED_SKILLS)


def test_the_pi_skills_tree_ships_exactly_the_operator_skills() -> None:
    pi_skills = PLUGIN / ".pi-plugin" / "skills"
    expected = {f"{PI_PREFIX}{skill}" for skill in SHIPPED_SKILLS}
    assert _subdirectory_names(directory=pi_skills) == expected


def test_the_harness_neutral_prose_covers_exactly_the_operator_skills() -> None:
    """Both harnesses read the same `prose/`, so a stale body would ship twice."""
    prose = {path.stem for path in (PLUGIN / "prose").glob("*.md")}
    assert prose == set(SHIPPED_SKILLS)


def test_every_skill_carries_a_binding_in_all_three_harnesses() -> None:
    """Set equality per tree still permits a directory with no SKILL.md in it."""
    missing: list[str] = []
    for skill in SHIPPED_SKILLS:
        bindings = (
            PLUGIN / "skills" / skill / "SKILL.md",
            PLUGIN / ".codex-plugin" / "skills" / skill / "SKILL.md",
            PLUGIN / ".pi-plugin" / "skills" / f"{PI_PREFIX}{skill}" / "SKILL.md",
        )
        missing.extend(str(path.relative_to(ROOT)) for path in bindings if not path.is_file())
    assert missing == []


def test_no_manifest_advertises_a_retired_seat() -> None:
    """The manifests' DESCRIPTION text is the shipped claim, not just their keys."""
    offenders = [
        f"{manifest.name}:{seat}"
        for manifest in MANIFESTS
        for seat in RETIRED_SEATS
        if seat in json.dumps(json.loads(manifest.read_text(encoding="utf-8")))
    ]
    assert offenders == []


def test_every_manifest_names_every_shipped_operation() -> None:
    """The complement of the check above: every shipped op must be advertised."""
    missing = [
        f"{manifest.name}:{skill}"
        for manifest in MANIFESTS
        for skill in SHIPPED_SKILLS
        if skill not in json.dumps(json.loads(manifest.read_text(encoding="utf-8")))
    ]
    assert missing == []
