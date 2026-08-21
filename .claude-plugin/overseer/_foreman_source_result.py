"""Shared source-result unwrapping for foreman gatherer readers."""

from __future__ import annotations

from typing import TypeVar, overload

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from errors import OverseerSourceError

from overseer._vendor.returns.io import IOResult
from overseer._vendor.returns.pipeline import is_successful
from overseer._vendor.returns.unsafe import unsafe_perform_io

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = ["source_value"]

_SourceValue = TypeVar("_SourceValue")


@overload
def source_value(*, result: IOResult[_SourceValue, OverseerSourceError]) -> _SourceValue: ...


@overload
def source_value(*, result: dict[str, object] | None) -> dict[str, object] | None: ...


def source_value(
    *, result: IOResult[_SourceValue, OverseerSourceError] | dict[str, object] | None
) -> _SourceValue | dict[str, object] | None:
    """Return a source result value, or raise the source diagnostic as `ValueError`.

    `fetch_release_lane_runs` still has tests that monkeypatch the
    pre-railway dict/None shape. Normalize that compatibility shape here so
    every real `IOResult` caller shares one failure-track translation.
    """
    if isinstance(result, dict) or result is None:
        return result
    if not is_successful(result):
        raise ValueError(unsafe_perform_io(result.failure()).detail)
    return unsafe_perform_io(result.unwrap())
