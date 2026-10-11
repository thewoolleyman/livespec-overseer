"""Validated isolated-run registration lookup for concrete target composition."""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_localstate import read_local_record, remove_local_record
from _lpm_locks import HeldLock, release_lock
from _lpm_paths import account_database_home, local_record_path
from _lpm_results import ManagerError, invalid_request
from _lpm_runtime_base import RuntimeHost, destination_lock
from _lpm_runtime_issuance import refuse_destination_conflict
from _lpm_time import is_at_or_after, parse_manager_time

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "RegisteredDestination",
    "registered_destination",
]

_REGISTRATION_VERSION: Final = 1
_REGISTRATION_SECONDS: Final = 86400
_REGISTRATION_MEMBERS: Final = (
    "version",
    "consumer_run_id",
    "isolated_root",
    "target_path",
    "created_at",
    "expires_at",
)


@dataclass(kw_only=True)
class RegisteredDestination:
    """One validated destination and the issuance lock that currently protects it."""

    destination: str
    held_lock: HeldLock | None

    def release(self) -> None:
        """Release the destination lock once; repeated cleanup is a no-op."""
        if self.held_lock is not None:
            release_lock(held=self.held_lock)
            self.held_lock = None


def registered_destination(
    *, host: RuntimeHost, consumer_run_id: str
) -> Result[RegisteredDestination, ManagerError]:
    """Validate one registration and lock its canonical destination for issuance."""
    path = local_record_path(
        state_dir=host.state_dir,
        family="run-registration",
        identity=(consumer_run_id,),
    ).unwrap()
    stored = read_local_record(path=path, owner_uid=host.owner_uid)
    if isinstance(stored, Failure):
        return Failure(invalid_request(message="isolated-run registration is unsafe"))
    source = _registration_source(parsed=stored.unwrap(), consumer_run_id=consumer_run_id)
    if isinstance(source, Failure):
        return Failure(source.failure())
    validated = _validated_registration(host=host, path=path, source=source.unwrap())
    if isinstance(validated, Failure):
        return Failure(validated.failure())
    destination = validated.unwrap()
    held = destination_lock(host=host, destination=destination)
    if isinstance(held, Failure):
        return Failure(held.failure())
    registration = RegisteredDestination(destination=destination, held_lock=held.unwrap())
    conflict = refuse_destination_conflict(
        host=host,
        consumer_run_id=consumer_run_id,
        destination=destination,
    )
    if isinstance(conflict, Failure):
        registration.release()
        return Failure(conflict.failure())
    return Success(registration)


def _registration_source(
    *, parsed: object, consumer_run_id: str
) -> Result[dict[str, object], ManagerError]:
    if not isinstance(parsed, dict):
        return Failure(invalid_request(message="isolated-run registration is missing or invalid"))
    source = cast("dict[str, object]", parsed)
    if sorted(source) != sorted(_REGISTRATION_MEMBERS):
        return Failure(invalid_request(message="isolated-run registration has invalid members"))
    version = source["version"]
    if isinstance(version, bool) or version != _REGISTRATION_VERSION:
        return Failure(invalid_request(message="isolated-run registration version is invalid"))
    for member in _REGISTRATION_MEMBERS[1:]:
        value = source[member]
        if not isinstance(value, str) or value == "":
            return Failure(
                invalid_request(message=f"isolated-run registration {member} is invalid")
            )
    if source["consumer_run_id"] != consumer_run_id:
        return Failure(invalid_request(message="isolated-run registration identity is invalid"))
    return Success(source)


def _validated_registration(
    *, host: RuntimeHost, path: Path, source: dict[str, object]
) -> Result[str, ManagerError]:
    times = _validated_registration_times(host=host, path=path, source=source)
    if isinstance(times, Failure):
        return Failure(times.failure())
    return _validated_destination(host=host, source=source)


def _validated_registration_times(
    *, host: RuntimeHost, path: Path, source: dict[str, object]
) -> Result[None, ManagerError]:
    created = parse_manager_time(text=str(source["created_at"]))
    expires = parse_manager_time(text=str(source["expires_at"]))
    if created is None or expires is None:
        return Failure(invalid_request(message="isolated-run registration time is invalid"))
    duration = int((expires - created).total_seconds())
    if duration <= 0 or duration > _REGISTRATION_SECONDS:
        return Failure(invalid_request(message="isolated-run registration duration is invalid"))
    if is_at_or_after(moment=host.capture_time(), limit=str(source["expires_at"])) is not False:
        removed = remove_local_record(path=path, owner_uid=host.owner_uid)
        if isinstance(removed, Failure):
            return Failure(removed.failure())
        return Failure(invalid_request(message="isolated-run registration has expired"))
    return Success(None)


def _validated_destination(
    *, host: RuntimeHost, source: dict[str, object]
) -> Result[str, ManagerError]:
    root = Path(str(source["isolated_root"]))
    target = Path(str(source["target_path"]))
    if not all((root.is_absolute(), target.is_absolute())):
        return Failure(invalid_request(message="isolated-run registration paths must be absolute"))
    canonical_root = root.resolve(strict=False)
    canonical_target = target.resolve(strict=False)
    if not target.parent.is_relative_to(root) or not canonical_target.is_relative_to(
        canonical_root
    ):
        return Failure(invalid_request(message="isolated-run target escapes its root"))
    safe_directories = _safe_target_directories(
        root=root,
        target_parent=target.parent,
        owner_uid=host.owner_uid,
    )
    if isinstance(safe_directories, Failure):
        return Failure(safe_directories.failure())
    home = account_database_home(uid=host.owner_uid)
    if home is None:
        return Failure(invalid_request(message="the manager account home is unavailable"))
    protected = (home / ".claude" / ".credentials.json").resolve(strict=False)
    if canonical_target == protected:
        return Failure(invalid_request(message="isolated-run target is a protected credential"))
    return Success(str(canonical_target))


def _safe_target_directories(
    *, root: Path, target_parent: Path, owner_uid: int
) -> Result[None, ManagerError]:
    """Validate every declared directory from the isolated root through the target parent."""
    relative_parent = target_parent.relative_to(root)
    candidate = root
    directories = [candidate]
    for member in relative_parent.parts:
        candidate /= member
        directories.append(candidate)
    for directory in directories:
        try:
            status = directory.lstat()
        except OSError:
            return Failure(invalid_request(message="isolated-run target directory is missing"))
        mode = stat.S_IMODE(status.st_mode)
        safe = stat.S_ISDIR(status.st_mode) and status.st_uid == owner_uid and not mode & ~0o700
        if not safe:
            return Failure(invalid_request(message="isolated-run target directory is unsafe"))
    return Success(None)
