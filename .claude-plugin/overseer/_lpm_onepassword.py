"""The initial OnePassword backend: three vaults, one namespace, create-only revisions.

SPECIFICATION/contracts.md names `OnePasswordSecretStore` as the required initial backend
and constrains it in three ways this module makes mechanical.

THREE VAULTS, AND THE SEPARATION IS THE POINT. Acquisition login and mailbox material,
credential METADATA and raw credential VALUES live in three distinct vaults so that a role
authorized to decide WHICH credential to use is not thereby authorized to read one. The
value reference is an opaque pointer into the third vault; nothing in a metadata record
ever holds bytes.

CREATE ONLY — NEVER `op item edit`, never a revision deletion, never a reliance on 1Password
item-title uniqueness. Those three are one rule seen from three sides: the conditional
comparison is carried by the append-only chain, and any of them would silently reintroduce
last-writer-wins on a record whose whole safety story is "a stale writer's create cannot be
the next revision".

ONE NAMESPACE BINDING, CHECKED BEFORE EVERY READ OR CREATE. The vaults are bound to exactly
one host identity, effective uid and canonical state path, and a manager on another host,
under another uid or using another state path MUST NOT read or mutate through them. The
`machine_id_sha256` field is the digest of the one newline-trimmed lowercase 32-hex value
read from a regular root-owned mode-`0444` `/etc/machine-id`: an UNSAFE machine-id source is
`store-unavailable`, because a forgeable host identity is no identity at all.

Absence, duplicates or a mismatch of the namespace item is `store-unavailable` BEFORE any
credential data is read or mutated — not a reason to create one. Creating it is a
deliberate operator act performed before manager adoption.
"""

from __future__ import annotations

import re
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import sha256_hex

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ACQUISITION_VAULT",
    "MACHINE_ID_MODE",
    "METADATA_VAULT",
    "NAMESPACE_ITEM_TITLE",
    "NAMESPACE_MEMBERS",
    "VALUES_VAULT",
    "machine_id_digest",
    "namespace_item_fields",
    "namespace_mismatch",
    "op_item_create_argv",
    "previous_value_ref",
    "value_ref",
    "value_ref_is_registered",
    "values_item_title",
]

ACQUISITION_VAULT: Final = "llm-provider-manager-acquisition"
METADATA_VAULT: Final = "llm-provider-manager-token-metadata"
VALUES_VAULT: Final = "llm-provider-manager-token-values"

NAMESPACE_ITEM_TITLE: Final = "llm-provider-manager-namespace"
NAMESPACE_MEMBERS: Final = ("version", "machine_id_sha256", "effective_uid", "manager_state")

MACHINE_ID_MODE: Final = 0o444

_MACHINE_ID = re.compile(r"\A[0-9a-f]{32}\Z")
_VALUE_REF = re.compile(
    r"\Aop://llm-provider-manager-token-values/(?P<record_id>[0-9a-f-]{36})-"
    r"(?P<generation>[0-9a-f-]{36})/credential\Z"
)


def machine_id_digest(*, machine_id: str) -> str | None:
    """The namespace digest for a machine-id value, or None when the value is unsafe.

    The value must be exactly one newline-trimmed lowercase 32-hex string. Anything else —
    an uppercase spelling, a short read, a second line — is refused rather than hashed,
    because a namespace bound to a malformed host identity binds to nothing.
    """
    trimmed = machine_id.rstrip("\n")
    if _MACHINE_ID.match(trimmed) is None:
        return None
    return sha256_hex(data=trimmed.encode("ascii"))


def namespace_item_fields(
    *, machine_id_sha256: str, effective_uid: int, manager_state: str
) -> dict[str, str]:
    """The exact four application fields every namespace item must carry.

    `effective_uid` is base-10 without a leading zero except the value zero, and
    `manager_state` is the canonical absolute state path WITHOUT a trailing slash.
    """
    return {
        "version": "1",
        "machine_id_sha256": machine_id_sha256,
        "effective_uid": str(effective_uid),
        "manager_state": manager_state.rstrip("/") or "/",
    }


def namespace_mismatch(*, stored: object, expected: dict[str, str]) -> str | None:
    """Why `stored` does not bind this manager's namespace, or None when it does."""
    if not isinstance(stored, dict):
        return "namespace item is not an object"
    fields = cast("dict[str, object]", stored)
    if sorted(fields) != sorted(NAMESPACE_MEMBERS):
        return "namespace item has the wrong application fields"
    for member in NAMESPACE_MEMBERS:
        if fields[member] != expected[member]:
            return f"namespace item {member} names another manager namespace"
    return None


def values_item_title(*, record_id: str, value_generation: str) -> str:
    """`<record_id>-<value_generation>` — the immutable generation item's exact title."""
    return f"{record_id}-{value_generation}"


def value_ref(*, record_id: str, value_generation: str) -> str:
    """The one registered `value_ref` wire form. Stated literally by the contract.

    This is an explicit external-backend wire form, so it keeps its own syntax rather than
    going through the manager's length-prefixed digest identity.
    """
    title = values_item_title(record_id=record_id, value_generation=value_generation)
    return f"op://{VALUES_VAULT}/{title}/credential"


def previous_value_ref(*, record_id: str, prior_generation: str) -> str:
    """The same path with the immediately prior generation."""
    return value_ref(record_id=record_id, value_generation=prior_generation)


def value_ref_is_registered(*, reference: str) -> bool:
    """Whether `reference` has the one registered shape; any other shape is rejected."""
    return _VALUE_REF.match(reference) is not None


def op_item_create_argv(*, op_executable: str, vault: str) -> tuple[str, ...]:
    """`op item create --vault <vault> -` — the only mutation verb this backend uses.

    The item JSON is streamed to the child's standard input over an anonymous owner-process
    pipe: no assignment argument, no template file and no environment field may carry a
    credential, because all three are readable from outside the process.
    """
    return (op_executable, "item", "create", "--vault", vault, "-")
