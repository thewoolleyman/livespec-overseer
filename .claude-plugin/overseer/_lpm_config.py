"""The closed, validated `llm-provider-manager` configuration object.

SPECIFICATION/contracts.md states that the configuration object
MUST contain only `version` (the integer `1`) and a closed set of optional keys, that an
ABSENT configuration file means the default object, and that an unreadable existing file,
invalid UTF-8, malformed JSON, duplicate member name, unknown key or version, wrong JSON
type, malformed reservation shape, invalid enum, non-unique array, out-of-bounds value or
unregistered adapter or backend name MUST return `invalid-request` with exit `2` BEFORE
any store, health adapter, acquisition browser or provisioning target access.

"Before" is the whole contract. Every one of those failures is cheap to detect and
expensive to detect late: once a backend role has been launched, a token has been taken
from the user keyring and an `op` child has been spawned, and a configuration refusal at
that point has already paid the cost it was supposed to prevent. So this module performs
no I/O beyond reading the one configuration file and touches no registry state.

The same contract adds the one CROSS-FIELD relation:
`acquisition_worker_timeout_seconds` must be at least three times
`provider_probe_timeout_seconds` plus six times `external_call_timeout_seconds` plus three
seconds, reserving all three possible validation probes, their one- and two-second waits,
browser-control startup and terminal store/lock work. Each field can be individually
in-bounds while the set is unsatisfiable, which is exactly the shape a per-field validator
cannot see — so it is checked HERE, after the fields are accepted and before anything is
launched, and refused with the same pre-access `invalid-request`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import parse_canonical_json
from _lpm_config_fields import (
    HEALTH_STRATEGIES,
    INTEGER_FIELDS,
    enum_field,
    integer_field,
    name_list_field,
)
from _lpm_registry import REGISTERED_SECRET_STORE_BACKENDS, REGISTERED_TARGET_ADAPTERS
from _lpm_reservations import AccountReservations, reservations_from_object
from _lpm_results import ManagerError, invalid_request

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "CONFIG_VERSION",
    "PERMITTED_CONFIG_KEYS",
    "ManagerConfig",
    "config_from_object",
    "default_config",
    "load_manager_config",
    "parse_manager_config",
    "required_acquisition_worker_timeout",
]

CONFIG_VERSION: Final = 1

_DEFAULT_HEALTH_STRATEGY: Final = "none"

PERMITTED_CONFIG_KEYS: Final[frozenset[str]] = frozenset(
    {"version", "account_reservations", "health_strategy", "enabled_target_adapters"}
    | {"secret_store_backend"}
    | {field.name for field in INTEGER_FIELDS}
)


@dataclass(frozen=True, kw_only=True)
class ManagerConfig:
    """The accepted configuration: every key present, every value already validated.

    Constructed only by :func:`config_from_object`, so an instance means "this
    configuration passed the whole pre-access boundary" — there is no partially-validated
    form to mistake for an accepted one.
    """

    account_reservations: AccountReservations
    maximum_validation_age_seconds: int
    backend_cache_interval_seconds: int
    provider_probe_timeout_seconds: int
    external_call_timeout_seconds: int
    acquisition_worker_timeout_seconds: int
    acquisition_step_limit: int
    health_floor_percent: int
    browser_attention_wait_seconds: int
    health_strategy: str
    enabled_target_adapters: tuple[str, ...]
    secret_store_backend: str


def default_config() -> ManagerConfig:
    """The object an ABSENT configuration file means.

    Derived by validating the minimal object rather than restating each literal, so the
    defaults have ONE source — the bounds table and the registries — and cannot drift
    from the values every other caller is validated against.
    """
    return config_from_object(parsed={"version": CONFIG_VERSION}).unwrap()


def required_acquisition_worker_timeout(
    *, provider_probe_timeout_seconds: int, external_call_timeout_seconds: int
) -> int:
    """The contract's minimum acquisition worker timeout for these two intervals."""
    return 3 * provider_probe_timeout_seconds + 6 * external_call_timeout_seconds + 3


@dataclass(frozen=True, kw_only=True)
class _NamedFields:
    """The three accepted non-integer keys, carried together to the assembly step."""

    health_strategy: str
    enabled_target_adapters: tuple[str, ...]
    secret_store_backend: str


def config_from_object(*, parsed: object) -> Result[ManagerConfig, ManagerError]:
    """Validate one already-parsed configuration value into a `ManagerConfig`.

    The order is the contract's: envelope, then per-field bounds and enums, then the
    reservation shape (which needs the accepted `health_strategy`), then the cross-field
    acquisition-deadline relation. Every step refuses before the next one runs, so the
    first reported defect is the outermost one rather than a confusing consequence.
    """
    envelope = _validated_envelope(parsed=parsed)
    if isinstance(envelope, Failure):
        return envelope
    source = envelope.unwrap()
    integers = _validated_integers(source=source)
    if isinstance(integers, Failure):
        return integers
    named = _validated_names(source=source)
    if isinstance(named, Failure):
        return named
    reservations = reservations_from_object(
        value=source.get("account_reservations", {}),
        health_strategy=named.unwrap().health_strategy,
    )
    if isinstance(reservations, Failure):
        return reservations
    relation = _acquisition_deadline_refusal(integers=integers.unwrap())
    if relation is not None:
        return Failure(relation)
    return Success(
        _assembled(
            reservations=reservations.unwrap(),
            integers=integers.unwrap(),
            named=named.unwrap(),
        )
    )


