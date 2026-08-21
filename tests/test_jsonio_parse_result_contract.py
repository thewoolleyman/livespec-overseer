"""Contract tests for jsonio parse failure-vs-absence discrimination."""

from __future__ import annotations

import sys
from pathlib import Path

_OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
if str(_OVERSEER_DIR) not in sys.path:
    sys.path.insert(0, str(_OVERSEER_DIR))

import jsonio  # noqa: E402

__all__: list[str] = []


def _assert_success(*, result: object, expected: dict[str, object] | None) -> None:
    assert hasattr(result, "unwrap")
    assert result.unwrap() == expected


def _assert_failure(*, result: object) -> None:
    assert hasattr(result, "failure")
    error = result.failure()
    assert error.message == "malformed JSON"


def test_parse_object_discriminates_malformed_absent_and_present():
    _assert_failure(result=jsonio.parse_object(text="{oops}"))
    _assert_success(result=jsonio.parse_object(text="[1, 2, 3]"), expected=None)
    _assert_success(result=jsonio.parse_object(text='{"id": "x"}'), expected={"id": "x"})


def test_parse_object_line_discriminates_malformed_absent_and_present():
    _assert_failure(result=jsonio.parse_object_line(line="{oops}\n"))
    _assert_success(result=jsonio.parse_object_line(line="[1, 2, 3]\n"), expected=None)
    _assert_success(result=jsonio.parse_object_line(line='{"id": "x"}\n'), expected={"id": "x"})
