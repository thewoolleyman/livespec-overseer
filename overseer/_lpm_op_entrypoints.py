"""The consumer role entrypoints: what a role process does once the launcher's exec lands.

SPECIFICATION/contracts.md splits one credential-role run in two. Everything before the exec
belongs to the launcher — the registry validation, the scrub, the keyring read, the process
replacement — and `_lpm_launcher` / `_lpm_role_child` own it. Everything after belongs to the
role, and these three functions are that half for the consumer roles this backend serves:
the metadata reader, the three metadata writers, and final provisioning.

A ROLE BUILDS ITS OWN AUTHORITY FROM WHAT THE LAUNCHER LEFT IT, which is why `RoleEntry`
exists. The launcher installed exactly one manager-named variable and exec'd; the role then
knows its own name, the retained `op` path, the path it was HANDED, its environment and its
namespace. Nothing in that list is a capability — the token is read per call by
`HostOpChild`, from the variable the registry names for this role — so an entry cannot carry
authority to a role the registry did not give it.

AN UNREGISTERED OR TOKENLESS ROLE HAS NO FALLBACK. "No other role-name string, key/role
pairing, descriptor set or external-command scope is registered initially", and the tokenless
`target-status` "MUST ... receive no manager or `OP_*` credential variable" — it answers "did
that write commit?" and reads no vault at all. Either one asks for a store this module must
not build, so both become that role's own closed failure object before any child exists.

THE READER'S TWO INPUTS ARE TWO WHOLE OBJECTS, not one object with an optional member:
`{"version":1,"mode":"get","record_id":...}` or `{"version":1,"mode":"list",...}`. The
mode/record relation is therefore part of the shape, and a `get` with nothing to get or a
`list` carrying a record is an input the contract never defined. "Before any browser, store or
target action, each role MUST reject a missing, extra, duplicate or wrongly typed member, a
relation-invalid value or an inapplicable descriptor as a role failure."

FINAL PROVISIONING VALIDATES ITS TARGET BINDING FIRST. "after successful role exec it MUST
validate the target binding before reading that variable or accessing the values vault", and
"the preceding read-only target-binding validation is not the write call" — so a binding that
does not validate is still the pre-write `store-unavailable`, and it must leave no
values-vault access behind. The validation is a PORT rather than an import because it is the
registered target's, and the target is chosen by configuration rather than by this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_launcher import pre_exec_failure_object
from _lpm_op import HostOpChild
from _lpm_op_store import OnePasswordSecretStore
from _lpm_op_values import TargetWrite, ValueReference, provisioned_credential_result
from _lpm_op_vault import VaultAccess
from _lpm_roles import credential_role
from _lpm_store import ConditionalSet

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "READER_GET_MODE",
    "READER_LIST_MODE",
    "RoleEntry",
    "TargetBinding",
    "metadata_read_result",
    "metadata_write_result",
    "provisioning_result",
]

READER_GET_MODE: Final = "get"
READER_LIST_MODE: Final = "list"


class TargetBinding(Protocol):
    """The registered target's read-only binding validation, which receives NO credential."""

    def __call__(self) -> str | None:
        """Why this reference does not bind to this consumer run, or None when it does."""
        ...


@dataclass(frozen=True, kw_only=True)
class RoleEntry:
    """What one role process knows about itself the moment the launcher's exec lands.

    `op_executable` is the value this role was HANDED in its closed input;
    `retained_executable` is the fork-inherited path the contract makes the comparison
    authority for it. Both travel because the comparison is the control.
    """

    role_name: str
    op_executable: str
    retained_executable: str
    environ: Mapping[str, str]
    namespace: Mapping[str, str]
    timeout_seconds: float


def metadata_read_result(
    *, entry: RoleEntry, mode: str, record_id: str | None
) -> dict[str, object]:
    """One metadata read in this role's own closed shape: a record, a list, or a refusal."""
    store = _store(entry=entry)
    if store is None:
        return pre_exec_failure_object(role_name=entry.role_name)
    if mode == READER_LIST_MODE and record_id is None:
        return store.metadata_list()
    if mode == READER_GET_MODE and record_id is not None:
        return store.metadata_get(record_id=record_id)
    return pre_exec_failure_object(role_name=entry.role_name)


def metadata_write_result(*, entry: RoleEntry, request: ConditionalSet) -> dict[str, object]:
    """One conditional revision appended under this role's own authority, or its refusal."""
    store = _store(entry=entry)
    if store is None:
        return pre_exec_failure_object(role_name=entry.role_name)
    return store.credential_conditional_set(request=request)


def provisioning_result(
    *,
    entry: RoleEntry,
    reference: ValueReference,
    binding: TargetBinding,
    write: TargetWrite,
) -> dict[str, object]:
    """Validate the target binding, then resolve one value and hand it straight to the target."""
    access = _authorized(entry=entry)
    if access is None:
        return pre_exec_failure_object(role_name=entry.role_name)
    unbound = binding()
    if unbound is not None:
        # Before the variable is read and before the vault is opened, so this refusal costs
        # no credential access at all — which is the whole reason the order is stated.
        return pre_exec_failure_object(role_name=entry.role_name)
    return provisioned_credential_result(
        access=access, namespace=entry.namespace, reference=reference, write=write
    )


def _store(*, entry: RoleEntry) -> OnePasswordSecretStore | None:
    """This role's `SecretStore`, or None when the registry grants it no token at all."""
    access = _authorized(entry=entry)
    if access is None:
        return None
    return OnePasswordSecretStore(access=access, namespace=entry.namespace)


def _authorized(*, entry: RoleEntry) -> VaultAccess | None:
    """This role's authorized vault access, or None when there is no such registered role.

    An unregistered name and the tokenless `target-status` are one answer here: neither has a
    manager-named variable an `op` child could be given, so neither can be handed backend
    access. Refusing both without a fallback is the registry's closed-table rule holding.
    """
    role = credential_role(name=entry.role_name)
    if role is None or role.variable is None:
        return None
    return VaultAccess(
        runner=HostOpChild(
            environ=entry.environ,
            variable=role.variable,
            timeout_seconds=entry.timeout_seconds,
        ),
        op_executable=entry.op_executable,
        retained_executable=entry.retained_executable,
        role=role,
    )
