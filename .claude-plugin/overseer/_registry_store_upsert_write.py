"""Upsert write error handling for the durable registry store."""

from __future__ import annotations

import os

from _registry_core import warn
from _registry_rows_io import write_rows

__all__: list[str] = ["write_upsert_rows"]


def write_upsert_rows(
    *,
    rows: list[dict[str, object]],
    store_path: str | os.PathLike[str] | None,
    path: os.PathLike[str],
) -> bool:
    try:
        written = write_rows(rows=rows, store_path=store_path, raise_errors=True)
    except OSError as exc:
        warn(message=f"could not upsert mapping store {path}: {exc}")
        return False
    # A write the mapping-store contract refuses is reported as a failed upsert,
    # not as a silent no-op: the caller's row was never persisted either way.
    return written
