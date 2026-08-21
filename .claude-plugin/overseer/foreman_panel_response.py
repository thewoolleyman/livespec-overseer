"""Reviewer stdout parsing helpers for the foreman panel convenor."""

from __future__ import annotations

import jsonio

__all__: list[str] = [
    "reviewer_response_object",
]


def _fenced_json_body(*, text: str) -> str | None:
    stripped = text.strip()
    prefix = "```json\n" if stripped.startswith("```json\n") else "```\n"
    suffix = "\n```"
    if stripped.startswith(prefix) and stripped.endswith(suffix):
        return stripped.removeprefix(prefix).removesuffix(suffix).strip()
    return None


def reviewer_response_object(*, raw_stdout: str) -> dict[str, object] | None:
    response = jsonio.parse_object(text=raw_stdout)
    if response is not None:
        return response
    fenced_body = _fenced_json_body(text=raw_stdout)
    if fenced_body is None:
        return None
    return jsonio.parse_object(text=fenced_body)
