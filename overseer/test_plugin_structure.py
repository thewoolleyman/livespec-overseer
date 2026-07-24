"""Structure tests for the installable /overseer plugin surface."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = ROOT / ".claude-plugin"
PROSE = PLUGIN_ROOT / "prose" / "overseer.md"
BINDING = PLUGIN_ROOT / "skills" / "overseer" / "SKILL.md"
LEGACY_POINTER = ROOT / "overseer" / "SKILL.md"


def test_overseer_plugin_marketplace_entry_points_at_plugin_root():
    marketplace = json.loads((PLUGIN_ROOT / "marketplace.json").read_text(encoding="utf-8"))
    plugin = json.loads((PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8"))

    assert marketplace["name"] == "livespec-overseer"
    assert marketplace["plugins"] == [
        {
            "name": "livespec-overseer",
            "source": "./.claude-plugin",
            "description": plugin["description"],
        }
    ]
    assert plugin["name"] == "livespec-overseer"


def test_overseer_skill_binding_resolves_single_source_prose():
    prose = PROSE.read_text(encoding="utf-8")
    binding = BINDING.read_text(encoding="utf-8")
    legacy_pointer = LEGACY_POINTER.read_text(encoding="utf-8")

    assert "${CLAUDE_PLUGIN_ROOT}/prose/overseer.md" in binding
    assert 'cat "${CLAUDE_PLUGIN_ROOT}/prose/overseer.md"' in binding
    assert "This binding adds NO operation behavior of its own" in binding
    assert "You are the **bottom pane** of the overseer" in prose
    assert "You are the **bottom pane** of the overseer" not in binding
    assert "You are the **bottom pane** of the overseer" not in legacy_pointer
    assert ".claude-plugin/prose/overseer.md" in legacy_pointer


def test_overseer_operator_prose_cites_slice_1_command_names():
    prose = PROSE.read_text(encoding="utf-8")

    assert "```bash\noverseer-start\n```" in prose
    assert "overseerd --warn-percent N 2> tmp/overseer/daemon.log" in prose
    assert "```bash\noverseer/overseer-start\n```" not in prose
    assert "overseer/overseerd --warn-percent" not in prose
