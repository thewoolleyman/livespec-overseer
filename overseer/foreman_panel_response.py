"""Reviewer stdout parsing helpers for the foreman panel convenor."""

from __future__ import annotations

import re

import jsonio

_FENCE_PATTERN = re.compile(r"```(?:json)?\n(.*?)\n```", re.DOTALL)

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


def _parsed_response(*, text: str, leading: bool = False) -> dict[str, object] | None:
    result = jsonio.parse_leading_object(text=text) if leading else jsonio.parse_object(text=text)
    return None if jsonio.is_parse_failure(result=result) else result.unwrap()


def _embedded_fenced_response(*, text: str) -> dict[str, object] | None:
    match = _FENCE_PATTERN.search(text)
    if match is None:
        return None
    return _parsed_response(text=match.group(1))


def _trailing_response(*, text: str) -> dict[str, object] | None:
    start = len(text)
    while True:
        start = text.rfind("{", 0, start)
        if start < 0:
            return None
        response = _parsed_response(text=text[start:])
        if response is not None:
            return response


def reviewer_response_object(*, raw_stdout: str) -> dict[str, object] | None:
    response = _parsed_response(text=raw_stdout)
    if response is not None:
        return response
    leading = _parsed_response(text=raw_stdout, leading=True)
    if leading is not None:
        return leading
    fenced_body = _fenced_json_body(text=raw_stdout)
    if fenced_body is not None:
        return _parsed_response(text=fenced_body)
    embedded_fenced = _embedded_fenced_response(text=raw_stdout)
    if embedded_fenced is not None:
        return embedded_fenced
    return _trailing_response(text=raw_stdout)
