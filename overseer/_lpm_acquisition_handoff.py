"""The bounded acquisition handoff: describe the mint, and refuse to be one.

SPECIFICATION/contracts.md gives every registered provider-and-kind row an ACQUISITION
TERMINAL — `claude setup-token` for the initial Anthropic row — and spec.md keeps browser
acquisition agent-discovered rather than provider-scripted, running it through a closed
research/execution role protocol with a headed browser, an operator-resolvable verification
artifact and a bounded worker deadline.

NONE OF THAT HAPPENS HERE, AND THAT IS THE WHOLE POINT OF THE MODULE. This is the handoff:
it names WHAT would have to be minted and WHICH terminal mints it, and then stops. It spawns
no process, opens no browser, touches no vault and writes nothing. A caller that discovers a
missing credential gets a description it can show an operator, never an acquisition it
triggered by asking.

THE AUTHORIZATION FLAG IS A GATE, NOT A LABEL. An unauthorized caller receives a typed
`invalid-request` and NO description at all — not a description marked unauthorized. The
difference matters because the description is the actionable half: returning it alongside a
refusal invites a caller to act on it anyway, which is exactly the "acquire as a side effect
of reporting" path this refusal exists to close.

IT IS SEPARATE FROM THE MIGRATION THAT CALLS IT because a mint is not a migration step. A
migration moves credentials that already exist; minting one that does not is a different act
with a different authorization, and the two share only the fact that one can DISCOVER the
need for the other.
"""

from __future__ import annotations

from dataclasses import dataclass

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_registry import provider_row
from _lpm_results import ManagerError, invalid_request

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "AcquisitionHandoff",
    "acquisition_handoff",
]


@dataclass(frozen=True, kw_only=True)
class AcquisitionHandoff:
    """The bounded description of a mint an operator must perform deliberately."""

    provider: str
    kind: str
    purpose: str
    account_id: str
    terminal: str


def acquisition_handoff(
    *, provider: str, kind: str, account_id: str, purpose: str, authorized: bool
) -> Result[AcquisitionHandoff, ManagerError]:
    """Describe the mint for one missing credential, or refuse for want of authorization.

    The terminal comes from the registry row rather than from the caller, so a handoff can
    only ever name an acquisition path the contract already registered — an unregistered
    provider or kind is refused before any description is built.
    """
    for name, value in (("account_id", account_id), ("purpose", purpose)):
        if value == "":
            return Failure(invalid_request(message=f"handoff {name} must be a non-empty string"))
    row = provider_row(provider=provider, kind=kind)
    if row is None:
        return Failure(
            invalid_request(message=f"{provider} {kind} is not a registered provider row")
        )
    if not authorized:
        return Failure(
            invalid_request(message="minting a credential requires separate operator authorization")
        )
    return Success(
        AcquisitionHandoff(
            provider=provider,
            kind=kind,
            purpose=purpose,
            account_id=account_id,
            terminal=row.acquisition_terminal,
        )
    )
