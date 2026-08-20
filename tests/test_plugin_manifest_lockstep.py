"""Lockstep gates for the Claude and nested Codex plugin manifests."""

from __future__ import annotations

import json
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = ROOT / ".claude-plugin"
CODEX_PLUGIN_ROOT = PLUGIN_ROOT / ".codex-plugin"


def test_nested_codex_manifest_stays_in_lockstep_with_claude_manifest():
    claude = json.loads((PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8"))
    codex = json.loads((CODEX_PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8"))

    mirrored_fields = ("name", "version", "description")
    drifted = {
        field: {"claude": claude[field], "codex": codex[field]}
        for field in mirrored_fields
        if claude[field] != codex[field]
    }

    assert drifted == {}, (
        "nested Codex manifest drifted from its Claude sibling on lockstep fields: " f"{drifted}"
    )
    assert codex["skills"] == "./.codex-plugin/skills/"


def test_release_please_bumps_both_plugin_manifest_versions():
    config = json.loads((ROOT / "release-please-config.json").read_text(encoding="utf-8"))

    version_targets = {
        entry.get("path")
        for package in config.get("packages", {}).values()
        for entry in package.get("extra-files", [])
        if isinstance(entry, dict)
        and entry.get("type") == "json"
        and entry.get("jsonpath") == "$.version"
    }

    assert {
        ".claude-plugin/plugin.json",
        ".claude-plugin/.codex-plugin/plugin.json",
    } <= version_targets


def _marketplace_description_drift(*, manifest: dict, marketplace: dict) -> dict:
    """Return the drift between a manifest description and its marketplace entry.

    Extracted so the real-file gate and its discriminating control exercise the
    SAME comparison. A control that re-implements the check, or that merely
    compares two literals, proves nothing about the code that runs in CI.
    """
    entries = [e for e in marketplace["plugins"] if e.get("name") == manifest["name"]]
    if len(entries) != 1:
        return {"entries_named": len(entries)}
    if entries[0]["description"] != manifest["description"]:
        return {
            "marketplace": entries[0]["description"],
            "manifest": manifest["description"],
        }
    return {}


def test_marketplace_description_stays_in_lockstep_with_both_manifests():
    """The plugin description lives in THREE artifacts, not two.

    `overseer-mr2f2k`. The two `plugin.json` files are gated above, but the
    marketplace entry carries a byte-identical copy of the same description and
    was gated by nothing: measured 2026-08-20, all three were identical while no
    test anywhere read the marketplace file. Adding a fourth operation therefore
    updated two of three artifacts and left the marketplace still advertising
    three, with a fully green suite.
    """
    claude = json.loads((PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads((PLUGIN_ROOT / "marketplace.json").read_text(encoding="utf-8"))

    drift = _marketplace_description_drift(manifest=claude, marketplace=marketplace)

    assert drift == {}, f"marketplace description drifted from the Claude manifest: {drift}"


def test_marketplace_gate_reports_a_marketplace_only_drift():
    """DISCRIMINATING CONTROL: the gate must FAIL on a marketplace-only edit.

    A gate that only ever sees agreeing strings cannot distinguish "correct"
    from "not looking". This drives the same helper the gate above uses with a
    marketplace entry whose description alone was changed -- the exact shape
    that shipped undetected before -- and asserts the drift is reported.
    """
    manifest = {"name": "livespec-overseer", "description": "Exposes a, b, c and d."}
    stale_marketplace = {
        "plugins": [{"name": "livespec-overseer", "description": "Exposes a, b and c."}]
    }

    drift = _marketplace_description_drift(manifest=manifest, marketplace=stale_marketplace)

    assert drift != {}, "gate failed to report a marketplace-only description drift"
    assert drift["manifest"] == "Exposes a, b, c and d."
    assert drift["marketplace"] == "Exposes a, b and c."


def test_marketplace_gate_reports_a_missing_or_duplicated_entry():
    """Second control leg: a name that resolves to no entry is drift, not a pass."""
    manifest = {"name": "livespec-overseer", "description": "Exposes a."}

    assert _marketplace_description_drift(manifest=manifest, marketplace={"plugins": []}) == {
        "entries_named": 0
    }
