"""Journal records for deterministic foreman-act dispositions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

__all__: list[str] = ["AppendJournal", "append_journal"]


class AppendJournal(Protocol):
    def __call__(self, *, repo: Path, record: dict[str, object]) -> None: ...


def append_journal(*, repo: Path, record: dict[str, object]) -> None:
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    stamped = {"at": _utc_now(), **record}
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as handle:
        _ = handle.write(json.dumps(stamped, sort_keys=True) + "\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
