"""A bounded lock wait fails closed, and the lock file is never deleted.

SPECIFICATION/contracts.md serializes this operation on kernel lock files and makes a
TIMEOUT acquiring one `store-unavailable` rather than a reason to proceed unserialized.

Two properties are pinned here. A wait that expires returns that refusal having changed
nothing — in particular it does not delete the lock file, because deleting it would let a
second holder open a FRESH file, take a lock on a different open file description, and
believe it was serialized against the first. And a lock is released by closing its
description, which is what makes a killed worker unable to wedge the account it held.

The clock and the sleep are injected so the bounded wait is exercised deterministically
rather than by making this suite actually wait.
"""

from __future__ import annotations

import importlib
import os
import pathlib

__all__: list[str] = []


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_locks.py"
    assert module_path.is_file(), "overseer/_lpm_locks.py must exist"
    return (importlib.import_module("_lpm_locks"),)


def _uid() -> int:
    return os.geteuid()


def test_a_lock_is_taken_once_and_released_by_closing_its_description(tmp_path):
    (locks,) = _modules()
    path = tmp_path / "locks" / "account.lock"
    ticks = iter([0.0, 0.0, 1.0, 2.0, 3.0])

    held = locks.take_lock(
        path=path,
        owner_uid=_uid(),
        timeout_seconds=1.0,
        monotonic=lambda: next(ticks),
        sleep=lambda _seconds: None,
    ).unwrap()
    contended = locks.take_lock(
        path=path,
        owner_uid=_uid(),
        timeout_seconds=0.0,
        monotonic=lambda: next(ticks),
        sleep=lambda _seconds: None,
    )

    assert path.stat().st_mode & 0o777 == 0o600
    assert contended.failure().error_type == "store-unavailable"
    assert contended.failure().message == "account.lock was held past the wait budget"
    assert path.exists(), "a bounded wait that expires deletes nothing"
    locks.release_lock(held=held)
    reacquired = locks.take_lock(
        path=path,
        owner_uid=_uid(),
        timeout_seconds=0.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )
    assert reacquired.unwrap().path == path
    locks.release_lock(held=reacquired.unwrap())


def test_a_contended_lock_waits_and_succeeds_within_its_budget(tmp_path):
    (locks,) = _modules()
    path = tmp_path / "locks" / "record.lock"
    first = locks.take_lock(
        path=path,
        owner_uid=_uid(),
        timeout_seconds=0.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    ).unwrap()
    naps: list[float] = []

    def _release_after_one_nap(seconds: float) -> None:
        naps.append(seconds)
        locks.release_lock(held=first)

    second = locks.take_lock(
        path=path,
        owner_uid=_uid(),
        timeout_seconds=5.0,
        monotonic=lambda: 0.0,
        sleep=_release_after_one_nap,
    )

    assert naps == [locks.LOCK_POLL_SECONDS]
    locks.release_lock(held=second.unwrap())


def test_an_unusable_lock_path_is_store_unavailable(tmp_path):
    (locks,) = _modules()
    target = tmp_path / "locks" / "real.lock"
    linked = tmp_path / "locks" / "account.lock"
    target.parent.mkdir(mode=0o700)
    target.write_text("", encoding="utf-8")
    linked.symlink_to(target)
    directory = tmp_path / "locks" / "adir"
    directory.mkdir()

    symlinked = locks.take_lock(
        path=linked,
        owner_uid=_uid(),
        timeout_seconds=0.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )
    unusable = locks.take_lock(
        path=directory,
        owner_uid=_uid(),
        timeout_seconds=0.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )
    refused_parent = locks.take_lock(
        path=tmp_path / "locks" / "real.lock" / "nested.lock",
        owner_uid=_uid(),
        timeout_seconds=0.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    assert symlinked.failure().message == "account.lock is a symlink"
    assert unusable.failure().message.startswith("adir is unusable: ")
    assert refused_parent.failure().error_type == "store-unavailable"
