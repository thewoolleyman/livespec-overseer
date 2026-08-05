"""Coverage-only edge for the valve-disposition integration helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

HELPER_PATH = Path(__file__).with_name("test_foreman_valve_disposition.py")

__all__: list[str] = []


def helper_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("foreman_valve_disposition_helper", HELPER_PATH)
    assert spec is not None
    assert spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_write_config_can_leave_the_disposition_key_absent(*, tmp_path: Path):
    repo = tmp_path / "repo"

    helper_module().write_config(repo=repo, value="consensus", include_key=False)

    assert "foreman_valve_disposition" not in (repo / ".livespec.jsonc").read_text(encoding="utf-8")
