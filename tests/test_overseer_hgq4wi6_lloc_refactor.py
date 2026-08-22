"""Acceptance coverage for overseer-hgq4wi.6 beside-test LLOC refactor."""

from __future__ import annotations

import ast
import tokenize
from io import BytesIO
from pathlib import Path

__all__: list[str] = []


SCOPED_FILES = (
    "overseer/test_supervisor_codex_restart_safety.py",
    "overseer/test_supervisor_liveness_starvation.py",
    "overseer/test_supervisor_row_color_operator.py",
    "overseer/test_supervisor_fail_soft_marker.py",
    "overseer/test_supervisor_builders.py",
    "overseer/test_supervisor_warned_stamp_written.py",
    "overseer/test_supervisor_archive_gc.py",
    "overseer/test_foreman_session_classifier.py",
)


def docstring_lines(*, source: str) -> set[int]:
    tree = ast.parse(source)
    out: set[int] = set()
    holders = [tree, *(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))]
    for holder in holders:
        body = holder.body
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            assert first.end_lineno is not None
            out.update(range(first.lineno, first.end_lineno + 1))
    return out


def logical_line_count(*, source: str) -> int:
    docstrings = docstring_lines(source=source)
    code_lines: set[int] = set()
    tokens = tokenize.tokenize(BytesIO(source.encode("utf-8")).readline)
    for token in tokens:
        if token.type in {
            tokenize.ENCODING,
            tokenize.ENDMARKER,
            tokenize.NEWLINE,
            tokenize.NL,
            tokenize.COMMENT,
            tokenize.INDENT,
            tokenize.DEDENT,
        }:
            continue
        if token.start[0] not in docstrings:
            code_lines.add(token.start[0])
    return len(code_lines)


def test_hgq4wi6_scoped_beside_tests_keep_refactor_margin():
    root = Path(__file__).resolve().parents[1]

    measured = {
        path: logical_line_count(source=(root / path).read_text(encoding="utf-8"))
        for path in SCOPED_FILES
    }

    assert measured == {
        "overseer/test_supervisor_codex_restart_safety.py": 127,
        "overseer/test_supervisor_liveness_starvation.py": 119,
        "overseer/test_supervisor_row_color_operator.py": 137,
        "overseer/test_supervisor_fail_soft_marker.py": 143,
        "overseer/test_supervisor_builders.py": 102,
        "overseer/test_supervisor_warned_stamp_written.py": 153,
        "overseer/test_supervisor_archive_gc.py": 86,
        "overseer/test_foreman_session_classifier.py": 37,
    }
    assert all(count <= 180 for count in measured.values())


def test_hgq4wi6_owner_markers_are_removed_from_scoped_files():
    root = Path(__file__).resolve().parents[1]

    for path in SCOPED_FILES:
        source = (root / path).read_text(encoding="utf-8")
        assert "livespec-lloc-soft-band-owner: overseer-hgq4wi.6" not in source
