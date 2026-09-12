"""The closed provider, credential-kind, target-adapter and backend registries.

SPECIFICATION/contracts.md states the initial provider
registry as EXACTLY one row and requires that an acquire or provision request naming an
unregistered provider or credential kind return `invalid-request` with exit `2` before any
store, worker, health adapter or target access. The same contract additionally requires
every row to declare shared-usage observation either `unsupported` or as one registered
observer, and pins the initial Anthropic setup-token row to `unsupported` because that
value receives HTTP `403` from Anthropic's usage endpoint.

That last fact is the reason this table is data rather than prose. `unsupported` is not a
gap waiting to be filled in: issuing the usage request with a setup token, or claiming an
observed remainder for it, is FORBIDDEN. A future row may declare an observer; it may not
quietly inherit one.

PURPOSE IS NOT REGISTERED, and that omission is deliberate. The provider registry imposes
no purpose restriction: `factory` is the conventional initial rollout purpose and
`interactive` is the reserved interoperability spelling for coexistence with
`caam-anthropic-loop`, but acquire and provision must accept either name and every other
non-empty purpose identically, subject only to byte-exact matching and configured
reservation policy. Both names are declared here so a caller cites one constant rather
than a string literal — `Reserved` means reservation configuration and consumers must use
that exact spelling, and it grants no extra behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__: list[str] = [
    "CONVENTIONAL_FACTORY_PURPOSE",
    "PROVIDER_REGISTRY",
    "REGISTERED_SECRET_STORE_BACKENDS",
    "REGISTERED_TARGET_ADAPTERS",
    "RESERVED_INTERACTIVE_PURPOSE",
    "UNSUPPORTED_SHARED_USAGE",
    "ProviderRow",
    "provider_is_registered",
    "provider_row",
    "rows_for_provider",
]

UNSUPPORTED_SHARED_USAGE: Final = "unsupported"
CONVENTIONAL_FACTORY_PURPOSE: Final = "factory"
RESERVED_INTERACTIVE_PURPOSE: Final = "interactive"

REGISTERED_TARGET_ADAPTERS: Final = ("isolated-run",)
REGISTERED_SECRET_STORE_BACKENDS: Final = ("onepassword",)


@dataclass(frozen=True, kw_only=True)
class ProviderRow:
    """One registered provider-and-credential-kind row and its declared adapters."""

    provider: str
    kind: str
    acquisition_terminal: str
    account_identity_inspector: str
    validation_adapter: str
    shared_usage_observation: str


PROVIDER_REGISTRY: Final[tuple[ProviderRow, ...]] = (
    ProviderRow(
        provider="anthropic",
        kind="claude-code-oauth",
        acquisition_terminal="claude setup-token",
        account_identity_inspector="anthropic-browser-account-email",
        validation_adapter="anthropic-messages-probe",
        shared_usage_observation=UNSUPPORTED_SHARED_USAGE,
    ),
)


def provider_row(*, provider: str, kind: str) -> ProviderRow | None:
    """The registered row for this provider-and-kind pair, or None when unregistered.

    Matching is byte-exact on both fields. A request naming a registered provider with an
    unregistered kind is as unregistered as an unknown provider: the adapters a row
    declares are per-KIND, so there is nothing to fall back to.
    """
    for row in PROVIDER_REGISTRY:
        if row.provider == provider and row.kind == kind:
            return row
    return None


def rows_for_provider(*, provider: str) -> tuple[ProviderRow, ...]:
    """Every registered row for `provider`, in registry order.

    The multi-purpose reservation rule needs this: such a reservation is invalid when ANY
    registered credential-kind row for that provider declares `unsupported`, so the
    question is asked of the whole provider rather than of one requested kind.
    """
    return tuple(row for row in PROVIDER_REGISTRY if row.provider == provider)


def provider_is_registered(*, provider: str) -> bool:
    """Whether any registered row names `provider`."""
    return rows_for_provider(provider=provider) != ()
