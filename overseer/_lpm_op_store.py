"""`OnePasswordSecretStore` — the required initial backend behind the `SecretStore` port.

SPECIFICATION/contracts.md names it directly: "The required initial backend is
`OnePasswordSecretStore`." Everything it does is defined by the three mechanics modules
beside it — the namespace-bound vault access, the chains a metadata read resolves to, and
the one create a conditional write appends — and this module is where those become the
port's three methods.

IT IS A COMPOSITION, DELIBERATELY. A `SecretStore` is "the manager's replaceable secret
backend", and the whole point of the port is that a future registered backend "MUST preserve
the same port and privilege split but MAY define a different opaque `value_ref` namespace".
Putting the mechanics in this class instead would make the port's one implementation the
place three unrelated concerns live, and the next backend would have nothing to replace
piecewise.

ONE STORE IS BOUND TO ONE ROLE AND ONE NAMESPACE, and that is the privilege split made
structural. The authority is in `access` — its registry role, its retained executable, its
vault scope — so a `metadata-reader`'s store CANNOT answer a conditional set with a
committed create however it is called: the create's vault is outside that role's row and the
refusal happens before any child. A store that took its role per call would be one argument
away from lending a reader a writer's authority.

THE NAMESPACE IS A FIELD RATHER THAN A PER-CALL ARGUMENT for the same reason. "The three
initial 1Password vaults MUST be bound to exactly one manager state namespace: one host
identity, effective uid and canonical `<manager-state>` path", and that binding is a property
of the PROCESS, resolved once from the host. A caller that could vary it between a get and
the write that follows could prove one namespace and mutate under another.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_op_metadata import metadata_get_answer, metadata_list_answer
from _lpm_op_revision import conditional_set_answer
from _lpm_op_vault import VaultAccess
from _lpm_store import ConditionalSet

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "OnePasswordSecretStore",
]


@dataclass(frozen=True, kw_only=True)
class OnePasswordSecretStore:
    """The initial backend: one role's authority, one namespace, three closed answers."""

    access: VaultAccess
    namespace: Mapping[str, str]

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        """The current logical record for `record_id`, or authoritative absence."""
        return metadata_get_answer(
            access=self.access, namespace=self.namespace, record_id=record_id
        )

    def metadata_list(self) -> dict[str, object]:
        """Every chain's current logical revision, plus every invalid-chain descriptor."""
        return metadata_list_answer(access=self.access, namespace=self.namespace)

    def credential_conditional_set(self, *, request: ConditionalSet) -> dict[str, object]:
        """Append the one desired revision when the expected predecessor still holds."""
        return conditional_set_answer(access=self.access, namespace=self.namespace, request=request)
