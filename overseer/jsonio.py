"""Typed JSON-object parsing for the overseer.

`json.loads` is typed as returning `Any`. Under a strict type checker that is
contagious: `isinstance(parsed, dict)` narrows only to `dict[Unknown, Unknown]`,
so every downstream `.get()` yields an unknown type and the checker can no longer
see the `isinstance` guards the call sites already perform on each field.

Funnelling every parse through this module fixes that once, at the boundary. A
JSON object's keys are strings by the grammar, so the narrowing to
`dict[str, object]` is a fact about JSON rather than a wish about this data — and
because the values come back as `object` rather than `Any`, the `isinstance`
checks at each call site become real, checked narrowings instead of decoration.

The alternative the product tree took for the same problem is a file-level
`# pyright: reportUnknown...=none` pragma on a dedicated helpers module. That is
the right call there (a pure-helper module, nothing else in it to weaken); here
the parsing is a few lines inside modules full of unrelated logic, so a
file-level pragma would silence three rules across code that should keep them.

Uses the repo-vendored ``returns`` Result rail, like the foreman source
readers that consume it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "JsonObjectParse",
    "JsonParseError",
    "as_float",
    "as_list",
    "as_object",
    "is_parse_failure",
    "parse_object",
    "parse_object_line",
]


@dataclass(frozen=True, kw_only=True)
class JsonParseError:
    """Malformed JSON diagnostic carried on the Result failure track."""

    message: str


JsonObjectParse = Result[dict[str, object] | None, JsonParseError]


def as_object(*, value: object) -> dict[str, object] | None:
    """Narrow an ALREADY-PARSED JSON value to a string-keyed mapping, or None.

    For callers that must keep their own ``try``/``except`` around the parse —
    typically because they report a malformed file and a well-formed non-object
    file with DIFFERENT diagnostics, a distinction worth more than the few lines
    it costs. They keep their error handling and gain the narrowing.

    :func:`parse_object` is the one-call form for everyone else.
    """
    if not isinstance(value, dict):
        return None
    # Safe by the JSON grammar: object keys are always strings. This is the one
    # place the folder asserts that, so no call site has to.
    return cast("dict[str, object]", value)


def as_list(*, value: object) -> list[object] | None:
    """Narrow an already-parsed JSON value to a list, or None if it is not one.

    The list sibling of :func:`as_object`, and it exists for the same reason:
    ``isinstance(value, list)`` narrows only to ``list[Unknown]``, so iterating it
    yields unknowns and the per-element ``isinstance`` checks that follow stop
    meaning anything to a type checker. Elements come back as ``object``, which
    those checks then narrow for real.
    """
    if not isinstance(value, list):
        return None
    return cast("list[object]", value)


def as_float(*, value: object) -> float | None:
    """Coerce an already-parsed JSON scalar to a float, or None if it is not numeric.

    JSON numbers arrive as ``int`` or ``float``; a legacy hand-edited value may be
    a numeric string. Anything else — an object, an array, null, a non-numeric
    string — is not a number, and every caller here treats that as "no value"
    rather than as an error worth raising.

    ``bool`` is rejected deliberately. It is an ``int`` subclass, so a bare
    ``isinstance(value, int)`` would accept ``true`` and silently yield ``1.0``
    from something that was never a number.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def is_parse_failure(*, result: JsonObjectParse) -> bool:
    """Whether a JSON object parse failed before producing a JSON value."""
    return isinstance(result, Failure)


def parse_object(*, text: str) -> JsonObjectParse:
    """Parse ``text`` as a JSON object.

    Malformed JSON returns ``Failure(JsonParseError(...))``. Well-formed JSON
    that is not an object returns ``Success(None)``. A JSON object returns
    ``Success(dict[str, object])``.
    """
    try:
        parsed: object = json.loads(text)
    except ValueError:
        return Failure(JsonParseError(message="malformed JSON"))
    return Success(as_object(value=parsed))


def parse_object_line(*, line: str) -> JsonObjectParse:
    """Parse one JSONL record, skipping blank lines.

    The same contract as :func:`parse_object`, plus: a line that is empty or
    whitespace-only returns ``Success(None)`` rather than being reported as
    malformed. Every JSONL reader here wants that, and doing it per-caller
    invited each to spell the blank-line check slightly differently.
    """
    if not line.strip():
        return Success(None)
    return parse_object(text=line)
