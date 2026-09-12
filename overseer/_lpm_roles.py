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
    "credential_role",
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


def role_execution_vector(
    *, python_executable: str, packaged_companion: str, name: str
) -> tuple[str, ...] | None:
    """The one execution vector a role name maps to, or None when unregistered.

    `<resolved-python> -I -S <packaged-companion> --credential-role <role-name>`. The
    mapping lives in manager-owned code, never in configuration or request input: these
    vectors are the COMPLETE role-executable allowlist, and the launcher accepts no
    caller-supplied executable or argument.
    """
    if credential_role(name=name) is None:
        return None
    return (python_executable, "-I", "-S", packaged_companion, "--credential-role", name)
