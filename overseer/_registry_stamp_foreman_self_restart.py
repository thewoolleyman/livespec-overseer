"""Foreman self-restart lineage state in the injection-stamp sidecar."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import jsonio
from _registry_core import atomic_write, file_lock, resolve_stamp_store
from _registry_stamp_core import read_stamp_data, stamp_key

__all__: list[str] = [
    "ForemanSelfRestartRecord",
    "consume_foreman_self_restart_notice",
    "read_foreman_self_restart",
    "record_foreman_self_restart",
]


@dataclass(frozen=True, kw_only=True)
class ForemanSelfRestartRecord:
    attempted: bool
    reason: str | None
    notice_pending: bool


def _self_restart_key(*, repo: str, topic: str) -> str:
    return f"{stamp_key(repo=repo, topic=topic)}\tforeman_self_restart"


def _record_from_entry(*, entry: dict[str, object] | None) -> ForemanSelfRestartRecord | None:
    self_restart = jsonio.as_object(value=entry.get("foreman_self_restart")) if entry else None
    if self_restart is None:
        return None
    reason = self_restart.get("reason")
    return ForemanSelfRestartRecord(
        attempted=self_restart.get("attempted") is True,
        reason=reason if isinstance(reason, str) else None,
        notice_pending=self_restart.get("notice_pending") is True,
    )


def read_foreman_self_restart(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> ForemanSelfRestartRecord:
    data = read_stamp_data(path=resolve_stamp_store(stamp_path=stamp_path))
    records = (
        _record_from_entry(entry=jsonio.as_object(value=data.get(key)))
        for key in (
            _self_restart_key(repo=repo, topic=topic),
            stamp_key(repo=repo, topic=topic),
        )
    )
    return next(
        (record for record in records if record is not None),
        ForemanSelfRestartRecord(attempted=False, reason=None, notice_pending=False),
    )


def record_foreman_self_restart(
    *,
    repo: str,
    topic: str,
    reason: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Persist the once-per-lineage foreman self-restart fact.

    This deliberately lives outside the in-memory uncertifiable-ready band state:
    a self-restart produces a new declaration/session, while the lineage cap must
    survive that identity change.
    """
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = _self_restart_key(repo=repo, topic=topic)
        entry = jsonio.as_object(value=data.get(key))
        current = dict(entry) if entry is not None else {}
        prior = _record_from_entry(entry=current)
        current["foreman_self_restart"] = {
            "attempted": True,
            "notice_pending": prior.notice_pending if prior and prior.attempted else True,
            "reason": reason,
        }
        data[key] = current
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")


def consume_foreman_self_restart_notice(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = _self_restart_key(repo=repo, topic=topic)
        entry = jsonio.as_object(value=data.get(key))
        current = dict(entry) if entry is not None else {}
        prior = _record_from_entry(entry=current) or ForemanSelfRestartRecord(
            attempted=False,
            reason=None,
            notice_pending=False,
        )
        current["foreman_self_restart"] = {
            "attempted": prior.attempted,
            "notice_pending": False,
            "reason": prior.reason,
        }
        data[key] = current
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")
