"""The two caam decision modules at the LLOC ceiling decompose along their own seams.

`caam_anthropic_pass` and `caam_anthropic_decide` both sit one or two logical
lines under the 250-LLOC hard ceiling, so the refusal trigger cannot be wired
into either until each gives up a concern that is not its own. The two concerns
moved here are the ones whose callers are entirely internal: the account table a
pass renders, and the per-trigger choice of a destination. What stays behind is
what each module is named for -- orchestrating one pass, and deciding then
executing one switch.
"""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "overseer"


def test_the_account_table_a_pass_renders_moves_into_its_own_module() -> None:
    module_path = PACKAGE / "caam_pass_table.py"

    assert module_path.is_file(), "the pass table render belongs in overseer/caam_pass_table.py"

    module = importlib.import_module("caam_pass_table")

    assert sorted(module.__all__) == ["emit_pass_table", "pass_table_lines"]
    source = (PACKAGE / "caam_anthropic_pass.py").read_text(encoding="utf-8")
    assert "def _emit_table" not in source
    assert "def _table_lines" not in source
    assert "from caam_pass_table import" in source


def test_the_per_trigger_choice_of_a_destination_moves_out_of_the_decision() -> None:
    module_path = PACKAGE / "caam_decide_rotation.py"

    assert (
        module_path.is_file()
    ), "the per-trigger choice belongs in overseer/caam_decide_rotation.py"

    module = importlib.import_module("caam_decide_rotation")

    assert sorted(module.__all__) == ["RotationChoice", "RotationRequest", "rotation_choice"]
    source = (PACKAGE / "caam_anthropic_decide.py").read_text(encoding="utf-8")
    assert "drain_target" not in source
    assert "eligible_profiles" not in source
    assert "from caam_decide_rotation import" in source