def _validated_envelope(*, parsed: object) -> Result[dict[str, object], ManagerError]:
    if not isinstance(parsed, dict):
        return Failure(invalid_request(message="configuration must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    version = source.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version != CONFIG_VERSION:
        return Failure(invalid_request(message="configuration version must be the integer 1"))
    unknown = sorted(set(source) - PERMITTED_CONFIG_KEYS)
    if unknown:
        return Failure(invalid_request(message=f"unknown configuration key: {unknown[0]}"))
    return Success(source)


def _validated_integers(*, source: dict[str, object]) -> Result[dict[str, int], ManagerError]:
    integers: dict[str, int] = {}
    for field in INTEGER_FIELDS:
        accepted = integer_field(field=field, value=source.get(field.name, field.default))
        if isinstance(accepted, Failure):
            return accepted
        integers[field.name] = accepted.unwrap()
    return Success(integers)


def _validated_names(*, source: dict[str, object]) -> Result[_NamedFields, ManagerError]:
    strategy = enum_field(
        name="health_strategy",
        value=source.get("health_strategy", _DEFAULT_HEALTH_STRATEGY),
        permitted=HEALTH_STRATEGIES,
    )
    if isinstance(strategy, Failure):
        return strategy
    backend = enum_field(
        name="secret_store_backend",
        value=source.get("secret_store_backend", REGISTERED_SECRET_STORE_BACKENDS[0]),
        permitted=REGISTERED_SECRET_STORE_BACKENDS,
    )
    if isinstance(backend, Failure):
        return backend
    adapters = name_list_field(
        name="enabled_target_adapters",
        value=source.get("enabled_target_adapters", list(REGISTERED_TARGET_ADAPTERS)),
        registered=REGISTERED_TARGET_ADAPTERS,
    )
    if isinstance(adapters, Failure):
        return adapters
    return Success(
        _NamedFields(
            health_strategy=strategy.unwrap(),
            enabled_target_adapters=adapters.unwrap(),
            secret_store_backend=backend.unwrap(),
        )
    )


def _assembled(
    *, reservations: AccountReservations, integers: dict[str, int], named: _NamedFields
) -> ManagerConfig:
    return ManagerConfig(
        account_reservations=reservations,
        maximum_validation_age_seconds=integers["maximum_validation_age_seconds"],
        backend_cache_interval_seconds=integers["backend_cache_interval_seconds"],
        provider_probe_timeout_seconds=integers["provider_probe_timeout_seconds"],
        external_call_timeout_seconds=integers["external_call_timeout_seconds"],
        acquisition_worker_timeout_seconds=integers["acquisition_worker_timeout_seconds"],
        acquisition_step_limit=integers["acquisition_step_limit"],
        health_floor_percent=integers["health_floor_percent"],
        browser_attention_wait_seconds=integers["browser_attention_wait_seconds"],
        health_strategy=named.health_strategy,
        enabled_target_adapters=named.enabled_target_adapters,
        secret_store_backend=named.secret_store_backend,
    )


def parse_manager_config(*, text: str) -> Result[ManagerConfig, ManagerError]:
    """Parse and validate configuration TEXT; a duplicate member name is refused."""
    parsed = parse_canonical_json(text=text)
    if isinstance(parsed, Failure):
        return Failure(invalid_request(message=f"configuration is {parsed.failure().reason}"))
    return config_from_object(parsed=parsed.unwrap())


def load_manager_config(*, path: Path) -> Result[ManagerConfig, ManagerError]:
    """Read the configuration file; an absent file means the default object.

    An EXISTING but unreadable file is never treated as absent. Silently substituting
    defaults for a file the operator wrote would run the manager under a configuration
    nobody chose — including a default `health_strategy` of `none`, which applies no
    health-based exclusion at all.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Success(default_config())
    except (OSError, ValueError) as failure:
        reason = failure.__class__.__name__
        return Failure(invalid_request(message=f"configuration is unreadable: {reason}"))
    return parse_manager_config(text=text)


def _acquisition_deadline_refusal(*, integers: dict[str, int]) -> ManagerError | None:
    required = required_acquisition_worker_timeout(
        provider_probe_timeout_seconds=integers["provider_probe_timeout_seconds"],
        external_call_timeout_seconds=integers["external_call_timeout_seconds"],
    )
    if integers["acquisition_worker_timeout_seconds"] < required:
        return invalid_request(
            message=(
                "acquisition_worker_timeout_seconds must be at least "
                f"{required} for the configured probe and external-call timeouts"
            )
        )
    return None
