"""The credential-role launcher: validate, scrub, verify the key, exec — never return bytes.

SPECIFICATION/contracts.md makes the launcher a short-lived child created BEFORE any token
retrieval, whose parent passes only the closed role input, one closed role name, one
nullable key description and that role's declared descriptors. Inside the child, and
BEFORE key lookup, it reapplies the complete closed inherited credential-override scrub;
retrieves the named token from the Linux user keyring through `keyctl search`, `rdescribe`
and only then `pipe`; installs ONLY the corresponding manager-named variable; and
immediately replaces itself with the mapped role process.

TOKEN BYTES MUST NEVER RETURN ACROSS THE LAUNCHER PIPE OR ENTER THE PARENT. That is the
whole design: the parent manager and the selection brain never hold a service-account
token, so a bug in either cannot leak one. This module therefore exposes validation,
description checking, argv construction and the child ENVIRONMENT — and has no function
that returns a payload.

THE PERMISSION CHECK IS EXACT AND IT IS NOT "OWNER BITS ARE ENOUGH". The raw description
must contain exactly five fields — type `user`, decimal uid equal to the effective uid,
decimal gid, lowercase permission `3f0b0000`, and the required role description. An
optional `0x` prefix is normalized away before the comparison, and ANY other field or word
fails the lookup BEFORE the payload is piped. Any group or other permission therefore fails
closed: a key readable by another user is not the key this role was promised.

A FAILURE HERE IS A PRE-EXEC RESULT, NOT AN ABNORMAL EXIT. The launcher emits that role's
own exact secret-free failure object itself, destroys any key bytes and exits without role,
browser, store or target action. That distinction is load-bearing for final provisioning:
its pre-exec `store-unavailable` MUST NOT be reinterpreted as the ambiguous target-write
outcome that only applies after a successful exec.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_env import scrubbed_environment
from _lpm_results import ManagerError, internal_bug
from _lpm_roles import KEYRING_PERMISSION, CredentialRole, credential_role

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "DESCRIPTION_FIELDS",
    "KEYCTL_EXECUTABLE",
    "keyctl_pipe_argv",
    "keyctl_rdescribe_argv",
    "keyctl_search_argv",
    "pre_exec_failure_object",
    "role_child_environment",
    "user_keyring_description_matches",
    "validated_launch",
]

KEYCTL_EXECUTABLE: Final = "/usr/bin/keyctl"
DESCRIPTION_FIELDS: Final = 5
_USER_KEY_TYPE: Final = "user"

_UNAVAILABLE_ROLES: Final = (
    "acquisition-prerequisite",
    "browser-control",
    "metadata-reader",
    "lifecycle-writer",
    "report-writer",
    "recovery-writer",
)


def validated_launch(
    *, role_name: str, key_description: str | None, descriptors: Sequence[str]
) -> Result[CredentialRole, ManagerError]:
    """Validate the role name, key pairing and descriptor relation before any key lookup.

    Every refusal here is a caller BUG rather than an operator-correctable request: the
    role name, its key and its descriptor set all come from manager-owned code, and a
    mismatch means this process was asked to run a role that is not in the registry or to
    hand it authority the registry does not give it.
    """
    role = credential_role(name=role_name)
    if role is None:
        return Failure(internal_bug(message=f"unregistered credential role: {role_name}"))
    if key_description != role.key_description:
        return Failure(
            internal_bug(message=f"{role_name} requires key description {role.key_description}")
        )
    if tuple(descriptors) != role.descriptors:
        return Failure(
            internal_bug(
                message=f"{role_name} may inherit exactly: {', '.join(role.descriptors) or 'none'}"
            )
        )
    return Success(role)


def user_keyring_description_matches(
    *, raw: str, effective_uid: int, expected_description: str
) -> bool:
    """Whether a `keyctl rdescribe` line names exactly this role's owner-only user key.

    The separator is the default semicolon. Five fields exactly: a SIXTH field, or a
    description containing an extra word, fails rather than being ignored — the payload
    must not be piped on a key whose identity was only partly recognized.
    """
    fields = raw.split(";")
    if len(fields) != DESCRIPTION_FIELDS:
        return False
    key_type, uid, gid, permission, description = fields
    if key_type != _USER_KEY_TYPE or description != expected_description:
        return False
    if not uid.isdigit() or int(uid) != effective_uid or not gid.isdigit():
        return False
    return permission.removeprefix("0x") == KEYRING_PERMISSION


def keyctl_search_argv(*, description: str) -> tuple[str, ...]:
    """`keyctl search @u user <description>` — addressed at `@u` directly.

    Because the key grants owning-user read and search, the lookup must NOT depend on a
    session-keyring link or on possessor permission.
    """
    return (KEYCTL_EXECUTABLE, "search", "@u", _USER_KEY_TYPE, description)


def keyctl_rdescribe_argv(*, serial: str) -> tuple[str, ...]:
    """`keyctl rdescribe <serial>` — inspected BEFORE the payload is ever piped."""
    return (KEYCTL_EXECUTABLE, "rdescribe", serial)


def keyctl_pipe_argv(*, serial: str) -> tuple[str, ...]:
    """`keyctl pipe <serial>` — reached only after a valid description."""
    return (KEYCTL_EXECUTABLE, "pipe", serial)


def role_child_environment(
    *, role: CredentialRole, environ: Mapping[str, str], token: str | None
) -> dict[str, str]:
    """The environment the role process starts with: scrubbed, plus at most its own name.

    A token-bearing role receives ONLY its corresponding manager-named variable;
    `target-status` receives none. Passing a token for a tokenless role, or none for a
    token-bearing one, is refused by construction rather than silently tolerated.
    """
    child = scrubbed_environment(environ=environ)
    if role.variable is not None and token is not None:
        child[role.variable] = token
    return child


def pre_exec_failure_object(
    *, role_name: str, observer_mode: str | None = None
) -> dict[str, object]:
    """The exact secret-free object the LAUNCHER itself emits on a pre-exec failure.

    Search, description, pipe or permission failure, or failure to exec the validated role
    vector, maps to this role's own closed failure shape — never to a generic error and
    never to an abnormal-exit interpretation.
    """
    if role_name in _UNAVAILABLE_ROLES:
        return {"version": 1, "status": "unavailable"}
    if role_name == "provider-observer":
        status = "inconclusive" if observer_mode == "revalidate" else "unavailable"
        return {"version": 1, "status": status}
    return {"version": 1, "status": "store-unavailable"}
