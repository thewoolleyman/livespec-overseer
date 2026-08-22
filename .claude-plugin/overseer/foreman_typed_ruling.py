"""Typed-ruling vocabulary mechanics for foreman consensus acts."""

from __future__ import annotations

__all__: list[str] = [
    "ruling_kind_defined",
]


def ruling_kind_defined(*, kind: str) -> bool:
    return kind in governed_ruling_kinds()


def governed_ruling_kinds() -> frozenset[str]:
    """Return the ruling kinds defined by the governing orchestrator contract.

    v026 deliberately forbids this tree from defining or restating that
    vocabulary. Until the governing contract exposes a consumable definition,
    the channel is vocabulary-empty and every typed ruling escalates as
    unenumerated.
    """
    return frozenset()
