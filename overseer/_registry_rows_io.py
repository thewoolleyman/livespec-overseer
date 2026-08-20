"""Raw JSONL row I/O for the durable mapping store."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass

import jsonio
from _registry_core import atomic_write, resolve_store, warn

__all__: list[str] = [
    "RawMappingRow",
    "read_row_records",
    "read_rows",
    "write_rows",
]


@dataclass(frozen=True, kw_only=True)
class RawMappingRow:
    row: dict[str, object]
    raw_line: str
    lineno: int


def read_row_records(
    *,
    store_path: str | os.PathLike[str] | None = None,
) -> list[RawMappingRow]:
    """Read raw object rows with source text, skipping malformed JSONL lines.

    Operating on raw dicts (not Tracks) for rewrite/remove preserves unknown
    keys such as ``added_at`` on the surviving rows. Malformed JSON and
    non-object lines stay in this outer fail-soft layer: they are not mapping
    object rows and are still warned-and-skipped exactly as before.
    """
    path = resolve_store(store_path=store_path)
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    # ValueError covers the UnicodeDecodeError a non-UTF-8 store raises; it is a
    # ValueError subclass, so an OSError-only handler leaked it (B7).
    except (OSError, ValueError) as exc:  # PermissionError, NFS hiccup, mid-move, non-UTF-8
        warn(message=f"unreadable mapping store {path}: {exc}")
        return []
    records: list[RawMappingRow] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            warn(message=f"skipping malformed line {lineno} in {path}: {exc}")
            continue
        record = jsonio.as_object(value=obj)
        if record is None:
            warn(message=f"skipping non-object line {lineno} in {path}")
            continue
        records.append(RawMappingRow(row=record, raw_line=raw, lineno=lineno))
    return records


def read_rows(*, store_path: str | os.PathLike[str] | None = None) -> list[dict[str, object]]:
    return [record.row for record in read_row_records(store_path=store_path)]


def write_rows(
    *,
    rows: Iterable[dict[str, object]],
    store_path: str | os.PathLike[str] | None = None,
    raise_errors: bool = False,
) -> None:
    body = "".join(json.dumps(row) + "\n" for row in rows)
    atomic_write(path=resolve_store(store_path=store_path), body=body, raise_errors=raise_errors)
