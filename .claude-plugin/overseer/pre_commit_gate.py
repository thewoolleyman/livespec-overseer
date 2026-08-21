"""Shared helpers for the repo-local pre-commit shape wrapper."""

from __future__ import annotations

from collections.abc import Iterable

__all__: list[str] = [
    "union_skip_targets",
]


def union_skip_targets(*, existing: str, required: Iterable[str]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for target in (*existing.split(), *required):
        if not target or target in seen:
            continue
        seen.add(target)
        ordered.append(target)
    return " ".join(ordered)
