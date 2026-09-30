"""`llm-provider-manager` ships as a FOURTH operator surface, in every harness at once.

SPECIFICATION/contracts.md requires the operation to ship as a first-class operator
operation with one visible binding per supported harness, where supported harness is the
closed set of the Claude binding, the Codex binding and the namespaced Pi binding. Every
manifest that declares the operation must move in lockstep, so its availability and
version agree across harnesses.

WHY A DEDICATED MODULE RATHER THAN MORE LINES IN `test_shipped_skill_surface.py`. That
gate asserts SET EQUALITY over the shipped trees, which is exactly the right shape for
"no fourth seat appears unnoticed" and exactly the wrong shape for "this particular
operation is completely wired". Set equality is satisfied by a directory; it says nothing
about whether the prose exists, whether the manifests advertise the operation, or whether
the three bindings agree on which prose they read. Both properties are wanted, and they
are different questions.

The COUNT is asserted here too, and deliberately as an exact number against a named set
rather than as `len(...) >= 4`. The acceptance condition this module was written for is
that the invariant moves from three to four IN THE COMMIT THAT SHIPS the operation --
which is a statement about a closed set changing by one known member, not about a
directory listing growing.

`package.json` is checked for the Pi ADVERTISEMENT but never for a version. The contract
is explicit that its package version is not an operation version and is excluded from
manifest lockstep: Pi operation availability derives from the namespaced binding's
existence plus the outer plugin manifest, so asserting a version here would invent a
fourth lockstep participant the contract does not have.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / ".claude-plugin"

OPERATION = "llm-provider-manager"

# The three surfaces that predate this one. Named so the four-surface assertion below
# says which member joined, rather than merely that the count grew.
PRECEDING_OPERATIONS = ("caam-anthropic-loop", "drain-backlog", "overseer")
EXPECTED_OPERATIONS = (*PRECEDING_OPERATIONS, OPERATION)

# The contract's closed "manifest that declares the operation" set: exactly the outer
# manifest and the nested Codex one. `marketplace.json` carries the same description and
# is gated by `test_plugin_manifest_lockstep.py`; it declares no skills of its own.
DECLARING_MANIFESTS = (
    PLUGIN / "plugin.json",
    PLUGIN / ".codex-plugin" / "plugin.json",
)

LOCKSTEP_FIELDS = ("name", "version", "description")


def _binding_paths(*, operation: str) -> dict[str, Path]:
    return {
        "claude": PLUGIN / "skills" / operation / "SKILL.md",
        "codex": PLUGIN / ".codex-plugin" / "skills" / operation / "SKILL.md",
        "pi": PLUGIN / ".pi-plugin" / "skills" / f"livespec-overseer-{operation}" / "SKILL.md",
    }


def _manifest(*, path: Path) -> dict[str, object]:
    parsed: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return parsed


def test_the_manager_ships_one_prose_contract_and_one_binding_per_supported_harness() -> None:
    prose = PLUGIN / "prose" / f"{OPERATION}.md"
    assert prose.is_file(), f"the one harness-neutral operator contract must exist: {prose}"

    missing = [
        f"{harness}:{path.relative_to(ROOT)}"
        for harness, path in _binding_paths(operation=OPERATION).items()
        if not path.is_file()
    ]
    assert missing == [], f"these harness bindings are missing: {missing}"


def test_every_binding_reads_the_one_shared_prose_contract() -> None:
    """One contract, three readers -- not three contracts that happen to agree today."""
    silent = [
        harness
        for harness, path in _binding_paths(operation=OPERATION).items()
        if f"prose/{OPERATION}.md" not in path.read_text(encoding="utf-8")
    ]
    assert silent == [], f"these bindings do not read the shared prose contract: {silent}"


def test_every_manifest_declaring_the_manager_names_it_and_moves_in_lockstep() -> None:
    manifests = {path.name: _manifest(path=path) for path in DECLARING_MANIFESTS}

    unadvertised = [
        name for name, manifest in manifests.items() if OPERATION not in json.dumps(manifest)
    ]
    assert unadvertised == [], f"these manifests do not declare the operation: {unadvertised}"

    outer = _manifest(path=PLUGIN / "plugin.json")
    codex = _manifest(path=PLUGIN / ".codex-plugin" / "plugin.json")
    drifted = {
        field: {"outer": outer[field], "codex": codex[field]}
        for field in LOCKSTEP_FIELDS
        if outer[field] != codex[field]
    }
    assert drifted == {}, f"the declaring manifests drifted on lockstep fields: {drifted}"


def test_the_codex_manifest_carries_the_skill_registration_data() -> None:
    """The nested manifest's `skills` value is how Codex finds the binding at all."""
    codex = _manifest(path=PLUGIN / ".codex-plugin" / "plugin.json")

    assert codex["skills"] == "./.codex-plugin/skills/"
    assert (PLUGIN / ".codex-plugin" / "skills" / OPERATION).is_dir()


def test_package_metadata_advertises_the_namespaced_pi_binding_root() -> None:
    """Pi availability derives from the namespaced binding plus this advertisement."""
    package = _manifest(path=ROOT / "package.json")
    pi = package["pi"]
    assert isinstance(pi, dict)

    assert pi["skills"] == ["./.claude-plugin/.pi-plugin/skills"]
    assert _binding_paths(operation=OPERATION)["pi"].parent.name == (
        f"livespec-overseer-{OPERATION}"
    )


def test_the_shipped_surface_is_exactly_four_operations_including_the_original_three() -> None:
    """The invariant moves three -> four by gaining ONE named member, not by growing.

    Asserted per-tree rather than once, because a surface half-added to two trees out of
    four is the shape this repository has shipped before: the manifests were updated and
    the marketplace entry was not, with a fully green suite.
    """
    trees = {
        "claude": {path.name for path in (PLUGIN / "skills").iterdir() if path.is_dir()},
        "codex": {
            path.name for path in (PLUGIN / ".codex-plugin" / "skills").iterdir() if path.is_dir()
        },
        "pi": {
            path.name.removeprefix("livespec-overseer-")
            for path in (PLUGIN / ".pi-plugin" / "skills").iterdir()
            if path.is_dir()
        },
        "prose": {path.stem for path in (PLUGIN / "prose").glob("*.md")},
    }

    for harness, shipped in trees.items():
        assert shipped == set(EXPECTED_OPERATIONS), f"{harness} tree is not the four-surface set"
        assert len(shipped) == 4, harness

    for preceding in PRECEDING_OPERATIONS:
        assert all(
            preceding in shipped for shipped in trees.values()
        ), f"the pre-existing {preceding} surface must remain installed alongside the new one"
