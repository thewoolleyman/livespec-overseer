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
