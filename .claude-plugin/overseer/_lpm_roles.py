"""The closed credential-role registry: one key, one descriptor set, one `op` scope each.

SPECIFICATION/contracts.md states this registry as a closed table and adds the sentence
that makes it enforceable: "No other role-name string, key/role pairing, descriptor set or
external-command scope is registered initially."

THE POINT OF THE SPLIT IS LEAST AUTHORITY, NOT TIDINESS. 1Password cannot grant value
creation without read permission, so the acquisition writer's token can read the values
vault — and the contract answers that with BEHAVIOUR rather than permission: its adapter
must create one new generation item without reading any credential-generation item, may
list titles only to enumerate the namespace item, and must make no other values-vault read.
The selection brain, which decides WHICH record to use, is authorized to read metadata only
and must never receive either value-reader token.

`target-status` IS DELIBERATELY TOKENLESS. It answers "did that write commit?" and needs no
secret at all, so it carries a null key description, performs no keyring call, and receives
no manager or `OP_*` variable. A role that needed a token to report a commit status would
put a value-reading capability on the recovery path of every ambiguous write.

DESCRIPTOR SETS ARE PART OF THE IDENTITY, not an implementation detail: final provisioning
and `target-status` may hold only the target-reference lock, browser-control only its two
Chrome CDP pipes plus its private MCP-proxy and worker-control channels, and the
acquisition writer only the read end of one captured-credential pipe. Every other role
receives no extra descriptor, and no role may receive another role's set.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__: list[str] = [
    "CREDENTIAL_ROLES",
    "KEYRING_PERMISSION",
    "LIFECYCLE_ROLES",
    "CredentialRole",
    "PackagedCompanion",
    "credential_role",
    "execution_vector_for",
    "role_execution_vector",
]

KEYRING_PERMISSION: Final = "3f0b0000"

LIFECYCLE_ROLES: Final = ("lifecycle-writer", "report-writer", "recovery-writer")

_METADATA_READ: Final = ("metadata-vault item get", "metadata-vault item list")
_METADATA_WRITE: Final = (*_METADATA_READ, "metadata-vault revision item create")
_ACQUISITION_READ: Final = ("acquisition-vault item get", "acquisition-vault item list")
_VALUES_READ: Final = (
    "values-vault item list",
    "values-vault namespace-item item get",
    "values-vault referenced-value item get",
)


@dataclass(frozen=True, kw_only=True)
class CredentialRole:
    """One registered role: its key, its manager-named variable, descriptors and scope."""

    name: str
    key_description: str | None
    variable: str | None
    descriptors: tuple[str, ...]
    op_scope: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class PackagedCompanion:
    """The resolved interpreter and the packaged companion every role vector is built from.

    They travel TOGETHER because neither half is meaningful alone. The contract's vector is
    `<resolved-python> -I -S <packaged-companion> …`, where the interpreter is the canonical
    regular executable for the INVOKING interpreter and the companion is a canonical regular
    file inside THAT SAME validated installed package. A caller able to supply one without
    the other could run this package's companion under some other interpreter, or another
    package's companion under this one — and either pairing runs code the validated root
    never vouched for.
    """

    python_executable: str
    packaged_companion: str


def _role(
    *,
    name: str,
    key_description: str | None,
    variable: str | None,
    descriptors: tuple[str, ...] = (),
    op_scope: tuple[str, ...] = (),
) -> CredentialRole:
    return CredentialRole(
        name=name,
        key_description=key_description,
        variable=variable,
        descriptors=descriptors,
        op_scope=op_scope,
    )


CREDENTIAL_ROLES: Final[dict[str, CredentialRole]] = {
    role.name: role
    for role in (
        _role(
            name="acquisition-prerequisite",
            key_description="lpm-op-acquisition-reader",
            variable="LPM_ACQUISITION_READER_OP_SERVICE_ACCOUNT_TOKEN",
            op_scope=_ACQUISITION_READ,
        ),
        _role(
            name="browser-control",
            key_description="lpm-op-acquisition-reader",
            variable="LPM_ACQUISITION_READER_OP_SERVICE_ACCOUNT_TOKEN",
            descriptors=("chrome-cdp-read", "chrome-cdp-write", "mcp-proxy", "worker-control"),
            op_scope=_ACQUISITION_READ,
        ),
        _role(
            name="acquisition-writer",
            key_description="lpm-op-acquisition",
            variable="LPM_ACQUISITION_OP_SERVICE_ACCOUNT_TOKEN",
            descriptors=("captured-credential-read",),
            op_scope=(
                *_METADATA_WRITE,
                "values-vault item list",
                "values-vault namespace-item item get",
                "values-vault immutable-generation item create",
            ),
        ),
        _role(
            name="metadata-reader",
            key_description="lpm-op-metadata-reader",
            variable="LPM_METADATA_READER_OP_SERVICE_ACCOUNT_TOKEN",
            op_scope=_METADATA_READ,
        ),
        _role(
            name="lifecycle-writer",
            key_description="lpm-op-metadata-writer",
            variable="LPM_METADATA_WRITER_OP_SERVICE_ACCOUNT_TOKEN",
            op_scope=_METADATA_WRITE,
        ),
        _role(
            name="report-writer",
            key_description="lpm-op-metadata-writer",
            variable="LPM_METADATA_WRITER_OP_SERVICE_ACCOUNT_TOKEN",
            op_scope=_METADATA_WRITE,
        ),
        _role(
            name="recovery-writer",
            key_description="lpm-op-metadata-writer",
            variable="LPM_METADATA_WRITER_OP_SERVICE_ACCOUNT_TOKEN",
            op_scope=_METADATA_WRITE,
        ),
        _role(
            name="provider-observer",
            key_description="lpm-op-provider-observer",
            variable="LPM_PROVIDER_OBSERVER_OP_SERVICE_ACCOUNT_TOKEN",
            op_scope=_VALUES_READ,
        ),
        _role(
            name="final-provisioning",
            key_description="lpm-op-value-reader",
            variable="LPM_VALUE_READER_OP_SERVICE_ACCOUNT_TOKEN",
            descriptors=("target-reference-lock",),
            op_scope=_VALUES_READ,
        ),
        _role(
            name="target-status",
            key_description=None,
            variable=None,
            descriptors=("target-reference-lock",),
        ),
    )
}


def credential_role(*, name: str) -> CredentialRole | None:
    """The registered role, or None. An unregistered name has no fallback by design."""
    return CREDENTIAL_ROLES.get(name)


def execution_vector_for(*, companion: PackagedCompanion, role: CredentialRole) -> tuple[str, ...]:
    """The one execution vector an ALREADY-RESOLVED registered role maps to.

    `<resolved-python> -I -S <packaged-companion> --credential-role <role-name>`. The
    mapping lives in manager-owned code, never in configuration or request input: these
    vectors are the COMPLETE role-executable allowlist, and the launcher accepts no
    caller-supplied executable or argument.

    This spelling exists beside the name-keyed one because a caller holding a resolved
    `CredentialRole` has ALREADY had the registration question answered. Re-deriving the
    answer there would add an "unregistered" branch to code that cannot reach it, and the
    only honest way to cover such a branch is to stop asking the question twice.
    """
    return (
        companion.python_executable,
        "-I",
        "-S",
        companion.packaged_companion,
        "--credential-role",
        role.name,
    )


def role_execution_vector(
    *, python_executable: str, packaged_companion: str, name: str
) -> tuple[str, ...] | None:
    """The one execution vector a role name maps to, or None when unregistered."""
    role = credential_role(name=name)
    if role is None:
        return None
    return execution_vector_for(
        companion=PackagedCompanion(
            python_executable=python_executable, packaged_companion=packaged_companion
        ),
        role=role,
    )
