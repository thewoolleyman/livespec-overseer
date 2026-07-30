"""Tests for the Codex plugin's cached launcher payload."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = ROOT / ".claude-plugin"
CODEX_PLUGIN_ROOT = PLUGIN_ROOT / ".codex-plugin"
PLUGIN_BIN = PLUGIN_ROOT / "bin"
PLUGIN_PACKAGE = PLUGIN_ROOT / "overseer"
SOURCE_PACKAGE = ROOT / "overseer"
PROSE = PLUGIN_ROOT / "prose" / "overseer.md"
CODEX_BINDING = CODEX_PLUGIN_ROOT / "skills" / "overseer" / "SKILL.md"


def test_codex_plugin_root_ships_runnable_overseer_launchers():
    start = PLUGIN_BIN / "overseer-start"
    daemon = PLUGIN_BIN / "overseerd"
    runtime_modules = sorted(
        path.name
        for path in SOURCE_PACKAGE.iterdir()
        if (
            (path.suffix == ".py" or path.name == "version.json")
            and not path.name.startswith("test_")
            and path.name != "conftest.py"
        )
    )

    assert start.is_file()
    assert daemon.is_file()
    assert "overseer.start" in start.read_text(encoding="utf-8")
    assert "overseer.daemon" in daemon.read_text(encoding="utf-8")
    plugin_modules = sorted(path.name for path in PLUGIN_PACKAGE.iterdir() if path.is_file())
    assert plugin_modules == runtime_modules

    prose = PROSE.read_text(encoding="utf-8")
    codex_binding = CODEX_BINDING.read_text(encoding="utf-8")
    assert "$PLUGIN_ROOT/bin/overseer-start" in prose
    assert "$PLUGIN_ROOT/../overseer/overseer-start" not in prose
    assert "Read `$PLUGIN_ROOT/prose/overseer.md`" in codex_binding
