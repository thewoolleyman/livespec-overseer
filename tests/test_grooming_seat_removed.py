"""Guard that the grooming seat is gone and its one live consumer kept its check.

The grooming operator seat was retired by SPECIFICATION v047 (maintainer ruling
2026-09-06, console plan decision D5 bucket 2), the sibling cut to the foreman
seat pinned by ``tests/test_foreman_seat_removed.py``. The cut is by CONSUMER,
not by name prefix — and here the two rules disagree about exactly one module.
``grooming_conformance_plan_anchors`` was grooming-named but its live consumer is
``scripts/check-plan-anchor-metadata.py``, a gate inside the ``just check``
aggregate that has nothing to do with the drain pass. Deleting it would have
disarmed that gate; keeping it would have left a grooming module behind. So the
plan-anchor check MOVED to ``plan_anchor_metadata``, carrying the two names it
needed from its former siblings, and every other grooming module went.

This test pins both halves, so a later change cannot quietly reintroduce the seat
and cannot quietly re-orphan the check that outlived it.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "overseer"
PLUGIN = ROOT / ".claude-plugin"
CARRIER = PLUGIN / "overseer"

# Surfaces the grooming seat owned outright.
REMOVED_PATHS = (
    PLUGIN / "prose" / "grooming.md",
    PLUGIN / "skills" / "grooming",
    PLUGIN / ".codex-plugin" / "skills" / "grooming",
    PLUGIN / ".pi-plugin" / "skills" / "livespec-overseer-grooming",
)

MANIFESTS = (
    PLUGIN / "plugin.json",
    PLUGIN / ".codex-plugin" / "plugin.json",
    PLUGIN / "marketplace.json",
)


def _grooming_named(*, directory: Path) -> set[str]:
    """The grooming-named PRODUCT modules in ``directory``, beside-tests excluded.

    Mirrors the foreman guard's helper for the same reason: the carrier package
    carries no ``test_*`` by construction (`tests/test_plugin_carrier_lockstep.py`
    excludes them), so counting a beside-test would make the two sides unequal by
    construction rather than by fact.
    """
    return {
        path.name
        for path in directory.glob("*.py")
        if "grooming" in path.name.lower() and not path.name.startswith("test_")
    }


def test_no_grooming_named_module_survives_in_either_package() -> None:
    assert _grooming_named(directory=PACKAGE) == set()
    assert _grooming_named(directory=CARRIER) == set()


def test_the_grooming_skill_surfaces_are_deleted() -> None:
    assert [path for path in REMOVED_PATHS if path.exists()] == []


def test_no_manifest_advertises_a_grooming_operation() -> None:
    offenders = [
        manifest.name
        for manifest in MANIFESTS
        if "grooming" in json.dumps(json.loads(manifest.read_text(encoding="utf-8"))).lower()
    ]
    assert offenders == []


def test_the_registry_exposes_no_grooming_seat() -> None:
    registry_source = (PACKAGE / "registry.py").read_text(encoding="utf-8")
    assert "GroomingSeat" not in registry_source
    assert "grooming" not in registry_source.lower()


def test_signals_exposes_no_grooming_topic_helper() -> None:
    signals_source = (PACKAGE / "signals.py").read_text(encoding="utf-8")
    assert "grooming" not in signals_source.lower()


def test_the_plan_anchor_check_moved_to_a_non_grooming_module() -> None:
    """The one module the by-consumer rule kept, under a name the cut allows.

    The module import is deliberately INSIDE the test body: at Red the file does
    not exist yet, so the path assertion below fails as a genuine assertion rather
    than dying at collection with a ModuleNotFoundError.
    """
    module_path = PACKAGE / "plan_anchor_metadata.py"
    assert module_path.is_file()

    module = importlib.import_module("plan_anchor_metadata")

    assert module.plan_anchor_metadata_check is not None
    assert module.InvariantCheck is not None
    assert frozenset({"closed", "done"}) == module.TERMINAL_WORK_ITEM_STATUSES


def test_the_plan_anchor_gate_reaches_the_relocated_module() -> None:
    script = (ROOT / "scripts" / "check-plan-anchor-metadata.py").read_text(encoding="utf-8")
    assert "from plan_anchor_metadata import plan_anchor_metadata_check" in script
    assert "grooming" not in script.lower()
