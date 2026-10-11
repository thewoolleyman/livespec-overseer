"""Validated isolated-run registration lookup for concrete target composition."""

from __future__ import annotations

from pathlib import Path
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_localstate import read_local_record
from _lpm_paths import local_record_path
from _lpm_results import ManagerError, invalid_request
from _lpm_runtime_base import RuntimeHost
from _lpm_time import is_at_or_after, parse_manager_time

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
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


def registered_destination(*, host: RuntimeHost, consumer_run_id: str) -> Result[str, ManagerError]:
    """Return one registration's canonical destination or its typed refusal."""
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
    return _validated_registration(host=host, source=source.unwrap())


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
    *, host: RuntimeHost, source: dict[str, object]
) -> Result[str, ManagerError]:
    created = parse_manager_time(text=str(source["created_at"]))
    expires = parse_manager_time(text=str(source["expires_at"]))
    if created is None or expires is None:
        return Failure(invalid_request(message="isolated-run registration time is invalid"))
    duration = int((expires - created).total_seconds())
    if duration <= 0 or duration > _REGISTRATION_SECONDS:
        return Failure(invalid_request(message="isolated-run registration duration is invalid"))
    if is_at_or_after(moment=host.capture_time(), limit=str(source["expires_at"])) is not False:
        return Failure(invalid_request(message="isolated-run registration has expired"))
    root = Path(str(source["isolated_root"]))
    target = Path(str(source["target_path"]))
    if not all((root.is_absolute(), target.is_absolute())):
        return Failure(invalid_request(message="isolated-run registration paths must be absolute"))
    canonical_root = root.resolve(strict=False)
    canonical_target = target.resolve(strict=False)
    if not canonical_target.is_relative_to(canonical_root):
        return Failure(invalid_request(message="isolated-run target escapes its root"))
    return Success(str(canonical_target))
