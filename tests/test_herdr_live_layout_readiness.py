"""Regressions for the native Herdr live-layout fixture's readiness ordering."""

from __future__ import annotations

import ast
import shlex
from pathlib import Path

import pytest
import test_herdr_live_layout as live_layout
from test_herdr_live_observations import (
    TRANSIENT_NAME,
    ChildObservation,
    PaneReadiness,
    ReadyShellGate,
    startup_transient,
)

__all__: list[str] = []

LAYOUT_PATH = Path(__file__).with_name("test_herdr_live_layout.py")
CREATED_PANE = "w-load:p-created"


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


def test_an_unestablished_transient_fails_as_the_named_live_layout_fixture() -> None:
    """A setup expiry is never rendered as a layout or process-identity failure."""
    readiness = PaneReadiness(socket_path="unused", transient="controlled transient")
    readiness.panes.append(CREATED_PANE)
    gate = ReadyShellGate(
        inner=None,
        socket_path="unused",
        startup_transient="controlled transient",
        transient_name=TRANSIENT_NAME,
    )
    gate.gated.append(CREATED_PANE)
    gate.transient = ChildObservation(
        pid=None,
        reason=f"no {TRANSIENT_NAME!r} child was observed within 30.0s",
    )
    readiness.gate = gate

    with pytest.raises(AssertionError) as raised:
        _ = live_layout._established(readiness=readiness, pane_id=CREATED_PANE)

    message = str(raised.value)
    assert "native Herdr live-layout fixture" in message, message
    assert "readiness" in message and CREATED_PANE in message, message
    assert "controlled startup transient was never observed" in message, message
    assert "unrelated pane moved" not in message, message
    assert "shell must not be replaced" not in message, message
