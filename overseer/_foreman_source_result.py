"""Shared source-result unwrapping for foreman gatherer readers."""

from __future__ import annotations

from typing import TypeVar

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from errors import OverseerSourceError

from overseer._vendor.returns.io import IOResult
from overseer._vendor.returns.pipeline import is_successful
from overseer._vendor.returns.unsafe import unsafe_perform_io

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = ["source_value"]

_SourceValue = TypeVar("_SourceValue")


def source_value(*, result: IOResult[_SourceValue, OverseerSourceError]) -> _SourceValue:
    """Return a source result value, or raise the source diagnostic as `ValueError`."""
    if not is_successful(result):
        raise ValueError(unsafe_perform_io(result.failure()).detail)
    return unsafe_perform_io(result.unwrap())
