"""Restore a certified ready round lost before Herdr binds it durably."""

from __future__ import annotations

import json
import os

import jsonio
from _registry_core import atomic_write, file_lock, resolve_stamp_store
from _registry_rounds import RoundRecord
from _registry_stamp_core import read_stamp_data, stamp_key

__all__: list[str] = ["restore_round_record"]

_ROUND_FIELDS = frozenset(
    {
        "at",
        "bands",
        "compaction_rearmed_at",
        "expired_at",
        "expiry_notice_sent",
        "session_identity",
    }
)


def restore_round_record(
    *,
    repo: str,
    topic: str,
    record: RoundRecord,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Merge the previously-certified round back beside unrelated track metadata."""
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = stamp_key(repo=repo, topic=topic)
        entry = dict(jsonio.as_object(value=data.get(key)) or {})
        entry = {name: value for name, value in entry.items() if name not in _ROUND_FIELDS}
        entry.update(
            {
                "at": record.at,
                "bands": list(record.bands),
                "compaction_rearmed_at": record.compaction_rearmed_at,
                "expired_at": record.expired_at,
                "expiry_notice_sent": record.expiry_notice_sent,
                "session_identity": record.session_identity,
            }
        )
        data[key] = entry
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")
