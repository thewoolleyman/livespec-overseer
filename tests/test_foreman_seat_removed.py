"""Guard that the foreman seat is gone and only its bucket-1 residue remains.

The foreman operator seat was retired by SPECIFICATION v047 (maintainer ruling
2026-09-06, console plan decision D5 bucket 2). The cut is by CONSUMER, not by
name prefix: three ``foreman``-named modules keep live bucket-1 consumers and
therefore STAY, while every module the foreman skill alone reached goes. This
test pins both halves, so a later change cannot quietly reintroduce the seat and
cannot quietly delete the residue the daemon and the caam loop still import.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "overseer"
PLUGIN = ROOT / ".claude-plugin"
CARRIER = PLUGIN / "overseer"

# The three name-matched modules with live bucket-1 consumers, measured
# 2026-09-06: jsonio reaches _foreman_vendor_path; _registry_epic, ledger_comments
# and the grooming seat reach foreman_gather_sources; the caam-anthropic-loop
# reaches caam_foreman_override.
KEPT_MODULES = (
    "_foreman_vendor_path.py",
    "caam_foreman_override.py",
    "foreman_gather_sources.py",
)

# Surfaces the foreman seat owned outright.
REMOVED_PATHS = (
    PLUGIN / "prose" / "foreman.md",
    PLUGIN / "skills" / "foreman",
    PLUGIN / ".codex-plugin" / "skills" / "foreman",
    PLUGIN / ".pi-plugin" / "skills" / "livespec-overseer-foreman",
)

MANIFESTS = (
    PLUGIN / "plugin.json",
    PLUGIN / ".codex-plugin" / "plugin.json",
    PLUGIN / "marketplace.json",
)


def _foreman_named(*, directory: Path) -> set[str]:
    """The foreman-named PRODUCT modules in ``directory``, beside-tests excluded.

    The two assertions below compare the source package against its plugin mirror on
    one shared expectation, and the mirror carries no ``test_*`` by construction
    (`tests/test_plugin_carrier_lockstep.py` excludes them). Counting a beside-test as
    a survivor would therefore make the two sides unequal by construction the moment
    anyone tests one of the kept modules — a name-prefix accident, which is the exact
    thing this cut was made by CONSUMER rather than by name to avoid.
    """
    return {
        path.name
        for path in directory.glob("*.py")
        if "foreman" in path.name.lower() and not path.name.startswith("test_")
    }


def test_only_the_bucket_one_foreman_named_modules_survive() -> None:
    assert _foreman_named(directory=PACKAGE) == set(KEPT_MODULES)
    assert _foreman_named(directory=CARRIER) == set(KEPT_MODULES)


def test_the_kept_modules_are_still_reached_by_their_bucket_one_consumers() -> None:
    assert "_foreman_vendor_path" in (PACKAGE / "jsonio.py").read_text(encoding="utf-8")
    assert "foreman_gather_sources" in (PACKAGE / "_registry_epic.py").read_text(encoding="utf-8")
    assert "caam_foreman_override" in (PACKAGE / "caam_session_models.py").read_text(
        encoding="utf-8"
    )


def test_the_foreman_skill_surfaces_are_deleted() -> None:
    assert [path for path in REMOVED_PATHS if path.exists()] == []


def test_no_foreman_launcher_or_console_script_remains() -> None:
    launchers = sorted(
        path.name
        for directory in (PACKAGE, PLUGIN / "bin")
        for path in directory.iterdir()
        if path.is_file() and path.suffix == "" and "foreman" in path.name.lower()
    )
    assert launchers == []
    # `tomllib` is stdlib only from 3.11 and this project supports 3.10.16, so the
    # one table this test needs is read directly, as the console-entrypoint suite does.
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = re.search(r"^\[project\.scripts\]\s*$(.*?)(?=^\[)", text, re.MULTILINE | re.DOTALL)
    assert section is not None, "pyproject.toml has no [project.scripts] table"
    assert [line for line in section.group(1).splitlines() if "foreman" in line] == []


def test_no_manifest_advertises_a_foreman_operation() -> None:
    offenders = [
        manifest.name
        for manifest in MANIFESTS
        if "foreman" in json.dumps(json.loads(manifest.read_text(encoding="utf-8"))).lower()
    ]
    assert offenders == []


def test_the_registry_exposes_no_foreman_seat() -> None:
    registry_source = (PACKAGE / "registry.py").read_text(encoding="utf-8")
    assert "ForemanSeat" not in registry_source
    assert "foreman_self_restart" not in registry_source
