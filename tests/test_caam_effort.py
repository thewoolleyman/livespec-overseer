"""Tests for caam settings effort re-assertion."""

from __future__ import annotations

import importlib
import json
import stat
from pathlib import Path
from types import ModuleType

__all__: list[str] = []


def caam_effort_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_effort.py"
    assert module_path.is_file()
    return importlib.import_module("caam_effort")


def caam_enforcement_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_enforcement.py"
    assert module_path.is_file()
    return importlib.import_module("caam_enforcement")


def write_settings(*, path: Path, effort: str) -> dict[str, object]:
    settings = {
        "hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "h"}]}]},
        "env": {"ANTHROPIC_MODEL": "claude-opus-5"},
        "plugins": {"livespec-overseer": {"enabled": True}},
        "mcpServers": {"box": {"command": "box-mcp", "args": ["--stdio"]}},
        "integrations": {"terminal": {"enabled": False}},
        "effortLevel": effort,
        "model": "claude-fable-5[1m]",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    path.chmod(0o644)
    return settings


def read_json(*, path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_effort_floor_raises_low_and_medium_but_leaves_higher_setting(*, tmp_path: Path):
    module = caam_effort_module()

    low = tmp_path / "low.json"
    medium = tmp_path / "medium.json"
    higher = tmp_path / "higher.json"
    write_settings(path=low, effort="low")
    write_settings(path=medium, effort="medium")
    write_settings(path=higher, effort="xhigh")

    assert module.enforce_effort_floor(settings_path=low) == [
        "effort: settings.json effortLevel 'low' -> 'high' "
        "(raised to the floor; a switch had reset it)"
    ]
    assert read_json(path=low)["effortLevel"] == "high"

    assert module.enforce_effort_floor(settings_path=medium) == [
        "effort: settings.json effortLevel 'medium' -> 'high' "
        "(raised to the floor; a switch had reset it)"
    ]
    assert read_json(path=medium)["effortLevel"] == "high"

    assert module.enforce_effort_floor(settings_path=higher) == []
    assert read_json(path=higher)["effortLevel"] == "xhigh"


def test_effort_rewrite_preserves_other_settings_and_writes_mode_0600(*, tmp_path: Path):
    module = caam_effort_module()
    settings_path = tmp_path / "settings.json"
    before = write_settings(path=settings_path, effort="low")

    module.enforce_effort_floor(settings_path=settings_path)

    after = read_json(path=settings_path)
    assert after["effortLevel"] == "high"
    for key in ("hooks", "env", "plugins", "mcpServers", "integrations", "model"):
        assert after[key] == before[key]
    assert stat.S_IMODE(settings_path.stat().st_mode) == 0o600


def test_effort_enforcement_is_silent_safe_for_unreadable_or_unparseable_settings(
    *, tmp_path: Path
):
    module = caam_effort_module()
    unparseable = tmp_path / "broken.json"
    unparseable.write_text("{", encoding="utf-8")
    directory = tmp_path / "settings-dir"
    directory.mkdir()

    assert module.enforce_effort_floor(settings_path=unparseable) == []
    assert unparseable.read_text(encoding="utf-8") == "{"
    assert module.enforce_effort_floor(settings_path=directory) == []


def test_blank_effort_configuration_disables_the_write(*, tmp_path: Path, monkeypatch):
    module = caam_effort_module()
    settings_path = tmp_path / "settings.json"
    write_settings(path=settings_path, effort="low")
    monkeypatch.setenv("CAAM_ROTATE_EFFORT", "")

    assert module.enforce_effort_floor(settings_path=settings_path) == []
    assert read_json(path=settings_path)["effortLevel"] == "low"


def test_unknown_and_absent_effort_values_are_raised_to_the_floor(*, tmp_path: Path):
    module = caam_effort_module()
    unknown_path = tmp_path / "unknown.json"
    absent_path = tmp_path / "absent.json"
    write_settings(path=unknown_path, effort="turbo")
    write_settings(path=absent_path, effort="low")
    absent = read_json(path=absent_path)
    del absent["effortLevel"]
    absent_path.write_text(json.dumps(absent, indent=2), encoding="utf-8")

    assert module.enforce_effort_floor(settings_path=unknown_path) == [
        "effort: settings.json effortLevel 'turbo' -> 'high' "
        "(raised to the floor; a switch had reset it)"
    ]
    assert read_json(path=unknown_path)["effortLevel"] == "high"

    assert module.enforce_effort_floor(settings_path=absent_path) == [
        "effort: settings.json effortLevel None -> 'high' "
        "(raised to the floor; a switch had reset it)"
    ]
    assert read_json(path=absent_path)["effortLevel"] == "high"


def test_write_oserror_returns_without_raising(*, tmp_path: Path, monkeypatch):
    module = caam_effort_module()
    settings_path = tmp_path / "settings.json"
    write_settings(path=settings_path, effort="low")

    def fail_replace(*, self: Path, target: Path) -> Path:
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_replace)

    assert module.enforce_effort_floor(settings_path=settings_path) == []


def test_effort_runs_before_no_models_returns(*, tmp_path: Path):
    module = caam_enforcement_module()
    settings_path = tmp_path / "settings.json"
    write_settings(path=settings_path, effort="low")

    result = module.enforce_models(settings_path=settings_path, no_models=True)

    assert result == [
        "effort: settings.json effortLevel 'low' -> 'high' "
        "(raised to the floor; a switch had reset it)"
    ]
    assert read_json(path=settings_path)["effortLevel"] == "high"


def test_effort_runs_when_model_enforcement_is_enabled(*, tmp_path: Path):
    module = caam_enforcement_module()
    settings_path = tmp_path / "settings.json"
    write_settings(path=settings_path, effort="low")

    result = module.enforce_models(settings_path=settings_path, no_models=False)

    assert result == [
        "effort: settings.json effortLevel 'low' -> 'high' "
        "(raised to the floor; a switch had reset it)"
    ]
    assert read_json(path=settings_path)["effortLevel"] == "high"
