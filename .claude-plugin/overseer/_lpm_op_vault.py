"""One role's authorized, namespace-bound access to one vault — and nothing wider.

SPECIFICATION/contracts.md gates every SecretStore call this backend makes behind two
questions that are asked BEFORE the first child is spawned and one that is asked before the
first credential item is read. All three are properties of the pair (this role, this
vault), which is why they live together here.

MAY THIS ROLE ADDRESS THIS VAULT AT ALL? "every registry role's complete
external-executable allowlist is the one retained canonical `op` path: each role MUST
require its `op_executable` to equal that retained canonical regular executable, invoke only
that absolute path, constrain the vault to its table row and reject every other prefix."
Both halves are decided from values this process already holds, so a refusal costs no
child, no token read and no backend call — which is what `authorization_defect` is for and
why :func:`namespace_bound_summaries` asks it first.

IS THIS VAULT BOUND TO THIS MANAGER'S NAMESPACE? "Before every SecretStore read or create,
the role MUST enumerate the namespace title in each vault that call will access and require
exactly one well-formed item whose three identity fields equal the current manager
namespace; absence, duplicates, mismatch or an unsafe machine-id source MUST return
`store-unavailable` before reading credential data or mutating."

ONE ENUMERATION ANSWERS BOTH THE BINDING AND THE CALLER. The contract requires the
binding check to "validate it independently, while credential metadata get, list and chain
reconciliation MUST exclude exactly that title" — independently of the record grammar, not
in a separate backend call. So :func:`namespace_bound_summaries` returns the WHOLE listing
it already read, including the reserved item, and the caller excludes that one title. A
second `item list` would be a second answer, and a backend that changed between the two
would leave the binding proved against a listing nobody used.

ABSENCE AND DUPLICATION ARE SEPARATE REASONS. Both are `store-unavailable` to the manager,
but one says the operator never created the binding item and the other says something
created a second one; sending a reader after the wrong one of those costs the whole
investigation. Neither resolves: the contract forbids choosing among duplicates, and
creating the missing item is a deliberate operator act performed before manager adoption.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_onepassword import NAMESPACE_ITEM_TITLE, namespace_mismatch
from _lpm_op import (
    OpRunner,
    op_item_get_argv,
    op_item_list_argv,
    retained_executable_defect,
    vault_scope_defect,
)
from _lpm_op_items import OpItem, parse_item_fields, parse_item_summaries
from _lpm_roles import CredentialRole

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "VaultAccess",
    "namespace_bound_summaries",
]


@dataclass(frozen=True, kw_only=True)
class VaultAccess:
    """The three fixed vectors, bound to one role's authority and one retained executable.

    `op_executable` is the value this role was HANDED in its closed input and
    `retained_executable` is the fork-inherited path the contract makes "the comparison
    authority for `op_executable`". Both are fields because the comparison is the whole
    control: a single path would leave nothing to compare, and the supplied one is the half
    a defective caller controls.
    """

    runner: OpRunner
    op_executable: str
    retained_executable: str
    role: CredentialRole

    def authorization_defect(self, *, vault: str) -> str | None:
        """Why this role may not address `vault` through this executable, or None.

        Executable first, because it is the question about the whole invocation: a role
        pointed at another binary is refused before anything asks which vault that binary
        would have been told to open.
        """
        substituted = retained_executable_defect(
            supplied=self.op_executable, retained=self.retained_executable
        )
        if substituted is not None:
            return substituted
        return vault_scope_defect(role=self.role, vault=vault)

    def summaries(self, *, vault: str) -> Result[tuple[OpItem, ...], str]:
        """Enumerate `vault`, or report that the enumeration did not complete.

        A non-zero exit is an UNKNOWN OUTCOME reported as a failure, never as an empty
        listing. An empty listing is how a backend outage comes to be read as authoritative
        absence, and absence is what licenses a genesis create.
        """
        outcome = self.runner(
            argv=op_item_list_argv(op_executable=self.op_executable, vault=vault),
            stdin_bytes=None,
        )
        if outcome.exit_status != 0:
            return Failure("the backend did not complete its enumeration")
        return parse_item_summaries(stdout=outcome.stdout)

    def fields(self, *, vault: str, item_id: str) -> Result[dict[str, str], str]:
        """Read one item's application fields by ITEM ID, never by title."""
        outcome = self.runner(
            argv=op_item_get_argv(op_executable=self.op_executable, vault=vault, item_id=item_id),
            stdin_bytes=None,
        )
        if outcome.exit_status != 0:
            return Failure("the backend did not complete an item read")
        return parse_item_fields(stdout=outcome.stdout)


def namespace_bound_summaries(
    *, access: VaultAccess, vault: str, expected: Mapping[str, str]
) -> Result[tuple[OpItem, ...], str]:
    """`vault`'s complete listing, returned only once its namespace binding holds.

    The reserved namespace item is LEFT IN the returned listing deliberately. Its exclusion
    belongs to the record grammar — "credential metadata get, list and chain reconciliation
    MUST exclude exactly that title" — and a function that dropped it here would make that
    exclusion invisible at the place the contract states it.
    """
    unauthorized = access.authorization_defect(vault=vault)
    if unauthorized is not None:
        return Failure(unauthorized)
    listing = access.summaries(vault=vault)
    if isinstance(listing, Failure):
        return listing
    summaries = listing.unwrap()
    unbound = _binding_defect(access=access, vault=vault, expected=expected, summaries=summaries)
    if unbound is not None:
        return Failure(unbound)
    return Success(summaries)


def _binding_defect(
    *,
    access: VaultAccess,
    vault: str,
    expected: Mapping[str, str],
    summaries: tuple[OpItem, ...],
) -> str | None:
    """Why `summaries` does not prove this vault is bound to this manager's namespace.

    It takes the ALREADY-READ listing rather than enumerating again, so the binding is
    proved against exactly the items its caller is about to use.
    """
    bound = [summary for summary in summaries if summary.title == NAMESPACE_ITEM_TITLE]
    if not bound:
        return "the namespace item is absent from that vault"
    if len(bound) > 1:
        return "the namespace item is duplicated in that vault"
    stored = access.fields(vault=vault, item_id=bound[0].item_id)
    if isinstance(stored, Failure):
        return stored.failure()
    return namespace_mismatch(stored=stored.unwrap(), expected=dict(expected))
