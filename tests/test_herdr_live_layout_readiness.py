"""Regressions for the native Herdr live-layout fixture's readiness ordering."""

from __future__ import annotations

import ast
import shlex
from pathlib import Path

from test_herdr_live_observations import TRANSIENT_NAME, startup_transient

__all__: list[str] = []

LAYOUT_PATH = Path(__file__).with_name("test_herdr_live_layout.py")


def test_the_unrelated_pane_exercise_establishes_its_transient_before_grading(
    *, tmp_path: Path
) -> None:
    """Load cannot strand the controlled child under a pre-readiness process name.

    The first executable Herdr starts must already carry the controlled name at
    the kernel exec boundary. Renaming from Python code leaves a scheduling gap
    in which a loaded host truthfully reports ``python`` instead. The exercise
    must then grade that readiness before any adapter/layout assertion.
    """
    command = startup_transient(scratch=tmp_path)
    executable = Path(shlex.split(command)[0])

    assert executable.name == TRANSIENT_NAME, (
        f"the startup transient first execs {executable.name!r}, leaving a load-sensitive "
        f"gap before it becomes {TRANSIENT_NAME!r}"
    )

    tree = ast.parse(LAYOUT_PATH.read_text(encoding="utf-8"), filename=str(LAYOUT_PATH))
    exercise = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "test_an_unrelated_pane_is_left_exactly_where_it_was"
    )
    readiness_line = next(
        node.lineno
        for node in ast.walk(exercise)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_established"
    )
    first_grade_line = min(
        node.lineno for node in ast.walk(exercise) if isinstance(node, ast.Assert)
    )

    assert readiness_line < first_grade_line, (
        f"readiness is graded on line {readiness_line}, after the first layout/outcome "
        f"assertion on line {first_grade_line}"
    )
